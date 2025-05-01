# modules/update_handler.py
import subprocess
import requests
import json
from .info_handler import read_infos # Import from the same module directory

def trigger_update():
    subprocess.run(['sh', 'update_application.sh'])
    return "Update triggered successfully!"

def fetch_update_info(uri="https://raw.githubusercontent.com/Npmr/rpi-rgb-led-matrix-frontend/refs/heads/main/info.json"):
    try:
        uResponse = requests.get(uri)
        uResponse.raise_for_status()  # Raise an exception for bad status codes
        return uResponse.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching update info: {e}")
        return None