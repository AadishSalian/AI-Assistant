import os
from core.config_loader import load_config
from core.logger import setup_logger
from modules.wake_word.engine import WakeWordEngine
from modules.tts.piper_engine import TTSEngine

def main():
    # Load config and setup logging
    config = load_config("config/config.yaml")
    logger = setup_logger(config['assistant']['log_level'])
    
    logger.info("Initializing Sweetie Assistant...")
    
    # Initialize TTS First (so it's ready when wake word triggers)
    tts_engine = TTSEngine(
        model_path=config['tts']['model_path'],
        config_path=config['tts']['config_path']
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
                
    except KeyboardInterrupt:
        logger.info("Shutting down assistant...")
    except Exception as e:
        logger.error(f"Critical error: {e}")

if __name__ == "__main__":
    main()
