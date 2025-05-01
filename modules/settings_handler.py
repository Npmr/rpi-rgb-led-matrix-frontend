# modules/settings_handler.py
import json

def read_settings(filename="settings.json"):
    try:
        with open(filename, 'r') as f:
            settings = json.load(f)
        return settings
    except FileNotFoundError:
        print(f"Error: {filename} not found.")
        return {}
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {filename}.")
        return {}

def save_settings(new_settings, filename="settings.json"):
    try:
        with open(filename, 'w') as f:
            json.dump(new_settings, f, indent=4)
        return True
    except IOError:
        print(f"Error: Could not write to {filename}.")
        return False