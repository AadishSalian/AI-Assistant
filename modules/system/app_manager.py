import os
import psutil
import winreg
import logging
import subprocess

try:
    import pygetwindow as gw
except ImportError:
    gw = None

logger = logging.getLogger("sweetie.app_manager")

class AppManager:
    def __init__(self, config):
        self.apps_config = config.get('apps', {})

    def resolve_app_name(self, app_name):
        app_name = app_name.lower().strip()
        # Direct hit in config
        if app_name in self.apps_config:
            return app_name, self.apps_config[app_name]
            
        # Fuzzy match in config (keys or the actual path)
        for key, path in self.apps_config.items():
            if key in app_name or app_name in key or app_name in path.lower():
                return key, path
                
        # Fallback for OS recognized names (like notepad, calc)
        return app_name, f"{app_name}.exe"

    def find_running_processes(self, exe_name):
        exe_name = exe_name.lower()
        procs = []
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == exe_name:
                    procs.append(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return procs

    def _focus_window_for_pids(self, pids):
        import win32gui
        import win32process
        import win32con
        import win32com.client
        
        focused = False
        def callback(hwnd, _):
            nonlocal focused
            if focused: return True
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                if found_pid in pids:
                    try:
                        # Windows sometimes blocks SetForegroundWindow. Alt keypress bypasses it.
                        shell = win32com.client.Dispatch("WScript.Shell")
                        shell.SendKeys('%')
                        
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        win32gui.SetForegroundWindow(hwnd)
                        focused = True
                    except Exception as e:
                        logger.error(f"Failed to focus hwnd: {e}")
            return True
            
        win32gui.EnumWindows(callback, None)
        return focused

    def launch_app(self, app_name):
        resolved_name, path = self.resolve_app_name(app_name)
        exe_name = os.path.basename(path).lower()
        
        # Check if already running to focus instead
        pids = self.find_running_processes(exe_name)
        if pids:
            logger.info(f"{exe_name} is already running. Attempting to focus via PIDs.")
            if self._focus_window_for_pids(pids):
                return True, f"Switched to {resolved_name}."
            else:
                logger.info(f"Processes found but no visible windows. Launching new instance.")
            
        # Launch it
        try:
            logger.info(f"Launching {resolved_name} via {path}")
            os.startfile(path)
            return True, f"Launched {resolved_name}."
        except Exception as e:
            logger.error(f"Failed to launch {path}: {e}")
            return False, f"I couldn't launch {resolved_name}. Check the path in config."

    def switch_app(self, app_name):
        resolved_name, path = self.resolve_app_name(app_name)
        exe_name = os.path.basename(path).lower()
        
        pids = self.find_running_processes(exe_name)
        if not pids:
            return False, f"I don't see any running processes for {resolved_name}."
            
        if self._focus_window_for_pids(pids):
            return True, f"Switched to {resolved_name}."
            
        return False, f"Could not find a visible window for {resolved_name}."

    def close_app(self, app_name, batch=False, except_app=None):
        if batch:
            # Batch closing logic
            return self._batch_close(app_name, except_app)
            
        resolved_name, path = self.resolve_app_name(app_name)
        exe_name = os.path.basename(path).lower()
        closed_count = 0
        
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == exe_name:
                    proc.terminate() # Graceful close (SIGTERM)
                    closed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        if closed_count > 0:
            return True, f"Closed {resolved_name}."
        return False, f"I couldn't find {resolved_name} running."

    def _batch_close(self, target_type, except_app=None):
        target_type = target_type.lower() if target_type else ""
        
        browsers = ['chrome.exe', 'firefox.exe', 'msedge.exe', 'brave.exe', 'opera.exe']
        except_exe = None
        if except_app:
            _, path = self.resolve_app_name(except_app)
            except_exe = os.path.basename(path).lower()
            
        config_exes = [os.path.basename(p).lower() for p in self.apps_config.values()]
            
        closed = []
        for proc in psutil.process_iter(['name']):
            try:
                p_name = proc.info['name'].lower()
                # Skip essential system processes and sweetie processes
                if p_name in ['explorer.exe', 'python.exe', 'cmd.exe', 'powershell.exe', 'piper.exe']:
                    continue
                    
                if except_exe and p_name == except_exe:
                    continue
                    
                should_close = False
                if 'browser' in target_type:
                    if p_name in browsers:
                        should_close = True
                elif 'everything' in target_type or 'all' in target_type:
                    # Safe constraint: only batch-close apps mapped in config
                    if p_name in config_exes:
                        should_close = True

                if should_close:
                    proc.terminate()
                    closed.append(p_name)
            except:
                continue
                
        if closed:
            return True, f"Closed {len(closed)} processes."
        return False, "Found nothing to close."

    def app_stats(self, app_name):
        resolved_name, path = self.resolve_app_name(app_name)
        exe_name = os.path.basename(path).lower()
        total_ram_mb = 0
        count = 0
        
        for proc in psutil.process_iter(['name', 'memory_info']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == exe_name:
                    total_ram_mb += proc.info['memory_info'].rss / (1024 * 1024)
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        if count > 0:
            return True, f"{resolved_name} is using {total_ram_mb:.0f} megabytes of RAM."
        return False, f"{resolved_name} doesn't appear to be running."

    def manage_startup(self, action, app_name):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        resolved_name, path = self.resolve_app_name(app_name) if app_name else ("", "")
        
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            
            if action == 'enable':
                if not path.endswith('.exe'):
                    return False, f"I don't have an absolute path for {resolved_name} to enable it."
                winreg.SetValueEx(key, resolved_name, 0, winreg.REG_SZ, path)
                winreg.CloseKey(key)
                return True, f"Enabled {resolved_name} on startup."
                
            elif action == 'disable':
                try:
                    winreg.DeleteValue(key, resolved_name)
                except FileNotFoundError:
                    pass
                winreg.CloseKey(key)
                return True, f"Disabled {resolved_name} from startup."
                
            elif action == 'list':
                items = []
                try:
                    i = 0
                    while True:
                        name, val, _ = winreg.EnumValue(key, i)
                        items.append(name)
                        i += 1
                except OSError:
                    pass
                winreg.CloseKey(key)
                return True, f"You have {len(items)} startup items registered."
                
        except Exception as e:
            logger.error(f"Registry access failed: {e}")
            return False, "I couldn't access the Windows Registry."
            
        return False, "Unknown startup action."
