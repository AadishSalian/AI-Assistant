import os
import urllib.request

def download_file(url, filepath):
    if not os.path.exists(filepath):
        print(f"Downloading {filepath}...")
        urllib.request.urlretrieve(url, filepath)
        print(f"Done downloading {filepath}.")
    else:
        print(f"{filepath} already exists.")

if __name__ == "__main__":
    # Ensure assets directory exists
    os.makedirs("assets", exist_ok=True)
    
    voices = [
        {
            "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/low/",
            "name": "en_US-lessac-low"
        },
        {
            "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/low/",
            "name": "en_US-ryan-low"
        }
    ]
    
    print("Setting up local TTS voice models...")
    for voice in voices:
        model_file = f"{voice['name']}.onnx"
        config_file = f"{voice['name']}.onnx.json"
        
        download_file(voice['url'] + model_file, f"assets/{model_file}")
        download_file(voice['url'] + config_file, f"assets/{config_file}")
        
    print("\nVoice setup complete.")
