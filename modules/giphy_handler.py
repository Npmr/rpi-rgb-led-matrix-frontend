# modules/giphy_handler.py
import requests
import os
import time
import random
from .settings_handler import read_settings

settings = read_settings()
# API key takes precedence from the environment, then falls back to settings.json.
GIPHY_API_KEY = os.environ.get("GIPHY_API_KEY") or settings.get("giphyApiKey", "YOUR_GIPHY_API_KEY")
TRENDING_API_URL = "http://api.giphy.com/v1/gifs/trending"
SEARCH_URL = f"https://api.giphy.com/v1/gifs/search?api_key={GIPHY_API_KEY}&q="
DOWNLOAD_PATH = "static/giphy_cache"

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

def fetch_trending_gif():
    params = {"api_key": GIPHY_API_KEY, "limit": 50} # Adjust limit as needed
    try:
        response = requests.get(TRENDING_API_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        if data and data.get("data"):
            trending_gifs = data["data"]
            random_gif = random.choice(trending_gifs)
            gif_url = random_gif["images"]["original"]["url"]
            return gif_url
        else:
            print("Error: No trending GIFs found in Giphy response.")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching trending GIFs from Giphy: {e}")
        return None

def fetch_searched_gif(search_term):
    search_query = search_term.replace(" ", "+")
    url = SEARCH_URL + search_query
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        gifs = response.json().get('data', [])
        if gifs:
            return random.choice(gifs)['images']['original']['url']
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching searched Giphy: {e}")
        return None

def download_gif(gif_url):
    try:
        response = requests.get(gif_url, stream=True, timeout=30)
        response.raise_for_status()
        filename = os.path.join(DOWNLOAD_PATH, f"giphy_{int(time.time())}.gif")
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return filename
    except requests.exceptions.RequestException as e:
        print(f"Error downloading GIF from {gif_url}: {e}")
        return None