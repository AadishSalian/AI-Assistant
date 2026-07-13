import webview
import psutil
import time
import logging

logger = logging.getLogger("sweetie.gui")

class Api:
    def __init__(self):
        self.window = None

    def set_window(self, window):
        self.window = window

    def resize_window(self, mode):
        # mode is 'dock' or 'dashboard'
        if not self.window: return
        if mode == 'dock':
            self.window.resize(320, 140)
        else:
            self.window.resize(400, 600)

    def trigger_action(self, action_name):
        logger.info(f"UI Action Triggered: {action_name}")
        # Phase 5-9: wire this to real commands

    # --- Methods to push to UI ---
    
    def push_state(self, state_name, message=""):
        if self.window:
            self.window.evaluate_js(f"setState('{state_name}', '{message}')")
            
    def push_transcript(self, text):
        if self.window:
            safe_text = text.replace('\\', '\\\\').replace("'", "\\'")
            self.window.evaluate_js(f"updateTranscript('{safe_text}')")
            
    def push_log(self, text):
        if self.window:
            safe_text = text.replace('\\', '\\\\').replace("'", "\\'")
            self.window.evaluate_js(f"addLogEntry('{safe_text}')")

def start_stats_loop(api):
    while True:
        try:
            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent
            
            if api.window:
                api.window.evaluate_js(f"updateStats({cpu}, {mem}, {disk})")
        except Exception as e:
            logger.error(f"Stats error: {e}")
            time.sleep(2)
