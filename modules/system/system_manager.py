import os
import ctypes
import psutil
import logging

try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    from ctypes import cast, POINTER
except ImportError:
    pass

try:
    import screen_brightness_control as sbc
except ImportError:
    sbc = None

logger = logging.getLogger("sweetie.system_manager")

class SystemManager:
    def __init__(self):
        pass

    def get_volume_interface(self):
        try:
            devices = AudioUtilities.GetSpeakers()
            return devices.EndpointVolume
        except Exception as e:
            logger.error(f"Failed to get volume interface: {e}")
            return None

    def set_volume(self, level=None, direction=None):
        try:
            import pythoncom
            pythoncom.CoInitialize() # required if called on background thread
            volume_int = self.get_volume_interface()
            if not volume_int:
                return False, "Failed to access audio device."
                
            if direction == "up":
                current_vol = volume_int.GetMasterVolumeLevelScalar()
                new_vol = min(1.0, current_vol + 0.1)
                volume_int.SetMasterVolumeLevelScalar(new_vol, None)
                return True, "Turning volume up."
            elif direction == "down":
                current_vol = volume_int.GetMasterVolumeLevelScalar()
                new_vol = max(0.0, current_vol - 0.1)
                volume_int.SetMasterVolumeLevelScalar(new_vol, None)
                return True, "Turning volume down."
            elif level is not None:
                new_vol = max(0.0, min(1.0, float(level) / 100.0))
                volume_int.SetMasterVolumeLevelScalar(new_vol, None)
                return True, f"Setting volume to {int(level)} percent."
                
            return False, "Invalid volume command."
        except Exception as e:
            logger.error(f"Volume control failed: {e}")
            return False, "Failed to change volume."

    def set_mute(self, state):
        try:
            import pythoncom
            pythoncom.CoInitialize()
            volume_int = self.get_volume_interface()
            if not volume_int:
                return False, "Failed to access audio device."
                
            is_mute = 1 if state == "on" else 0
            volume_int.SetMute(is_mute, None)
            return True, "Muted." if is_mute else "Unmuted."
        except Exception as e:
            logger.error(f"Mute failed: {e}")
            return False, "Failed to change mute state."

    def set_brightness(self, level=None, direction=None):
        if sbc is None:
            return False, "Brightness control is not available."
            
        try:
            current_brightness = sbc.get_brightness(display=0)[0]
            if direction == "up":
                new_b = min(100, current_brightness + 10)
                sbc.set_brightness(new_b)
                return True, "Turning brightness up."
            elif direction == "down":
                new_b = max(0, current_brightness - 10)
                sbc.set_brightness(new_b)
                return True, "Turning brightness down."
            elif level is not None:
                new_b = max(0, min(100, int(level)))
                sbc.set_brightness(new_b)
                return True, f"Setting brightness to {new_b} percent."
                
            return False, "Invalid brightness command."
        except Exception as e:
            logger.error(f"Brightness control failed: {e}")
            return False, "Failed to adjust brightness (might not be supported on this monitor)."

    def get_system_info(self):
        try:
            cpu = int(psutil.cpu_percent(interval=0.5))
            mem = int(psutil.virtual_memory().percent)
            disk = psutil.disk_usage('C:\\')
            disk_free_gb = int(disk.free / (1024 ** 3))
            
            return True, f"You're at {cpu} percent CPU, {mem} percent memory, and have {disk_free_gb} gigabytes of free disk space."
        except Exception as e:
            logger.error(f"System info failed: {e}")
            return False, "Failed to retrieve system info."

    def power_action(self, action):
        try:
            if action == "lock":
                ctypes.windll.user32.LockWorkStation()
                return True, "Locking the screen."
            elif action == "sleep":
                # Sleep doesn't support a timeout natively via rundll32, so we'll just execute it
                os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
                return True, "Going to sleep."
            elif action == "restart":
                os.system("shutdown /r /t 10")
                return True, "Restarting in 10 seconds. Say cancel to stop."
            elif action == "shutdown":
                os.system("shutdown /s /t 10")
                return True, "Shutting down in 10 seconds. Say cancel to stop."
            elif action == "cancel":
                os.system("shutdown /a")
                return True, "Power operation cancelled."
                
            return False, "Unknown power action."
        except Exception as e:
            logger.error(f"Power action failed: {e}")
            return False, "Failed to execute power action."
