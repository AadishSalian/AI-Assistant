import pyaudio
import numpy as np
import openwakeword
from openwakeword.model import Model
import logging

logger = logging.getLogger("sweetie.wakeword")

class WakeWordEngine:
    def __init__(self, model_path_or_name, threshold=0.5):
        self.model_name = model_path_or_name
        self.threshold = threshold
        
        logger.info(f"Loading openWakeWord model: {self.model_name}")
        
        # Download pre-trained models if they are missing
        try:
            openwakeword.utils.download_models()
        except Exception as e:
            logger.warning(f"Could not download models (might already exist): {e}")
            
        self.oww_model = Model(wakeword_models=[self.model_name], inference_framework="onnx")
        
        # Standard properties for openWakeWord audio
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000
        self.CHUNK = 1280
        
        self.audio = pyaudio.PyAudio()
        logger.info("Wake word engine initialized successfully.")

    def listen_for_wake_word(self):
        logger.info("Listening for wake word...")
        mic_stream = self.audio.open(format=self.FORMAT, 
                                     channels=self.CHANNELS,
                                     rate=self.RATE, 
                                     input=True, 
                                     frames_per_buffer=self.CHUNK)
        try:
            while True:
                # Read audio data from mic
                audio_data = np.frombuffer(mic_stream.read(self.CHUNK, exception_on_overflow=False), dtype=np.int16)
                
                # Get prediction
                prediction = self.oww_model.predict(audio_data)
                
                # Check scores
                for mdl, score in prediction.items():
                    if score >= self.threshold:
                        logger.info(f"Wake word detected! (Score: {score:.2f})")
                        # Clear internal buffer to prevent repeated immediate triggering
                        self.oww_model.reset()
                        return True
        finally:
            mic_stream.stop_stream()
            mic_stream.close()
