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
    
    # Piper TTS model (en_US-lessac-low)
    base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/low/"
    model_file = "en_US-lessac-low.onnx"
    config_file = "en_US-lessac-low.onnx.json"
    
    print("Setting up local assets...")
    download_file(base_url + model_file, f"assets/{model_file}")
    download_file(base_url + config_file, f"assets/{config_file}")
    print("\nSetup complete. You are ready to run main.py!")
