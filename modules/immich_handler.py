# modules/immich_handler.py
import requests
import os
import time
import random
from .settings_handler import read_settings

settings = read_settings()
IMMICH_API_KEY = settings.get("immichApiKey", "")
IMMICH_URL = settings.get("immichUrl", "").rstrip("/")
DOWNLOAD_PATH = "static/immich_cache"

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)


def _get_headers():
    return {
        "Accept": "application/json",
        "x-api-key": IMMICH_API_KEY
    }


def _check_config():
    if not IMMICH_API_KEY:
        print("Error: Immich API key not configured")
        return False
    if not IMMICH_URL:
        print("Error: Immich URL not configured")
        return False
    return True


def fetch_random_asset():
    if not _check_config():
        return None
    try:
        url = f"{IMMICH_URL}/api/asset/random"
        params = {"count": 50}
        response = requests.get(url, headers=_get_headers(), params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        if data and isinstance(data, list) and len(data) > 0:
            asset = random.choice(data)
            asset_id = asset.get("id")
            if asset_id:
                return f"{IMMICH_URL}/api/asset/file/{asset_id}"
        print("Error: No random assets found in Immich response")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching random asset from Immich: {e}")
        return None


def fetch_assets_by_album(album_id):
    if not _check_config():
        return None
    try:
        url = f"{IMMICH_URL}/api/album/{album_id}"
        response = requests.get(url, headers=_get_headers(), timeout=30)
        response.raise_for_status()
        album = response.json()
        assets = album.get("assets", [])
        if assets:
            asset = random.choice(assets)
            asset_id = asset.get("id")
            if asset_id:
                return f"{IMMICH_URL}/api/asset/file/{asset_id}"
        print(f"Error: No assets found in album {album_id}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching album assets from Immich: {e}")
        return None


def search_assets(query="", size=50):
    if not _check_config():
        return []
    try:
        url = f"{IMMICH_URL}/api/search/metadata"
        payload = {
            "query": query,
            "size": size,
            "withExif": False
        }
        response = requests.post(url, headers=_get_headers(), json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        assets = data.get("assets", {}).get("items", [])
        return [f"{IMMICH_URL}/api/asset/file/{asset['id']}" for asset in assets if asset.get("id")]
    except requests.exceptions.RequestException as e:
        print(f"Error searching Immich assets: {e}")
        return []


def get_albums():
    if not _check_config():
        return []
    try:
        url = f"{IMMICH_URL}/api/albums"
        params = {"size": 100}
        response = requests.get(url, headers=_get_headers(), params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return [{"id": album["id"], "name": album["albumName"], "assetCount": album.get("assetCount", 0)} for album in data]
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Immich albums: {e}")
        return []


def download_asset(asset_url):
    try:
        response = requests.get(asset_url, headers=_get_headers(), stream=True, timeout=60)
        response.raise_for_status()
        ext = ".jpg"
        content_type = response.headers.get("Content-Type", "")
        if "png" in content_type:
            ext = ".png"
        elif "heic" in content_type or "heif" in content_type:
            ext = ".heic"
        elif "webp" in content_type:
            ext = ".webp"
        filename = os.path.join(DOWNLOAD_PATH, f"immich_{int(time.time())}{ext}")
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return filename
    except requests.exceptions.RequestException as e:
        print(f"Error downloading asset from {asset_url}: {e}")
        return None