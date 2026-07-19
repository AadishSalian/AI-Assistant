import os
import threading
import webview
import time
import logging
from core.config_loader import load_config
from core.logger import setup_logger
from modules.wake_word.engine import WakeWordEngine
from modules.tts.piper_engine import TTSEngine
from modules.stt.whisper_engine import STTEngine
from core.gui_bridge import Api, start_stats_loop
from modules.intent.router import IntentRouter
from core.memory import MemoryBuffer
from modules.system.app_manager import AppManager
from modules.system.window_manager import WindowManager
from modules.system.screenshot_manager import ScreenshotManager

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
    
    ollama_config = config.get('ollama', {})
    intent_router = IntentRouter(
        ollama_host=ollama_config.get('host', 'http://localhost:11434'),
        model=ollama_config.get('model', 'llama3.2:3b')
    )
    
    memory = MemoryBuffer()
    app_manager = AppManager(config)
    window_manager = WindowManager(config)
    screenshot_manager = ScreenshotManager(config)
    
    user_name = config['assistant']['user_name']
    require_confirm = config.get('safety', {}).get('require_confirm', True)
    pending_action = None
    
    # Wait for the UI to fully render before pushing JavaScript events
    import time
    time.sleep(3)
    
    api.push_log("System initialized and ready.")
    
    try:
        while True:
            api.push_state('idle')
            if wakeword_engine.listen_for_wake_word():
                api.push_state('listening')
                api.push_log("Wake word detected")
                
                # Only greet if we don't have a pending action
                if not pending_action:
                    response_text = f"Hey {user_name}, welcome back boss"
                    api.push_transcript(response_text)
                    tts_engine.speak(response_text)
                else:
                    api.push_transcript("Listening for confirmation...")
                
                text = stt_engine.listen_and_transcribe(
                    timeout=stt_config.get('listen_timeout', 6),
                    phrase_time_limit=stt_config.get('phrase_limit', 15)
                )
                
                if text:
                    api.push_transcript(text)
                    logger.info(f"Captured Text: {text}")
                    api.push_log(f"User: {text}")
                    
                    api.push_state('thinking')
                    
                    # Phase 4: Route Intent
                    context = memory.get_context_string()
                    result = intent_router.route(text, context)
                    
                    intent_name = result.get('intent', 'unknown')
                    confidence = result.get('confidence', 0.0)
                    reply = result.get('conversational_reply', "Got it.")
                    params = result.get('parameters', {})
                    
                    # Handle Confirmation State
                    if pending_action:
                        if intent_name == 'system.confirm':
                            api.push_log("Executing confirmed action.")
                            tts_engine.speak("Executing, boss.")
                            pending_action()
                        else:
                            api.push_log("Action cancelled.")
                            tts_engine.speak("Action cancelled.")
                        pending_action = None
                        continue
                    
                    # Handle low confidence
                    if confidence < 0.60 or intent_name == 'unknown':
                        reply = "I'm not exactly sure what you mean, boss. Can you clarify?"
                        intent_name = "clarification_needed"
                        
                    logger.info(f"Resolved Intent: {intent_name} (Conf: {confidence}) | Params: {params}")
                    api.push_log(f"Intent: {intent_name}")
                    
                    # Save to memory
                    memory.add_exchange(text, reply, intent_name, params)
                    
                    # Phase 5 Execution
                    needs_confirm = False
                    
                    if intent_name == 'app.open':
                        success, msg = app_manager.launch_app(params.get('app_name', ''))
                        reply = msg if not success else reply
                        if success:
                            app_name = params.get('app_name', '').lower()
                            suggestion = window_manager.get_suggested_layout(app_name)
                            if suggestion:
                                needs_confirm = True
                                reply += f" Should I snap it to the {suggestion} for you?"
                                def execute_snap(s=suggestion):
                                    window_manager.position_window(s)
                                pending_action = execute_snap
                    elif intent_name == 'app.focus':
                        success, msg = app_manager.switch_app(params.get('app_name', ''))
                        reply = msg if not success else reply
                    elif intent_name == 'app.stats':
                        success, msg = app_manager.app_stats(params.get('app_name', ''))
                        reply = msg
                    elif intent_name == 'app.close':
                        batch = params.get('batch', False)
                        if batch and require_confirm:
                            needs_confirm = True
                            reply = "Are you sure you want to run a batch close operation?"
                            def execute_close():
                                app_manager.close_app(params.get('app_name', ''), batch, params.get('except_app'))
                            pending_action = execute_close
                        else:
                            success, msg = app_manager.close_app(params.get('app_name', ''), batch, params.get('except_app'))
                            reply = msg if not success else reply
                    elif intent_name == 'system.startup':
                        if require_confirm:
                            needs_confirm = True
                            reply = f"Are you sure you want to modify the registry for {params.get('app_name', '')}?"
                            def execute_startup():
                                success, msg = app_manager.manage_startup(params.get('action'), params.get('app_name'))
                                tts_engine.speak(msg)
                            pending_action = execute_startup
                        else:
                            success, msg = app_manager.manage_startup(params.get('action'), params.get('app_name'))
                            reply = msg
                    elif intent_name == 'window.position':
                        layout = params.get('layout', '')
                        target = params.get('target_window', 'current')
                        if target.lower() not in ['this', 'the', 'current', '']:
                            app_manager.switch_app(target)
                            time.sleep(0.5) # Give OS time to bring window to foreground
                        success, msg = window_manager.position_window(layout)
                        reply = msg
                    elif intent_name == 'window.monitor':
                        target = params.get('target_window', 'current')
                        if target.lower() not in ['this', 'the', 'current', '']:
                            app_manager.switch_app(target)
                            time.sleep(0.5)
                        success, msg = window_manager.move_to_monitor(params.get('monitor_index', 1))
                        reply = msg
                    elif intent_name == 'desktop.switch':
                        success, msg = window_manager.switch_desktop(params.get('target', 'next'))
                        reply = msg
                    elif intent_name == 'desktop.create':
                        success, msg = window_manager.create_desktop()
                        reply = msg
                    elif intent_name == 'screenshot.capture':
                        mode = params.get('mode', 'fullscreen')
                        target = params.get('target_window', 'current')
                        
                        if mode == 'window':
                            if target.lower() not in ['this', 'the', 'current', '']:
                                app_manager.switch_app(target)
                                time.sleep(0.5)
                            import win32gui
                            hwnd = win32gui.GetForegroundWindow()
                            success, msg = screenshot_manager.capture_window(hwnd)
                        elif mode == 'region':
                            tts_engine.speak("Select the region.")
                            success, msg = screenshot_manager.capture_region()
                        else:
                            success, msg = screenshot_manager.capture_fullscreen()
                        reply = msg
                    
                    # Speak the reply
                    api.push_transcript(reply)
                    tts_engine.speak(reply)
                    if needs_confirm:
                        api.push_log("Awaiting user confirmation...")
                        
                else:
                    api.push_transcript("")
                    logger.info("No speech detected.")
                    if pending_action:
                        pending_action = None
                        logger.info("Pending action timed out.")
                    
    except Exception as e:
        logger.error(f"Critical error in assistant loop: {e}")

def main():
    config = load_config("config/config.yaml")
    logger = setup_logger(config['assistant']['log_level'])
    
    # Silence harmless but scary pywebview/pythonnet COM initialization noise
    logging.getLogger('pywebview').setLevel(logging.CRITICAL)
    
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
