import logging
import os
import subprocess
import pyaudio

logger = logging.getLogger("sweetie.tts")

class TTSEngine:
    def __init__(self, voice_name="en_US-lessac-low", speed=1.0, sentence_silence=0.2):
        self.model_path = os.path.join("assets", f"{voice_name}.onnx")
        self.config_path = os.path.join("assets", f"{voice_name}.onnx.json")
        self.speed = speed
        self.sentence_silence = sentence_silence
        
        # Use the local Windows executable
        self.piper_exe = os.path.join("assets", "piper", "piper.exe")
        
        if not os.path.exists(self.piper_exe):
            logger.error(f"Piper executable not found at {self.piper_exe}.")
            self.ready = False
        elif not os.path.exists(self.model_path):
            logger.error(f"TTS Model not found at {self.model_path}. Run scripts/download_models.py")
            self.ready = False
        else:
            logger.info(f"TTS engine initialized with voice '{voice_name}' (Speed: {speed})")
            self.ready = True

    def speak(self, text):
        logger.info(f"Speaking: '{text}'")
        if not self.ready:
            logger.error("TTS engine not ready. Cannot speak.")
            return
            
        command = [
            self.piper_exe,
            "--model", self.model_path,
            "--config", self.config_path,
            "--length_scale", str(self.speed),
            "--sentence_silence", str(self.sentence_silence),
            "--output_raw"
        ]
        
        try:
            # Generate raw PCM audio
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            out, err = process.communicate(input=text.encode('utf-8'))
            
            if process.returncode != 0:
                logger.error(f"Piper process failed with return code {process.returncode}")
                return
                
            # Play the audio stream
            p = pyaudio.PyAudio()
            # Piper typically outputs 16kHz or 22050Hz based on the model.
            # Most low/medium models on huggingface are 16kHz or 22050Hz.
            # Note: A mismatch here causes chipmunk/slow audio. 
            # We are using 16kHz models here (lessac-low, ryan-low).
            stream = p.open(format=pyaudio.paInt16,
                            channels=1,
                            rate=16000,
                            output=True)
                            
            stream.write(out)
            stream.stop_stream()
            stream.close()
            p.terminate()
            
        except Exception as e:
            logger.error(f"Failed to play TTS: {e}")
