# modules/update_handler.py
import os
import subprocess
import threading

import requests

from .info_handler import read_infos # Import from the same module directory

# Guards against starting two updates at once (double click, two browsers).
_update_lock = threading.Lock()
_update_running = False


def update_script_path():
    """Absolute path of ``update_application.sh`` in the project root."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "update_application.sh",
    )


def is_update_running():
    """True while the update script is being executed."""
    return _update_running


def trigger_update(branch="main"):
    """Run the update script (blocking) and return a status message."""
    global _update_running
    with _update_lock:
        if _update_running:
            return "Update already running"
        _update_running = True
    try:
        subprocess.run(['sh', update_script_path(), branch])
    finally:
        with _update_lock:
            _update_running = False
    return "Update triggered successfully!"


def fetch_update_info(branch="main"):
    uri = f"https://raw.githubusercontent.com/Npmr/rpi-rgb-led-matrix-frontend/refs/heads/{branch}/info.json"
    try:
        uResponse = requests.get(uri, timeout=10)
        uResponse.raise_for_status()  # Raise an exception for bad status codes
        return uResponse.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching update info: {e}")
        return None
