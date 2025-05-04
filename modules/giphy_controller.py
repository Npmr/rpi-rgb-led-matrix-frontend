# modules/giphy_controller.py
import time
import threading
import random
import requests
import os
from . import giphy_handler
from . import display_control
from .settings_handler import read_settings

giphy_running = False
GIPHY_DISPLAY_DURATION = 300  # 5 minutes in seconds
DEVICE_ID = read_settings().get("deviceID", "pixel_display_rpi")
mqtt_publish_callback = None  # Placeholder for the callback function

GIPHY_API_KEY = read_settings().get("giphyApiKey")
TRENDING_URL = f"https://api.giphy.com/v1/gifs/trending?api_key={GIPHY_API_KEY}&limit=25"
SEARCH_URL = f"https://api.giphy.com/v1/gifs/search?api_key={GIPHY_API_KEY}&limit=25&q="
CATEGORIES_URL = f"https://api.giphy.com/v1/gifs/categories?api_key={GIPHY_API_KEY}"

_current_search_term = None

def set_mqtt_publish_callback(callback):
    global mqtt_publish_callback
    mqtt_publish_callback = callback

def _fetch_giphy_data(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json().get('data', [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Giphy data: {e}")
        return []

def get_art_design_subcategories():
    try:
        response = requests.get(CATEGORIES_URL)
        response.raise_for_status()
        categories_data = response.json().get('data', [])
        for category in categories_data:
            if category['name'] == 'Art & Design':
                return category['subcategories']
        return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Giphy categories: {e}")
        return []

def giphy_display_loop():
    global giphy_running, _current_search_term
    while giphy_running:
        if _current_search_term:
            gif_url = giphy_handler.fetch_searched_gif(_current_search_term) # Assuming you have this in giphy_handler
        else:
            gif_url = giphy_handler.fetch_trending_gif()

        if gif_url:
            local_path = giphy_handler.download_gif(gif_url)
            if local_path:
                filename = os.path.basename(local_path)
                print(f"Displaying Giphy: {filename} (Category: {_current_search_term if _current_search_term else 'trending'})")
                display_control.process_image_async(filename, "displayImage", "static/giphy_cache")
                time.sleep(GIPHY_DISPLAY_DURATION + 5)  # Wait for display + a small buffer
                if os.path.exists(local_path):
                    os.remove(local_path)  # Clean up
            else:
                print("Failed to download Giphy.")
        else:
            print(f"Failed to fetch Giphy (Category: {_current_search_term if _current_search_term else 'trending'}).")

        if giphy_running:
            time.sleep(10)  # Wait before fetching the next one
    print("Giphy display loop stopped.")

def start_giphy_loop(search_term=None):
    global giphy_running, mqtt_publish_callback, _current_search_term
    print(f"Giphy loop started (Category: {search_term if search_term else 'trending'})")
    _current_search_term = search_term
    if not giphy_running:
        print("Starting Giphy display loop.")
        giphy_running = True
        giphy_thread = threading.Thread(target=giphy_display_loop)
        giphy_thread.daemon = True
        giphy_thread.start()
        if mqtt_publish_callback:
            mqtt_publish_callback(f"switch/{DEVICE_ID}/giphy_control/state", "on", retain=True)
    else:
        print("Giphy display loop is already running.")

def stop_giphy_loop():
    global giphy_running, mqtt_publish_callback, _current_search_term
    print("Stopping Giphy display loop.")
    _current_search_term = None
    if giphy_running:
        giphy_running = False
        if mqtt_publish_callback:
            mqtt_publish_callback(f"switch/{DEVICE_ID}/giphy_control/state", "off", retain=True)
    else:
        print("Giphy display loop is not running.")