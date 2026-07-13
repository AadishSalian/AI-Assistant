import logging
import numpy as np
from faster_whisper import WhisperModel
import speech_recognition as sr

logger = logging.getLogger("sweetie.stt")

class STTEngine:
    def __init__(self, model_size="small", compute_type="int8"):
        logger.info(f"Loading faster-whisper model '{model_size}' (compute_type={compute_type})")
        # Run exclusively on CPU, heavily quantized for i5 performance
        self.model = WhisperModel(model_size, device="cpu", compute_type=compute_type)
        
        self.recognizer = sr.Recognizer()
        # Dynamically adjust to ambient noise
        self.recognizer.dynamic_energy_threshold = True
        # Amount of silence in seconds that means the user stopped speaking
        self.recognizer.pause_threshold = 1.2 
        
        logger.info("STT engine initialized successfully.")

    def listen_and_transcribe(self, timeout=6, phrase_time_limit=15):
        logger.info("Listening for command...")
        
        with sr.Microphone() as source:
            try:
                # Capture audio using VAD (Voice Activity Detection) built into SpeechRecognition
                audio_data = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            except sr.WaitTimeoutError:
                logger.warning("Listening timed out. No speech detected.")
                return ""
            except Exception as e:
                logger.error(f"Error capturing audio: {e}")
                return ""
            
        logger.info("Audio captured, transcribing...")
        
        try:
            # Convert sr.AudioData (16-bit PCM WAV) to numpy float32 array normalized between -1.0 and 1.0
            raw_data = audio_data.get_raw_data(convert_rate=16000, convert_width=2)
            audio_np = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Transcribe with faster-whisper
            segments, info = self.model.transcribe(audio_np, beam_size=1, language="en")
            
            # segments is a generator, so we iterate to get all text
            text = " ".join([segment.text for segment in segments]).strip()
            
            if text:
                logger.info(f"Transcribed Text: '{text}'")
            else:
                logger.info("Transcription yielded empty text (likely background noise).")
                
            return text
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ""
