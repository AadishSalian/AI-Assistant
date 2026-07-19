import sys
import tkinter as tk
import win32api
import win32con
import ctypes

# Make process DPI aware so coordinates perfectly match mss capture
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except:
    pass

class RegionSelector:
    def __init__(self):
        self.root = tk.Tk()
        self.root.attributes('-alpha', 0.4)
        self.root.attributes('-topmost', True)
        self.root.overrideredirect(True)
        self.root.config(cursor="cross")

        # Get total virtual screen size (spanning all monitors)
        self.vx = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
        self.vy = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
        vw = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        vh = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        
        self.root.geometry(f"{vw}x{vh}+{self.vx}+{self.vy}")

        self.canvas = tk.Canvas(self.root, cursor="cross", bg="black")
        self.canvas.pack(fill="both", expand=True)

        self.start_x = None
        self.start_y = None
        self.rect_id = None

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.root.bind("<Escape>", lambda e: self.cancel())
        
        # Bring to front aggressively
        self.root.lift()
        self.root.focus_force()

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y, 
            outline='red', width=3, fill="gray", stipple="gray50"
        )

    def on_drag(self, event):
        if self.rect_id:
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        if self.start_x is None: return
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        
        # Don't capture if it was just a tiny click
        if (x2 - x1) < 10 or (y2 - y1) < 10:
            self.cancel()
            return
            
        # Output coordinates (offset by virtual screen coordinates)
        print(f"{x1 + self.vx},{y1 + self.vy},{x2 + self.vx},{y2 + self.vy}")
        sys.stdout.flush()
        self.root.destroy()
        
    def cancel(self):
        print("CANCELLED")
        sys.stdout.flush()
        self.root.destroy()

if __name__ == "__main__":
    app = RegionSelector()
    app.root.mainloop()
