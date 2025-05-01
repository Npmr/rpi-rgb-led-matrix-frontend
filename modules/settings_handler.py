# modules/settings_handler.py
import json
import os

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
        # Get the directory of the current script (settings_handler.py)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up one level to the project root
        project_root = os.path.dirname(script_dir)
        # Construct the full path to settings.json
        filepath = os.path.join(project_root, filename)
        with open(filepath, 'w') as f:
            json.dump(new_settings, f, indent=4)
        return True
    except IOError as e:
        print(f"Error: Could not write to {filepath}: {e}")
        return False