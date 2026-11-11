# modules/giphy_controller.py
"""Giphy slideshow loop.

The loop runs in its own daemon thread and displays a new GIF every
``GIPHY_DISPLAY_DURATION`` seconds. Stopping must take effect immediately, so
all waits go through a ``threading.Event`` instead of ``time.sleep``: setting
the event wakes the thread instead of letting it finish a five minute nap.
"""
import os
import threading

import requests

from . import giphy_handler
from . import display_control
from .settings_handler import read_settings

giphy_running = False
GIPHY_DISPLAY_DURATION = 300  # 5 minutes in seconds
DEVICE_ID = read_settings().get("deviceID", "pixel_display_rpi")
mqtt_publish_callback = None  # Placeholder for the callback function

# Set by stop_giphy_loop(), cleared again whenever the loop starts. A waiting
# loop wakes up as soon as it is set.
_stop_event = threading.Event()
_giphy_thread = None
# Incremented on every start so an old thread cannot keep a new run alive.
_loop_generation = 0

_current_search_term = None

# Retry configuration
GIPHY_RETRY_INITIAL_DELAY = 10  # seconds
GIPHY_RETRY_MAX_DELAY = 300  # 5 minutes
GIPHY_RETRY_MULTIPLIER = 2


def set_mqtt_publish_callback(callback):
    global mqtt_publish_callback
    mqtt_publish_callback = callback


# API key takes precedence from the environment, then falls back to settings.json.
def _giphy_api_key():
    return os.environ.get("GIPHY_API_KEY") or read_settings().get("giphyApiKey", "")


def _giphy_categories_url():
    """Build the categories URL at request time so env-var key changes are honored."""
    params = {"api_key": _giphy_api_key()}
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"https://api.giphy.com/v1/gifs/categories?{query}"


def _fetch_giphy_data(url):
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.json().get('data', [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Giphy data: {e}")
        return []


def get_art_design_subcategories():
    try:
        response = requests.get(_giphy_categories_url(), timeout=15)
        response.raise_for_status()
        categories_data = response.json().get('data', [])
        for category in categories_data:
            if category['name'] == 'Art & Design':
                return category['subcategories']
        return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Giphy categories: {e}")
        return []


def _wait(seconds):
    """Sleep, but return True immediately when the loop is stopped."""
    return _stop_event.wait(seconds)


def _remove_quietly(path):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError as error:
            print(f"Could not remove {path}: {error}")


def _fetch_with_backoff(fetch_func, *args, **kwargs):
    """Fetch with exponential backoff retry logic, aborting on stop."""
    delay = GIPHY_RETRY_INITIAL_DELAY
    max_delay = GIPHY_RETRY_MAX_DELAY
    multiplier = GIPHY_RETRY_MULTIPLIER

    while giphy_running:
        try:
            return fetch_func(*args, **kwargs)
        except Exception as e:
            print(f"Giphy fetch failed: {e}. Retrying in {delay}s...")
            if _wait(delay):
                return None
            delay = min(delay * multiplier, max_delay)
    return None


def loop_thread_is_current():
    """True when called from inside the Giphy loop thread."""
    return _giphy_thread is not None and threading.current_thread() is _giphy_thread


def giphy_display_loop(generation=None):
    """Show one Giphy at a time until the loop is stopped."""
    global giphy_running, _current_search_term

    def running():
        if generation is None:
            return giphy_running
        return giphy_running and generation == _loop_generation

    while running():
        if _current_search_term:
            gif_url = _fetch_with_backoff(giphy_handler.fetch_searched_gif,
                                          _current_search_term)
        else:
            gif_url = _fetch_with_backoff(giphy_handler.fetch_trending_gif)

        # The fetch may take a while; do not show anything after a stop.
        if not running():
            break

        if not gif_url:
            print(f"Failed to fetch Giphy (Category: "
                  f"{_current_search_term if _current_search_term else 'trending'}).")
            if _wait(10):
                break
            continue

        local_path = giphy_handler.download_gif(gif_url)
        if not running():
            _remove_quietly(local_path)
            break

        if not local_path:
            print("Failed to download Giphy.")
            if _wait(10):
                break
            continue

        filename = os.path.basename(local_path)
        print(f"Displaying Giphy: {filename} "
              f"(Category: {_current_search_term if _current_search_term else 'trending'})")
        display_control.process_image_async(filename, "displayImage",
                                            "static/giphy_cache")
        stopped = _wait(GIPHY_DISPLAY_DURATION + 5)
        _remove_quietly(local_path)
        if stopped:
            break
        if _wait(10):
            break

    print("Giphy display loop stopped.")


def start_giphy_loop(search_term=None):
    global giphy_running, mqtt_publish_callback, _current_search_term
    global _giphy_thread, _loop_generation
    print(f"Giphy loop started (Category: {search_term if search_term else 'trending'})")
    _current_search_term = search_term
    if not giphy_running:
        print("Starting Giphy display loop.")
        giphy_running = True
        _stop_event.clear()
        _loop_generation += 1
        _giphy_thread = threading.Thread(target=giphy_display_loop,
                                         args=(_loop_generation,))
        _giphy_thread.daemon = True
        _giphy_thread.start()
        if mqtt_publish_callback:
            mqtt_publish_callback(f"switch/{DEVICE_ID}/giphy_control/state", "on", retain=True)
    else:
        print("Giphy display loop is already running.")


def stop_giphy_loop():
    """Stop the loop now. Returns True when a loop was actually running."""
    global giphy_running, mqtt_publish_callback, _current_search_term
    was_running = giphy_running
    giphy_running = False
    _current_search_term = None
    _stop_event.set()
    if was_running:
        print("Stopping Giphy display loop.")
        if mqtt_publish_callback:
            mqtt_publish_callback(f"switch/{DEVICE_ID}/giphy_control/state", "off", retain=True)
    else:
        print("Giphy display loop is not running.")
    return was_running
