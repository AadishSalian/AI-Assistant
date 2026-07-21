import webview
import psutil
import time
import logging

logger = logging.getLogger("sweetie.gui")

class Api:
    def __init__(self):
        self.window = None
        self.is_ready = False

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
        if self.window and self.is_ready:
            try:
                self.window.evaluate_js(f"setState('{state_name}', '{message}')")
            except Exception: pass
            
    def push_transcript(self, text):
        if self.window and self.is_ready:
            safe_text = text.replace('\\', '\\\\').replace("'", "\\'")
            try:
                self.window.evaluate_js(f"updateTranscript('{safe_text}')")
            except Exception: pass
            
    def push_log(self, text):
        if self.window and self.is_ready:
            safe_text = text.replace('\\', '\\\\').replace("'", "\\'")
            try:
                self.window.evaluate_js(f"addLogEntry('{safe_text}')")
            except Exception: pass

def start_stats_loop(api):
    while True:
        try:
            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent
            
            if api.window and api.is_ready:
                api.window.evaluate_js(f"updateStats({cpu}, {mem}, {disk})")
        except Exception:
            pass
        time.sleep(2)
