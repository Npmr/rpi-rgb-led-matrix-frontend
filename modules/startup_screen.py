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
import math
import os
import socket
import tempfile
import uuid
from threading import Lock, Timer

from PIL import Image

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

HEADER_COLOR = (255, 190, 0)
TEXT_COLOR = (255, 255, 255)

# Pixel heights of the bundled BDF fonts (see modules/surface.py). Bitmap
# fonts only exist at their native size, so these are the selectable sizes.
FONT_SIZES = (6, 8, 10, 13, 18, 20)

# auto: scroll only when the text cannot fit, always: ticker, never: wrap/clip.
SCROLL_MODES = ("auto", "always", "never")
DEFAULT_SCROLL_SPEED = 12
MAX_SCROLL_SPEED = 120
# A ticker defaults to as many characters as fit, see ticker_font_height().
TICKER_GAP = "   "
MAX_TICKER_FRAMES = 400

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
    """Greedy word wrap using ``measure(text, font)`` for the pixel width.

    Words wider than the canvas (a long IP address or hostname) are split by
    character so nothing can silently run off the panel.
    """
    words = str(text or "").split()
    if not words or max_width <= 0:
        return []

    tokens = []
    for word in words:
        if measure(word, font) <= max_width:
            tokens.append(word)
        else:
            tokens.extend(_chunk_word(word, max_width, font, measure))

    lines = [tokens[0]]
    for token in tokens[1:]:
        candidate = f"{lines[-1]} {token}"
        if measure(candidate, font) <= max_width:
            lines[-1] = candidate
        else:
            lines.append(token)
    return lines


def _chunk_word(word, max_width, font, measure):
    """Split a word into pieces that each fit into one line."""
    chunks = []
    current = ""
    for character in word:
        candidate = current + character
        if current and measure(candidate, font) > max_width:
            chunks.append(current)
            current = character
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def font_size_setting(settings):
    """Configured text height in pixels, or ``None`` for automatic sizing."""
    raw = str(settings.get("startupScreenFontSize", "auto") or "auto")
    raw = raw.strip().lower()
    if raw in ("", "auto"):
        return None
    try:
        value = int(float(raw))
    except (TypeError, ValueError):
        return None
    if value < FONT_SIZES[0] or value > 256:
        return None
    return value


def scroll_mode(settings):
    """One of ``auto``, ``always`` or ``never``."""
    mode = str(settings.get("startupScreenScroll", "auto") or "auto")
    mode = mode.strip().lower()
    return mode if mode in SCROLL_MODES else "auto"


def scroll_speed_setting(settings):
    """Ticker speed in pixels per second, clamped to a sane range."""
    try:
        value = float(settings.get("startupScreenScrollSpeed",
                                   DEFAULT_SCROLL_SPEED))
    except (TypeError, ValueError):
        return float(DEFAULT_SCROLL_SPEED)
    return max(1.0, min(value, float(MAX_SCROLL_SPEED)))


def ticker_font_height(settings, height, width=None):
    """Largest readable font for one scrolling line of text.

    Without an explicit size the ticker uses the largest bundled font that
    still shows roughly six characters on the canvas, so a 32px panel gets the
    5x8 font while a wide panel can use a big one.
    """
    explicit = font_size_setting(settings)
    if explicit is not None:
        return max(FONT_SIZES[0], min(explicit, max(1, height)))
    limit = max(1, height)
    if width:
        limit = min(limit, width / 3.6)
    fitting = [size for size in FONT_SIZES if size <= limit]
    return max(fitting) if fitting else FONT_SIZES[0]


def _wrap_parts(parts, font_height, max_width, measure):
    """Wrap each part separately and return the flat list of lines."""
    font = load_font(font_height)
    lines = []
    for part in parts:
        text = str(part or "").strip()
        if not text:
            continue
        lines.extend(wrap_text(text, max_width, font, measure))
    return lines


def plan_info(settings, ip, width, height, padding=2):
    """Work out the info text, its font size and whether it fits.

    Returns a dict with ``lines``, ``fontHeight``, ``headerLines`` (how many of
    the lines belong to the name/IP header) and ``fits``. ``fits`` is False
    when even the smallest bundled font needs more vertical space than the
    canvas offers - the caller then scrolls the text instead of clipping it.
    """
    header = _header_lines(settings, ip)
    message = str(settings.get("startupScreenText") or "").strip()
    max_width = max(1, width - 2 * padding)
    surface = Surface(width, height)
    measure = lambda text, font: surface.measure_text(text, font)

    def layout(font_height):
        header_lines = _wrap_parts(header, font_height, max_width, measure)
        body_lines = _wrap_parts([message] if message else [], font_height,
                                 max_width, measure)
        return header_lines + body_lines, len(header_lines)

    explicit = font_size_setting(settings)
    if explicit is not None:
        lines, header_lines = layout(explicit)
        return {
            "lines": lines,
            "fontHeight": explicit,
            "headerLines": header_lines,
            "fits": len(lines) * explicit <= height,
        }

    # Automatic: largest legible font whose wrapped text still fits.
    for candidate in sorted(FONT_SIZES, reverse=True):
        if candidate > height:
            continue
        lines, header_lines = layout(candidate)
        if len(lines) * candidate <= height:
            return {
                "lines": lines,
                "fontHeight": candidate,
                "headerLines": header_lines,
                "fits": True,
            }

    smallest = FONT_SIZES[0]
    lines, header_lines = layout(smallest)
    return {
        "lines": lines,
        "fontHeight": smallest,
        "headerLines": header_lines,
        "fits": False,
    }


def build_info_lines(settings, ip, width, height, padding=2):
    """Return the info screen text lines for the given canvas."""
    return plan_info(settings, ip, width, height, padding)["lines"]


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
    return plan_info(settings, ip, width, height, padding)["lines"]


def render_info_image(settings=None, ip=None, size=None, path=None):
    """Render the device info screen and return the path of the image.

    The result is a PNG, or an animated GIF when the text has to scroll: either
    because scrolling is configured, or because the name, IP and welcome text
    cannot fit on the canvas at the smallest legible font. ``led-image-viewer``
    loops animated GIFs, so the ticker keeps running until the timer cancels it.
    """
    settings = read_settings() if settings is None else settings
    if size is None:
        geometry = get_display_geometry(settings)
        size = (geometry["width"], geometry["height"])
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    ip = compute_local_ip() if ip is None else ip

    plan = plan_info(settings, ip, width, height)
    mode = scroll_mode(settings)
    if mode == "always" or (mode == "auto" and not plan["fits"]):
        return render_info_ticker(settings, ip, (width, height), path)

    surface = Surface(width, height)
    line_height = plan["fontHeight"]
    font = load_font(line_height)
    start_y = max(0, (height - line_height * len(plan["lines"])) // 2)
    for index, text in enumerate(plan["lines"]):
        color = HEADER_COLOR if index < plan["headerLines"] else TEXT_COLOR
        surface.draw_text(0, start_y + index * line_height, width, line_height,
                          text, color, font)

    if path is None:
        path = os.path.join(
            tempfile.gettempdir(), f"led_startup_{uuid.uuid4().hex}.png")
    surface.to_rgb().save(path)
    return path


def render_info_ticker(settings=None, ip=None, size=None, path=None):
    """Render name, IP and welcome text as a scrolling animated GIF."""
    settings = read_settings() if settings is None else settings
    if size is None:
        geometry = get_display_geometry(settings)
        size = (geometry["width"], geometry["height"])
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    ip = compute_local_ip() if ip is None else ip

    font_height = ticker_font_height(settings, height, width)
    font = load_font(font_height)

    segments = []
    title = str(settings.get("deviceName") or "").strip()
    if title:
        segments.append((title, HEADER_COLOR))
    segments.append((f"IP: {ip}", HEADER_COLOR))
    message = str(settings.get("startupScreenText") or "").strip()
    if message:
        segments.append((message, TEXT_COLOR))

    measure_surface = Surface(width, height)
    widths = [max(1, measure_surface.measure_text(text, font))
              for text, _color in segments]
    gap = max(1, measure_surface.measure_text(TICKER_GAP, font))
    strip_width = sum(widths) + gap * len(segments)

    # One wide strip, drawn once; every frame is a clipped view of it.
    strip = Surface(strip_width, height)
    x = 0
    for (text, color), text_width in zip(segments, widths):
        strip.draw_text(x, 0, text_width + 2, height, text, color, font,
                        align="left")
        x += text_width + gap

    speed = scroll_speed_setting(settings)
    travel = strip_width + width
    step = max(1, int(math.ceil(travel / MAX_TICKER_FRAMES)))
    # GIF delays are stored in hundredths of a second.
    frame_ms = max(10, int(round((step / speed) * 100.0)) * 10)

    frames = []
    for offset in range(0, travel, step):
        frame = Image.new("RGB", (width, height), (0, 0, 0))
        frame.paste(strip.image, (width - offset, 0))
        frames.append(frame)

    if path is None:
        path = os.path.join(
            tempfile.gettempdir(), f"led_startup_{uuid.uuid4().hex}.gif")
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=frame_ms, loop=0, optimize=False)
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
