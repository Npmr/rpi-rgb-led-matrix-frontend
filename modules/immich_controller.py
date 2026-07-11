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
# Album asset caching for sequential playback
_album_assets_cache = []
_album_asset_index = 0
_album_assets_fetched = False

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
    global _album_assets_cache, _album_asset_index, _album_assets_fetched
    while immich_running:
        asset_id = None
        
        if _current_source_type == "random":
            asset_url = _fetch_with_backoff(immich_handler.fetch_random_asset)
            if asset_url:
                asset_id = asset_url.split("/")[-2]
            display_duration = IMMICH_DISPLAY_DURATION_RANDOM
        elif _current_source_type == "album":
            # For album mode, fetch all assets on first run, then cycle through them
            if not _album_assets_fetched or not _album_assets_cache:
                print(f"Fetching all assets for album {_current_album_id}...")
                _album_assets_cache = _fetch_with_backoff(immich_handler.fetch_all_album_assets, _current_album_id) or []
                _album_asset_index = 0
                _album_assets_fetched = True
                if not _album_assets_cache:
                    print(f"No assets found in album {_current_album_id}")
                    time.sleep(30)
                    continue
            
            # Get next asset from cache
            if _album_asset_index < len(_album_assets_cache):
                asset_id = _album_assets_cache[_album_asset_index]
                _album_asset_index += 1
            else:
                # We've shown all assets, refetch for any new additions
                print("All album assets shown, refetching...")
                _album_assets_fetched = False
                time.sleep(5)
                continue
            
            display_duration = IMMICH_DISPLAY_DURATION_ALBUM
        elif _current_source_type == "search":
            asset_urls = _fetch_with_backoff(immich_handler.search_assets, _current_search_query)
            if asset_urls:
                asset_id = asset_urls[0].split("/")[-2]
            display_duration = IMMICH_DISPLAY_DURATION_SEARCH
        
        exif_orientation = None
        if asset_id:
            # Fetch asset info to get EXIF orientation
            settings = read_settings()
            if settings.get("immichAutoOrientation", "true").lower() == "true":
                asset_info = immich_handler.get_asset_info(asset_id)
                if asset_info:
                    exif_orientation = asset_info.get("orientation")
                    print(f"Immich asset {asset_id} EXIF orientation: {exif_orientation}")
            
            local_path = immich_handler.download_asset(asset_id)
            if local_path:
                filename = os.path.basename(local_path)
                print(f"Displaying Immich ({_current_source_type}): {filename}")
                # Pass exif_orientation to display control
                display_control.process_image_async(filename, "displayImage", "static/immich_cache", exif_orientation=exif_orientation)
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
    global _album_assets_cache, _album_asset_index, _album_assets_fetched
    
    settings = read_settings()
    IMMICH_DISPLAY_DURATION_RANDOM = int(settings.get("immichDisplayDurationRandom", 30))
    IMMICH_DISPLAY_DURATION_ALBUM = int(settings.get("immichDisplayDurationAlbum", 30))
    IMMICH_DISPLAY_DURATION_SEARCH = int(settings.get("immichDisplayDurationSearch", 30))
    
    print(f"Immich loop started (Source: {source_type})")
    _current_source_type = source_type
    _current_album_id = album_id
    _current_search_query = search_query
    
    # Reset album cache when starting album mode
    if source_type == "album":
        _album_assets_cache = []
        _album_asset_index = 0
        _album_assets_fetched = False
    
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
