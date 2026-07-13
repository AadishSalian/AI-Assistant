import yaml
import os

def load_config(filepath="config/config.yaml"):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Config file not found at {filepath}")
    
    with open(filepath, 'r') as f:
        return yaml.safe_load(f)
