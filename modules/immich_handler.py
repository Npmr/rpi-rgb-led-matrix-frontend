# modules/immich_handler.py
import requests
import os
import time
import random
from .settings_handler import read_settings


DOWNLOAD_PATH = "static/immich_cache"

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)


def _get_config():
    """Get current Immich configuration from settings."""
    settings = read_settings()
    api_key = settings.get("immichApiKey", "")
    url = settings.get("immichUrl", "").rstrip("/")
    return api_key, url


def _check_config(api_key, url):
    """Validate Immich configuration."""
    if not api_key:
        print("Error: Immich API key not configured in settings")
        return False
    if not url:
        print("Error: Immich URL not configured in settings")
        return False
    return True


def _get_headers(api_key):
    """Get request headers with API key."""
    return {
        "Accept": "application/json",
        "x-api-key": api_key
    }


def _handle_response(response, context=""):
    """Handle API response with proper error logging."""
    try:
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        status = response.status_code
        error_msg = f"Immich API error {status} {context}: {response.text[:500]}"
        if status == 401:
            error_msg += " - Invalid or expired API key"
        elif status == 403:
            error_msg += " - API key lacks required permissions (asset.read, album.read)"
        elif status == 404:
            error_msg += " - Endpoint not found (check Immich version compatibility)"
        print(error_msg)
        return None
    except requests.exceptions.JSONDecodeError:
        print(f"Immich API {context}: Invalid JSON response: {response.text[:200]}")
        return None


def fetch_random_asset():
    """Fetch a random asset from Immich and return its download URL."""
    api_key, url = _get_config()
    if not _check_config(api_key, url):
        return None

    try:
        endpoint = f"{url}/api/search/random"
        payload = {"size": 50}
        response = requests.post(
            endpoint,
            headers=_get_headers(api_key),
            json=payload,
            timeout=30
        )
        data = _handle_response(response, "search/random")
        if not data or not isinstance(data, list) or len(data) == 0:
            print("Error: No random assets found in Immich response")
            return None

        asset = random.choice(data)
        asset_id = asset.get("id")
        if not asset_id:
            print("Error: Random asset missing 'id' field")
            return None

        return f"{url}/api/assets/{asset_id}/original"

    except requests.exceptions.RequestException as e:
        print(f"Error fetching random asset from Immich: {e}")
        return None


def fetch_assets_by_album(album_id):
    """Fetch a random asset from a specific Immich album."""
    api_key, url = _get_config()
    if not _check_config(api_key, url):
        return None

    try:
        # Use search/metadata endpoint with albumIds filter (correct Immich v2+ API)
        endpoint = f"{url}/api/search/metadata"
        payload = {
            "albumIds": [album_id],
            "size": 100,
            "withExif": False
        }
        response = requests.post(
            endpoint,
            headers=_get_headers(api_key),
            json=payload,
            timeout=30
        )
        data = _handle_response(response, f"search/metadata (album: {album_id})")
        if not data:
            return None

        # Handle paginated response: data.assets.items
        assets = data.get("assets", {}).get("items", [])
        if not assets:
            print(f"Error: No assets found in album {album_id}")
            return None

        asset = random.choice(assets)
        asset_id = asset.get("id")
        if not asset_id:
            print("Error: Album asset missing 'id' field")
            return None

        return f"{url}/api/assets/{asset_id}/original"

    except requests.exceptions.RequestException as e:
        print(f"Error fetching album assets from Immich: {e}")
        return None


def fetch_all_album_assets(album_id):
    """Fetch ALL assets from a specific Immich album with pagination.
    
    Returns a list of asset IDs (not URLs) for the album.
    """
    api_key, url = _get_config()
    if not _check_config(api_key, url):
        return []

    all_assets = []
    page = 1
    size = 100  # Max page size for Immich

    try:
        while True:
            endpoint = f"{url}/api/search/metadata"
            payload = {
                "albumIds": [album_id],
                "size": size,
                "page": page,
                "withExif": False
            }
            response = requests.post(
                endpoint,
                headers=_get_headers(api_key),
                json=payload,
                timeout=30
            )
            data = _handle_response(response, f"search/metadata (album: {album_id}, page: {page})")
            if not data:
                break

            assets = data.get("assets", {}).get("items", [])
            if not assets:
                break

            # Extract asset IDs
            for asset in assets:
                asset_id = asset.get("id")
                if asset_id:
                    all_assets.append(asset_id)

            # Check if there are more pages
            total = data.get("assets", {}).get("total", 0)
            if len(all_assets) >= total:
                break

            page += 1

        print(f"Fetched {len(all_assets)} assets from album {album_id}")
        return all_assets

    except requests.exceptions.RequestException as e:
        print(f"Error fetching all album assets from Immich: {e}")
        return []


def search_assets(query="", size=50):
    """Search Immich assets by metadata query."""
    api_key, url = _get_config()
    if not _check_config(api_key, url):
        return []

    try:
        endpoint = f"{url}/api/search/metadata"
        payload = {
            "query": query,
            "size": size,
            "withExif": False
        }
        response = requests.post(
            endpoint,
            headers=_get_headers(api_key),
            json=payload,
            timeout=30
        )
        data = _handle_response(response, "search/metadata")
        if not data:
            return []

        assets = data.get("assets", {}).get("items", [])
        if not assets:
            print(f"Info: No assets found for query: '{query}'")
            return []

        urls = []
        for asset in assets:
            asset_id = asset.get("id")
            if asset_id:
                urls.append(f"{url}/api/assets/{asset_id}/original")
        return urls

    except requests.exceptions.RequestException as e:
        print(f"Error searching Immich assets: {e}")
        return []


def get_albums():
    """Get all Immich albums."""
    api_key, url = _get_config()
    if not _check_config(api_key, url):
        return []

    try:
        endpoint = f"{url}/api/albums"
        params = {"size": 100}
        response = requests.get(
            endpoint,
            headers=_get_headers(api_key),
            params=params,
            timeout=30
        )
        data = _handle_response(response, "albums")
        if not data or not isinstance(data, list):
            return []

        albums = []
        for album in data:
            album_id = album.get("id")
            album_name = album.get("albumName") or album.get("name")
            asset_count = album.get("assetCount", 0)
            if album_id and album_name:
                albums.append({
                    "id": album_id,
                    "name": album_name,
                    "assetCount": asset_count
                })
        return albums

    except requests.exceptions.RequestException as e:
        print(f"Error fetching Immich albums: {e}")
        return []


def get_asset_info(asset_id):
    """Fetch asset info from Immich including EXIF orientation."""
    api_key, url = _get_config()
    if not _check_config(api_key, url):
        return None

    try:
        endpoint = f"{url}/api/assets/{asset_id}"
        response = requests.get(
            endpoint,
            headers=_get_headers(api_key),
            timeout=30
        )
        data = _handle_response(response, f"assets/{asset_id}")
        if not data:
            return None

        # Extract relevant fields including EXIF orientation
        exif_info = data.get("exifInfo", {})
        return {
            "id": data.get("id"),
            "width": data.get("width"),
            "height": data.get("height"),
            "orientation": exif_info.get("orientation"),  # EXIF orientation 1-8
            "exifInfo": exif_info
        }

    except requests.exceptions.RequestException as e:
        print(f"Error fetching asset info from Immich: {e}")
        return None


def download_asset(asset_id):
    """Download an asset from Immich by its ID."""
    api_key, url = _get_config()
    if not _check_config(api_key, url):
        return None

    try:
        # Try edited version first (thumbnail with size=original&edited=true)
        # Fall back to /original if not available
        endpoint = f"{url}/api/assets/{asset_id}/thumbnail"
        params = {"size": "original", "edited": "true"}
        response = requests.get(
            endpoint,
            headers=_get_headers(api_key),
            params=params,
            stream=True,
            timeout=60
        )

        if response.status_code == 400 or response.status_code == 404:
            # Fallback to original file
            response.close()
            endpoint = f"{url}/api/assets/{asset_id}/original"
            response = requests.get(
                endpoint,
                headers=_get_headers(api_key),
                stream=True,
                timeout=60
            )

        response.raise_for_status()

        ext = ".jpg"
        content_type = response.headers.get("Content-Type", "")
        if "png" in content_type:
            ext = ".png"
        elif "heic" in content_type or "heif" in content_type:
            ext = ".heic"
        elif "webp" in content_type:
            ext = ".webp"
        elif "jpeg" in content_type or "jpg" in content_type:
            ext = ".jpg"

        filename = os.path.join(DOWNLOAD_PATH, f"immich_{int(time.time())}{ext}")
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return filename

    except requests.exceptions.RequestException as e:
        print(f"Error downloading asset {asset_id} from Immich: {e}")
        return None
