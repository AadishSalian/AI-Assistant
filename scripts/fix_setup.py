import urllib.request
import zipfile
import os
import subprocess
import sys

def main():
    print("--- Fixing pip dependencies ---")
    # Run pip install with higher timeout
    pip_cmd = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--default-timeout=100"]
    subprocess.run(pip_cmd)

    print("\n--- Downloading Piper Executable ---")
    url = "https://github.com/rhasspy/piper/releases/latest/download/piper_windows_amd64.zip"
    zip_path = "piper_windows_amd64.zip"
    
    os.makedirs("assets", exist_ok=True)
    
    try:
        urllib.request.urlretrieve(url, zip_path)
        print("Extracting Piper...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall("assets")
        os.remove(zip_path)
        print("Piper setup complete!")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error using 'latest': {e}")
        # Fallback to a hardcoded stable release tag
        url_fallback = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"
        print(f"Trying fallback URL: {url_fallback}")
        try:
            urllib.request.urlretrieve(url_fallback, zip_path)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall("assets")
            os.remove(zip_path)
            print("Piper setup complete via fallback!")
        except Exception as e2:
            print(f"Fallback failed: {e2}")
    except Exception as e:
        print(f"Failed to download/extract Piper: {e}")

if __name__ == "__main__":
    main()
