import os
import time
import subprocess
import logging
from io import BytesIO
from PIL import Image

logger = logging.getLogger("sweetie.screenshot_manager")

class ScreenshotManager:
    def __init__(self, config):
        self.config = config.get("screenshot", {})
        
        # Resolve save directory relative to sweetie root if not absolute
        save_dir = self.config.get("save_directory", "screenshots")
        if not os.path.isabs(save_dir):
            save_dir = os.path.join(os.getcwd(), save_dir)
        self.save_directory = save_dir
        self.format = self.config.get("format", "png").lower()
        
        os.makedirs(self.save_directory, exist_ok=True)

    def _save_and_copy(self, img_pil):
        """Saves the PIL Image to disk and copies it to the Windows clipboard."""
        import win32clipboard
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"Screenshot_{timestamp}.{self.format}"
        filepath = os.path.join(self.save_directory, filename)
        
        try:
            # Save to disk
            img_pil.save(filepath, format=self.format.upper())
            
            # Send to clipboard (requires converting to DIB format, stripping the 14-byte BMP header)
            output = BytesIO()
            img_rgb = img_pil.convert("RGB")
            img_rgb.save(output, "BMP")
            data = output.getvalue()[14:]
            output.close()
            
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
            
            logger.info(f"Saved screenshot to {filepath} and copied to clipboard.")
            return True, "Captured and copied to clipboard."
        except Exception as e:
            logger.error(f"Failed to save/copy screenshot: {e}")
            return False, "Failed to process the screenshot."

    def capture_fullscreen(self):
        """Captures all monitors combined."""
        import mss
        try:
            with mss.mss() as sct:
                # monitor[0] is a dict representing the bounding box of all monitors together
                sct_img = sct.grab(sct.monitors[0])
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                return self._save_and_copy(img)
        except Exception as e:
            logger.error(f"Fullscreen capture failed: {e}")
            return False, "Failed to capture the screen."

    def capture_window(self, hwnd):
        """Captures a specific window by its handle."""
        import mss
        import win32gui
        if not hwnd:
            return False, "No active window found to capture."
            
        try:
            # Get the exact window bounds
            rect = win32gui.GetWindowRect(hwnd)
            left, top, right, bottom = rect
            
            # Don't capture minimized or invisible windows
            if right - left <= 0 or bottom - top <= 0:
                return False, "Window is minimized or invalid."
                
            box = {"left": left, "top": top, "width": right - left, "height": bottom - top}
            
            with mss.mss() as sct:
                sct_img = sct.grab(box)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                return self._save_and_copy(img)
        except Exception as e:
            logger.error(f"Window capture failed: {e}")
            return False, "Failed to capture the window."

    def capture_region(self):
        """Launches the Tkinter overlay subprocess, waits for user selection, and captures it."""
        import mss
        try:
            overlay_path = os.path.join(os.getcwd(), "modules", "gui", "overlay.py")
            # Run the standalone UI process
            result = subprocess.run(
                ["python", overlay_path], 
                capture_output=True, 
                text=True, 
                creationflags=subprocess.CREATE_NO_WINDOW # Don't spawn a cmd terminal
            )
            
            output = result.stdout.strip()
            if not output or output == "CANCELLED":
                return False, "Screenshot cancelled."
                
            # Parse coordinates
            parts = output.split(',')
            if len(parts) != 4:
                return False, "Failed to parse region coordinates."
                
            x1, y1, x2, y2 = map(int, parts)
            box = {"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1}
            
            with mss.mss() as sct:
                sct_img = sct.grab(box)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                return self._save_and_copy(img)
        except Exception as e:
            logger.error(f"Region capture failed: {e}")
            return False, "Failed to capture region."
