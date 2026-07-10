# modules/immich_controller.py
import os
import time
import threading
import random
from . import immich_handler
from . import display_control
from .settings_handler import read_settings

immich_running = False
IMMICH_DISPLAY_DURATION_RANDOM = 30
IMMICH_DISPLAY_DURATION_ALBUM = 30
IMMICH_DISPLAY_DURATION_SEARCH = 30
DEVICE_ID = read_settings().get("deviceID", "pixel_display_rpi")
mqtt_publish_callback = None
_current_source_type = "random"
_current_album_id = None
_current_search_query = None

def set_mqtt_publish_callback(callback):
    global mqtt_publish_callback
    mqtt_publish_callback = callback

def _fetch_with_backoff(fetch_func, *args, **kwargs):
    delay = 10
    max_delay = 300
    while immich_running:
        try:
            return fetch_func(*args, **kwargs)
        except Exception as e:
            print(f"Fetch failed: {e}. Retrying in {delay}s...")
            time.sleep(delay)
            delay = min(delay * 2, max_delay)
    return None

def immich_display_loop():
    global immich_running, _current_source_type, _current_album_id, _current_search_query
    while immich_running:
        asset_id = None
        
        if _current_source_type == "random":
            asset_id = _fetch_with_backoff(immich_handler.fetch_random_asset)
            display_duration = IMMICH_DISPLAY_DURATION_RANDOM
        elif _current_source_type == "album":
            asset_id = _fetch_with_backoff(immich_handler.fetch_assets_by_album, _current_album_id)
            display_duration = IMMICH_DISPLAY_DURATION_ALBUM
        elif _current_source_type == "search":
            asset_urls = _fetch_with_backoff(immich_handler.search_assets, _current_search_query)
            if asset_urls:
                # Extract asset_id from URL
                asset_id = asset_urls[0].split("/")[-2] if asset_urls else None
            display_duration = IMMICH_DISPLAY_DURATION_SEARCH
        
        if asset_id:
            local_path = immich_handler.download_asset(asset_id)
            if local_path:
                filename = os.path.basename(local_path)
                print(f"Displaying Immich ({_current_source_type}): {filename}")
                display_control.process_image_async(filename, "displayImage", "static/immich_cache")
                time.sleep(display_duration + 5)
                if os.path.exists(local_path):
                    os.remove(local_path)
            else:
                print("Failed to download Immich asset.")
        else:
            print(f"Failed to fetch Immich ({_current_source_type}).")
        
        if immich_running:
            time.sleep(10)
    
    print("Immich display loop stopped.")

def start_immich_loop(source_type, album_id=None, search_query=None):
    global immich_running, IMMICH_DISPLAY_DURATION_RANDOM, IMMICH_DISPLAY_DURATION_ALBUM, IMMICH_DISPLAY_DURATION_SEARCH
    global _current_source_type, _current_album_id, _current_search_query
    
    settings = read_settings()
    IMMICH_DISPLAY_DURATION_RANDOM = int(settings.get("immichDisplayDurationRandom", 30))
    IMMICH_DISPLAY_DURATION_ALBUM = int(settings.get("immichDisplayDurationAlbum", 30))
    IMMICH_DISPLAY_DURATION_SEARCH = int(settings.get("immichDisplayDurationSearch", 30))
    
    print(f"Immich loop started (Source: {source_type})")
    _current_source_type = source_type
    _current_album_id = album_id
    _current_search_query = search_query
    
    if not immich_running:
        print("Starting Immich display loop.")
        immich_running = True
        immich_thread = threading.Thread(target=immich_display_loop)
        immich_thread.daemon = True
        immich_thread.start()
        if mqtt_publish_callback:
            mqtt_publish_callback(f"switch/{DEVICE_ID}/immich_control/state", "on", retain=True)
    else:
        print("Immich display loop is already running.")

def stop_immich_loop():
    global immich_running, mqtt_publish_callback, _current_source_type, _current_album_id, _current_search_query
    print("Stopping Immich display loop.")
    _current_source_type = "random"
    _current_album_id = None
    _current_search_query = None
    if immich_running:
        immich_running = False
        if mqtt_publish_callback:
            mqtt_publish_callback(f"switch/{DEVICE_ID}/immich_control/state", "off", retain=True)
    else:
        print("Immich display loop is not running.")
