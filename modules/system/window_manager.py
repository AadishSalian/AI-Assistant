import ctypes
from ctypes import wintypes
import win32gui
import win32api
import win32con
import json
import os
import logging
import traceback

logger = logging.getLogger("sweetie.window_manager")

# Make the process DPI aware to prevent misaligned snapping on mixed-DPI multi-monitor setups
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2) # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    pass

DWMWA_EXTENDED_FRAME_BOUNDS = 9

class RECT(ctypes.Structure):
    _fields_ = [
        ('left', wintypes.LONG),
        ('top', wintypes.LONG),
        ('right', wintypes.LONG),
        ('bottom', wintypes.LONG)
    ]

class WindowManager:
    def __init__(self, config):
        self.config = config
        self.memory_path = "config/layout_memory.json"
        self.layout_memory = self._load_memory()

    def _load_memory(self):
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load layout memory: {e}")
        return {}

    def _save_memory(self):
        os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
        try:
            with open(self.memory_path, 'w') as f:
                json.dump(self.layout_memory, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save layout memory: {e}")

    def get_dwm_offsets(self, hwnd):
        """Calculates the invisible border offsets applied by the Windows Desktop Window Manager."""
        rect = RECT()
        res = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd),
            wintypes.DWORD(DWMWA_EXTENDED_FRAME_BOUNDS),
            ctypes.byref(rect),
            ctypes.sizeof(rect)
        )
        if res != 0:
            return 0, 0, 0, 0
            
        win_rect = win32gui.GetWindowRect(hwnd)
        # Offset = Standard Window Rect - Visible DWM Rect
        left_offset = win_rect[0] - rect.left
        top_offset = win_rect[1] - rect.top
        right_offset = win_rect[2] - rect.right
        bottom_offset = win_rect[3] - rect.bottom
        
        return left_offset, top_offset, right_offset, bottom_offset

    def position_window(self, layout):
        """Positions the currently foreground window to a predefined layout."""
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return False, "No active window found."

        # First, ensure window is restored (not maximized/minimized) so SetWindowPos works predictably
        tup = win32gui.GetWindowPlacement(hwnd)
        if tup[1] == win32con.SW_SHOWMAXIMIZED or tup[1] == win32con.SW_SHOWMINIMIZED:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            
        if layout == 'maximize':
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            return True, "Maximized."
        elif layout == 'minimize':
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            return True, "Minimized."

        # Find which monitor this window is currently on
        monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
        monitor_info = win32api.GetMonitorInfo(monitor)
        work_area = monitor_info['Work'] # (left, top, right, bottom) excluding taskbar
        
        wa_left, wa_top, wa_right, wa_bottom = work_area
        wa_width = wa_right - wa_left
        wa_height = wa_bottom - wa_top

        # Desired Visible Rect
        target_w, target_h = wa_width, wa_height
        target_x, target_y = wa_left, wa_top

        if layout in ['left', 'left-half']:
            target_w = wa_width // 2
        elif layout in ['right', 'right-half']:
            target_w = wa_width // 2
            target_x = wa_left + target_w
        elif layout == 'top-left':
            target_w = wa_width // 2
            target_h = wa_height // 2
        elif layout == 'top-right':
            target_w = wa_width // 2
            target_h = wa_height // 2
            target_x = wa_left + target_w
        elif layout == 'bottom-left':
            target_w = wa_width // 2
            target_h = wa_height // 2
            target_y = wa_top + target_h
        elif layout == 'bottom-right':
            target_w = wa_width // 2
            target_h = wa_height // 2
            target_x = wa_left + target_w
            target_y = wa_top + target_h
        elif layout == 'center':
            target_w = int(wa_width * 0.7)
            target_h = int(wa_height * 0.8)
            target_x = wa_left + int(wa_width * 0.15)
            target_y = wa_top + int(wa_height * 0.1)
        else:
            return False, f"I don't know the layout '{layout}'."

        # Apply DWM offsets so the *visible* boundaries align perfectly with our target rect
        loff, toff, roff, boff = self.get_dwm_offsets(hwnd)
        
        final_x = target_x + loff
        final_y = target_y + toff
        final_w = target_w + (roff - loff)
        final_h = target_h + (boff - toff)

        win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, final_x, final_y, final_w, final_h, win32con.SWP_SHOWWINDOW)
        
        # Record layout memory
        import win32process
        import psutil
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            exe_name = psutil.Process(pid).name().replace(".exe", "")
            self.record_layout(exe_name, layout)
        except Exception as e:
            logger.error(f"Failed to record layout: {e}")
        
        return True, f"Snapped to {layout}."

    def move_to_monitor(self, monitor_index):
        """Moves the foreground window to the nth monitor (1-indexed)."""
        monitors = win32api.EnumDisplayMonitors()
        if not monitors:
            return False, "Could not detect monitors."
            
        if monitor_index < 1 or monitor_index > len(monitors):
            return False, f"Monitor {monitor_index} doesn't exist. I only see {len(monitors)} connected."
            
        # Target monitor info
        target_monitor_hhandle, _, target_rect = monitors[monitor_index - 1]
        
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return False, "No active window found."
            
        # Current monitor info
        curr_monitor_handle = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
        curr_info = win32api.GetMonitorInfo(curr_monitor_handle)
        curr_rect = curr_info['Monitor']
        
        # Calculate proportional offset (e.g., if window is centered on monitor 1, keep it centered on monitor 2)
        win_rect = win32gui.GetWindowRect(hwnd)
        x_ratio = (win_rect[0] - curr_rect[0]) / (curr_rect[2] - curr_rect[0])
        y_ratio = (win_rect[1] - curr_rect[1]) / (curr_rect[3] - curr_rect[1])
        
        new_w = win_rect[2] - win_rect[0]
        new_h = win_rect[3] - win_rect[1]
        
        new_x = target_rect[0] + int(x_ratio * (target_rect[2] - target_rect[0]))
        new_y = target_rect[1] + int(y_ratio * (target_rect[3] - target_rect[1]))
        
        # Restore if maximized before moving
        tup = win32gui.GetWindowPlacement(hwnd)
        was_maximized = False
        if tup[1] == win32con.SW_SHOWMAXIMIZED:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            was_maximized = True
            
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, new_x, new_y, new_w, new_h, win32con.SWP_SHOWWINDOW)
        
        if was_maximized:
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            
        return True, f"Moved to monitor {monitor_index}."

    def switch_desktop(self, direction_or_num):
        try:
            from pyvda import VirtualDesktop, get_virtual_desktops
        except ImportError:
            return False, "Virtual desktop library (pyvda) is not installed."
            
        try:
            current = VirtualDesktop.current()
            desktops = get_virtual_desktops()
            
            target_num = None
            if str(direction_or_num).isdigit():
                target_num = int(direction_or_num)
            elif direction_or_num == 'left':
                target_num = current.number - 1
            elif direction_or_num == 'right':
                target_num = current.number + 1
            elif direction_or_num == 'next':
                target_num = current.number + 1
            elif direction_or_num == 'previous':
                target_num = current.number - 1
                
            if not target_num:
                return False, f"I don't understand the desktop destination '{direction_or_num}'."
                
            if target_num < 1:
                return False, "You are already on the first desktop."
            if target_num > len(desktops):
                return False, f"Desktop {target_num} doesn't exist. You only have {len(desktops)}."
                
            VirtualDesktop(target_num).go()
            return True, f"Switched to desktop {target_num}."
        except Exception as e:
            logger.error(f"pyvda error: {e}")
            logger.error(traceback.format_exc())
            return False, "Failed to switch virtual desktops."

    def create_desktop(self):
        """Creates a new virtual desktop and switches to it."""
        from pyvda import VirtualDesktop
        try:
            new_desktop = VirtualDesktop.create()
            new_desktop.go()
            return True, "Created and switched to a new virtual desktop."
        except Exception as e:
            logger.error(f"Failed to create virtual desktop: {e}")
            return False, "Failed to create a virtual desktop."
            
    def close_desktop(self):
        """Closes the current virtual desktop."""
        from pyvda import VirtualDesktop
        try:
            current = VirtualDesktop.current()
            current.remove()
            return True, "Closed the virtual desktop."
        except Exception as e:
            logger.error(f"Failed to close virtual desktop: {e}")
            return False, "Failed to close the virtual desktop."

    def record_layout(self, app_name, layout):
        """Records that the user used 'layout' for 'app_name'."""
        app_name = app_name.lower()
        if app_name not in self.layout_memory:
            self.layout_memory[app_name] = {}
        
        self.layout_memory[app_name][layout] = self.layout_memory[app_name].get(layout, 0) + 1
        self._save_memory()

    def get_suggested_layout(self, app_name):
        """Returns the most frequently used layout for this app, if used > 2 times."""
        app_name = app_name.lower()
        if app_name in self.layout_memory:
            layouts = self.layout_memory[app_name]
            if not layouts: return None
            
            # Get the layout with the highest frequency
            best_layout = max(layouts, key=layouts.get)
            frequency = layouts[best_layout]
            
            # Only suggest if it's a strongly established pattern
            if frequency >= 2:
                return best_layout
        return None
