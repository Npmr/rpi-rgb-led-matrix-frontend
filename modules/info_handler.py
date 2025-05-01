# modules/info_handler.py
import json

def read_infos(filename="info.json"):
    try:
        with open(filename, 'r') as f:
            app_info = json.load(f)
        return app_info
    except FileNotFoundError:
        print(f"Error: {filename} not found.")
        return {}
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {filename}.")
        return {}