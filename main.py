import os
from core.config_loader import load_config
from core.logger import setup_logger
from modules.wake_word.engine import WakeWordEngine
from modules.tts.piper_engine import TTSEngine
from modules.stt.whisper_engine import STTEngine

def main():
    # Load config and setup logging
    config = load_config("config/config.yaml")
    logger = setup_logger(config['assistant']['log_level'])
    
    logger.info("Initializing Sweetie Assistant...")
    
    # Initialize TTS First
    tts_config = config.get('tts', {})
    tts_engine = TTSEngine(
        voice_name=tts_config.get('voice', 'en_US-lessac-low'),
        speed=tts_config.get('speed', 1.0),
        sentence_silence=tts_config.get('sentence_silence', 0.2)
    )
    
    # Initialize STT Engine
    stt_config = config.get('stt', {})
    stt_engine = STTEngine(
        model_size=stt_config.get('model_size', 'small'),
        compute_type=stt_config.get('compute_type', 'int8')
    )
    
    # Initialize Wake Word Listener
    wakeword_engine = WakeWordEngine(
        model_path_or_name=config['wake_word']['phrase'], 
        threshold=config['wake_word']['threshold']
    )
    
    user_name = config['assistant']['user_name']
    
    try:
        # Main continuous loop
        while True:
            # Blocks until wake word is detected
            if wakeword_engine.listen_for_wake_word():
                response_text = f"Hey {user_name}, welcome back boss"
                tts_engine.speak(response_text)
                
                # After speaking, listen for user command
                text = stt_engine.listen_and_transcribe(
                    timeout=stt_config.get('listen_timeout', 6),
                    phrase_time_limit=stt_config.get('phrase_limit', 15)
                )
                
                if text:
                    logger.info(f"Captured Text: {text}")
                    # Phase 3: Acknowledge the command
                    tts_engine.speak("On it, boss.")
                    
                    # Phase 4 will handle intent parsing here
                else:
                    logger.info("No speech detected or transcription failed.")
                
    except KeyboardInterrupt:
        logger.info("Shutting down assistant...")
    except Exception as e:
        logger.error(f"Critical error: {e}")

if __name__ == "__main__":
    main()
