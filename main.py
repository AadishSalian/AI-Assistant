import os
import threading
import webview
import time
from core.config_loader import load_config
from core.logger import setup_logger
from modules.wake_word.engine import WakeWordEngine
from modules.tts.piper_engine import TTSEngine
from modules.stt.whisper_engine import STTEngine
from core.gui_bridge import Api, start_stats_loop

def assistant_loop(config, logger, api):
    logger.info("Initializing Sweetie Assistant Models...")
    
    tts_config = config.get('tts', {})
    tts_engine = TTSEngine(
        voice_name=tts_config.get('voice', 'en_US-lessac-low'),
        speed=tts_config.get('speed', 1.0),
        sentence_silence=tts_config.get('sentence_silence', 0.2)
    )
    
    stt_config = config.get('stt', {})
    stt_engine = STTEngine(
        model_size=stt_config.get('model_size', 'small'),
        compute_type=stt_config.get('compute_type', 'int8')
    )
    
    wakeword_engine = WakeWordEngine(
        model_path_or_name=config['wake_word']['phrase'], 
        threshold=config['wake_word']['threshold']
    )
    
    user_name = config['assistant']['user_name']
    
    # Wait briefly for GUI to render
    time.sleep(1.5)
    api.push_log("System initialized and ready.")
    
    try:
        while True:
            api.push_state('idle')
            if wakeword_engine.listen_for_wake_word():
                api.push_state('listening')
                api.push_log("Wake word detected")
                
                response_text = f"Hey {user_name}, welcome back boss"
                api.push_transcript(response_text)
                tts_engine.speak(response_text)
                
                text = stt_engine.listen_and_transcribe(
                    timeout=stt_config.get('listen_timeout', 6),
                    phrase_time_limit=stt_config.get('phrase_limit', 15)
                )
                
                if text:
                    api.push_transcript(text)
                    logger.info(f"Captured Text: {text}")
                    api.push_log(f"User: {text}")
                    
                    api.push_state('thinking')
                    tts_engine.speak("On it, boss.")
                    api.push_log("Action acknowledged.")
                else:
                    api.push_transcript("")
                    logger.info("No speech detected.")
                    
    except Exception as e:
        logger.error(f"Critical error in assistant loop: {e}")

def main():
    config = load_config("config/config.yaml")
    logger = setup_logger(config['assistant']['log_level'])
    
    api = Api()
    
    # Run the assistant core in a background thread
    assistant_thread = threading.Thread(target=assistant_loop, args=(config, logger, api), daemon=True)
    assistant_thread.start()
    
    # Start stats polling thread for the dashboard
    stats_thread = threading.Thread(target=start_stats_loop, args=(api,), daemon=True)
    stats_thread.start()
    
    gui_config = config.get('gui', {})
    width = gui_config.get('dock_width', 320)
    height = gui_config.get('dock_height', 140)
    
    # Create the webview window
    window = webview.create_window(
        'Sweetie',
        url='ui/index.html',
        js_api=api,
        width=width,
        height=height,
        frameless=True,
        easy_drag=False, # We use the CSS drag region instead
        on_top=True,
        transparent=False, # Disabled to prevent pythonnet recursion crash on Windows
        background_color='#0A0A0B'
    )
    
    api.set_window(window)
    
    # Start the GUI event loop on the main thread (blocks until window is closed)
    webview.start()

if __name__ == "__main__":
    main()
