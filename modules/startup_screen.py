# modules/startup_screen.py
"""Startup screen shown on the matrix while the web app is coming up.

The screen either shows a picture from the existing picture library or a
generated info image with the device name, the local IP address and a welcome
text. It stays visible until the configured timer runs out or until the user
displays anything else, which is signalled by ``display_control.stopProcess()``.

Everything here is deliberately hardware free: the content is rendered with
Pillow (``modules.surface``) and handed to ``display_control`` for display, so
the whole flow can be unit tested.
"""
import os
import socket
import tempfile
import uuid
from threading import Lock, Timer

from .display_control import (
    display_image_file,
    is_grid_running,
    process_image_for_display,
)
from .geometry import get_display_geometry
from .settings_handler import flag_setting, read_settings
from .surface import Surface, load_font

DEFAULT_TEXT = "Welcome"
DEFAULT_DURATION = 30
MAX_DURATION = 24 * 60 * 60

_LOCK = Lock()
_cancelled = False
_launching = False
_showing = False
_timer = None


def _project_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pictures_dir():
    return os.path.join(_project_root(), "static", "pictures")


def compute_local_ip(timeout=0.5):
    """Best effort local IPv4 address, ``"offline"`` when there is none."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(timeout)
        # No packet is sent; connecting a UDP socket only selects a route.
        sock.connect(("8.8.8.8", 80))
        address = sock.getsockname()[0]
        if address and not address.startswith("0."):
            return address
    except OSError:
        pass
    finally:
        sock.close()

    try:
        address = socket.gethostbyname(socket.gethostname())
        if address and not address.startswith("127."):
            return address
        return address or "offline"
    except OSError:
        return "offline"


def _header_lines(settings, ip):
    title = str(settings.get("deviceName") or "").strip()
    lines = []
    if title:
        lines.append(title)
    lines.append(f"IP: {ip}")
    return lines


def wrap_text(text, max_width, font, measure):
    """Greedy word wrap using ``measure(text, font)`` for the pixel width."""
    words = str(text or "").split()
    if not words or max_width <= 0:
        return []
    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if measure(candidate, font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def duration_setting(settings):
    """Startup screen duration in seconds; ``0`` means 'until dismissed'."""
    raw = settings.get("startupScreenDuration", DEFAULT_DURATION)
    try:
        value = int(float(raw))
    except (TypeError, ValueError):
        return DEFAULT_DURATION
    return max(0, min(value, MAX_DURATION))


def _startup_image_path(settings):
    """Absolute path of the configured startup picture, or ``None``."""
    name = str(settings.get("startupScreenImage") or "").strip()
    if not name or os.path.basename(name) != name or ".." in name:
        return None
    path = os.path.join(pictures_dir(), name)
    return path if os.path.isfile(path) else None


def build_info_lines(settings, ip, width, height, padding=2):
    """Return the info screen text, word wrapped for the given canvas."""
    header = _header_lines(settings, ip)
    message = str(settings.get("startupScreenText") or "").strip()
    max_width = max(1, width - 2 * padding)
    max_lines = max(len(header) + 1, height // 8)

    lines = list(header)
    if message:
        surface = Surface(width, height)
        measure = lambda text, font: surface.measure_text(text, font)
        # Wrapping needs a font, the font size depends on the line count.
        # Two passes are enough to settle in practice.
        for _ in range(3):
            line_height = max(1, height // max(1, len(lines)))
            wrapped = wrap_text(message, max_width, load_font(line_height), measure)
            new_lines = header + wrapped
            if len(new_lines) > max_lines:
                new_lines = new_lines[:max_lines]
            if new_lines == lines:
                break
            lines = new_lines
    return lines


def render_info_image(settings=None, ip=None, size=None, path=None):
    """Render the device info screen and return the path of the PNG."""
    settings = read_settings() if settings is None else settings
    if size is None:
        geometry = get_display_geometry(settings)
        size = (geometry["width"], geometry["height"])
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    ip = compute_local_ip() if ip is None else ip

    lines = build_info_lines(settings, ip, width, height)
    header_count = len(_header_lines(settings, ip))

    surface = Surface(width, height)
    line_height = max(1, height // max(1, len(lines)))
    for index, text in enumerate(lines):
        font = load_font(line_height)
        color = (255, 190, 0) if index < header_count else (255, 255, 255)
        surface.draw_text(0, index * line_height, width, line_height,
                          text, color, font)

    if path is None:
        path = os.path.join(
            tempfile.gettempdir(), f"led_startup_{uuid.uuid4().hex}.png")
    surface.to_rgb().save(path)
    return path


def render_blank_image(settings=None, path=None):
    """A completely black canvas used to switch the panels off."""
    settings = read_settings() if settings is None else settings
    geometry = get_display_geometry(settings)
    surface = Surface(geometry["width"], geometry["height"])
    if path is None:
        path = os.path.join(
            tempfile.gettempdir(), f"led_startup_blank_{uuid.uuid4().hex}.png")
    surface.to_rgb().save(path)
    return path


def reset_startup_screen_state():
    """Forget any previous startup screen (used by tests)."""
    global _cancelled, _launching, _showing, _timer
    with _LOCK:
        timer, _timer = _timer, None
        _cancelled = False
        _launching = False
        _showing = False
    if timer is not None:
        timer.cancel()


def cancel_startup_screen():
    """Dismiss the startup screen and stop its timer.

    Called from ``display_control.stopProcess()``, so any display action
    (picture, Giphy, Immich, demo, grid start, MQTT) cancels the startup screen.
    While the startup screen itself is being launched the call is ignored.
    """
    global _cancelled, _showing, _timer
    with _LOCK:
        if _launching:
            return
        _cancelled = True
        _showing = False
        timer, _timer = _timer, None
    if timer is not None:
        timer.cancel()


def _on_timeout():
    global _timer, _showing
    with _LOCK:
        _timer = None
        was_showing = _showing
    if not was_showing:
        return

    # Stop the startup viewer and leave a black frame on the panels instead of
    # freezing the last startup image. Imported lazily: display_control imports
    # this module's cancel hook.
    cancel_startup_screen()
    from . import display_control
    try:
        display_control.stopProcess()
        blank = render_blank_image()
        display_control.display_image_file(blank, cleanup_path=blank)
    except Exception as exc:
        print(f"Startup screen timeout failed: {exc}")


def show_startup_screen(settings=None):
    """Display the startup screen once. Returns True when something was shown."""
    global _launching, _showing, _timer
    settings = read_settings() if settings is None else settings

    with _LOCK:
        if _cancelled or _launching or _showing:
            return False
        if not flag_setting(settings, "startupScreenEnabled"):
            return False

    if is_grid_running():
        print("Startup screen skipped: the grid display is running.")
        return False

    duration = duration_setting(settings)
    with _LOCK:
        _launching = True

    cleanup_path = None
    try:
        image_path = _startup_image_path(settings)
        if image_path:
            prepared = process_image_for_display(image_path, settings)
            cleanup_path = prepared if prepared != image_path else None
            display_path = prepared
        else:
            display_path = render_info_image(settings)
            cleanup_path = display_path
        display_image_file(display_path, cleanup_path=cleanup_path)
    except Exception as exc:
        print(f"Startup screen failed: {exc}")
        if cleanup_path and os.path.exists(cleanup_path):
            try:
                os.remove(cleanup_path)
            except OSError:
                pass
        return False
    finally:
        with _LOCK:
            _launching = False

    with _LOCK:
        _showing = True
        if duration > 0:
            _timer = Timer(duration, _on_timeout)
            _timer.daemon = True
            _timer.start()

    print(f"Startup screen shown for {duration}s." if duration else
          "Startup screen shown until the next action.")
    return True


def schedule_startup_screen(delay=3.0):
    """Show the startup screen after ``delay`` seconds, in the background."""
    def _run():
        try:
            show_startup_screen()
        except Exception as exc:
            print(f"Startup screen failed: {exc}")

    timer = Timer(delay, _run)
    timer.daemon = True
    timer.start()
    return timer
