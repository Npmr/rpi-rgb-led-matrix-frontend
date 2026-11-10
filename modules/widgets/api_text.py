# modules/widgets/api_text.py
"""Widget that periodically fetches a value from an HTTP API."""
import threading
import time
from urllib.parse import urlparse

import requests

from .base import Widget
from ..surface import load_font


def extract_json_path(data, path):
    """Resolve a dotted path (``main.temp``, ``items.0.name``) inside data."""
    if not path:
        return None
    current = data
    for part in str(path).split("."):
        if part == "":
            continue
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, (list, tuple)):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
        if current is None:
            return None
    return current


def extract_by_regex(text, pattern):
    """Return the first capture group (or whole match) of ``pattern``."""
    if not pattern:
        return None
    import re

    try:
        match = re.search(pattern, text)
    except re.error:
        return None
    if not match:
        return None
    if match.groups():
        return match.group(1)
    return match.group(0)


def format_value(value, decimals=0):
    """Format a fetched value into a compact string."""
    if value is None:
        return ""
    try:
        decimals = int(decimals)
    except (TypeError, ValueError):
        decimals = 0

    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, (int, float)):
        if decimals > 0:
            return f"{float(value):.{decimals}f}"
        return str(int(round(value)))
    return str(value)


def _is_http_url(url):
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


class ApiTextWidget(Widget):
    type_id = "api_text"

    def __init__(self, spec, context):
        super().__init__(spec, context)
        self.url = self.config.get("url", "")
        self.method = (self.config.get("method") or "GET").upper()
        self.json_path = self.config.get("jsonPath", "")
        self.regex = self.config.get("regex", "")
        self.prefix = self.config.get("prefix", "")
        self.suffix = self.config.get("suffix", "")
        self.error_text = self.config.get("errorText", "N/A")
        self.decimals = self.config.get("decimals", 0)
        try:
            self.interval = max(5, int(self.config.get("interval", 300)))
        except (TypeError, ValueError):
            self.interval = 300
        try:
            self.timeout = max(1, int(self.config.get("timeout", 10)))
        except (TypeError, ValueError):
            self.timeout = 10
        headers = self.config.get("headers")
        self.headers = headers if isinstance(headers, dict) else {}

        self._value = None
        self._text = ""
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    # --- fetching ---------------------------------------------------------
    def fetch_once(self):
        """Perform a single request and return the formatted value (or None)."""
        if not _is_http_url(self.url):
            return None
        try:
            response = requests.request(
                self.method,
                self.url,
                timeout=self.timeout,
                headers=self.headers,
            )
            response.raise_for_status()

            if self.json_path:
                try:
                    data = response.json()
                except ValueError:
                    return None
                value = extract_json_path(data, self.json_path)
            elif self.regex:
                value = extract_by_regex(response.text, self.regex)
            else:
                value = response.text.strip()
            return format_value(value, self.decimals)
        except requests.RequestException as error:
            print(f"API widget fetch failed ({self.url}): {error}")
            return None

    def _run(self):
        while not self._stop.is_set():
            value = self.fetch_once()
            with self._lock:
                if value is not None:
                    self._value = value
            self._stop.wait(self.interval)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        if not _is_http_url(self.url):
            with self._lock:
                self._value = None
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    # --- rendering --------------------------------------------------------
    def render(self, surface, rect):
        x, y, w, h = rect
        with self._lock:
            value = self._value
        if value is None:
            text = self.error_text
        else:
            text = f"{self.prefix}{value}{self.suffix}"
        if not text:
            return
        surface.draw_text(x, y, w, h, text, self.color, load_font(h), self.align)
