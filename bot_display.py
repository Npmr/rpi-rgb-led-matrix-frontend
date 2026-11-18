#!/usr/bin/env python3
"""Full-screen display bot renderer.

Runs as a standalone process because the RGB matrix can only be owned by one
process at a time. It renders a single large face, follows ``settings.json``
(hot-reloaded) and drains bot events from the shared event spool.

Usage:
    sudo python3 bot_display.py
"""
import os
import signal
import sys
import time

from modules.bot.engine import BotEngine
from modules.bot.motion import (
    MAX_WANDER_SCALE,
    Wanderer,
    eye_options,
    face_scale,
    wander_enabled,
    wander_speed,
)
from modules.bot.render import draw_face
from modules.bot.status import write_status
from modules.bot.styles import available_styles
from modules.matrix import build_matrix
from modules.settings_handler import read_settings
from modules.surface import Surface

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(PROJECT_ROOT, "settings.json")

FRAME_INTERVAL = 1.0 / 30.0
STATUS_INTERVAL = 0.5

DEFAULT_STYLE = "robot"
DEFAULT_COLOR = "#00d4ff"
DEFAULT_ACCENT = "#ffb000"
DEFAULT_BACKGROUND = "#000000"


def _settings_mtime():
    try:
        return os.path.getmtime(SETTINGS_PATH)
    except OSError:
        return None


def _color_setting(settings, key, default):
    value = settings.get(key)
    return value if value not in (None, "") else default


def _face_rect(now, width, height, settings, wanderer, paused=False):
    """Return (x, y, w, h) for the face on a full-screen canvas."""
    scale = face_scale(settings)
    if wander_enabled(settings) and wanderer is not None:
        return wanderer.update(now, width, height, paused=paused)

    side = max(8, int(round(min(width, height) * scale)))
    return (width - side) // 2, (height - side) // 2, side, side


def _options(settings, config=None):
    return {
        "color": _color_setting(settings, "botFaceColor", DEFAULT_COLOR),
        "accent": _color_setting(settings, "botRobotAccent", DEFAULT_ACCENT),
        **eye_options(settings, config),
    }


def _face_style(settings, config=None):
    configured = (config or {}).get("faceStyle") or settings.get(
        "botFaceStyle", DEFAULT_STYLE
    )
    return configured if configured in available_styles() else DEFAULT_STYLE


def run():
    settings = read_settings()
    matrix = build_matrix(settings)
    width, height = matrix.width, matrix.height

    engine = BotEngine(settings)
    settings_mtime = _settings_mtime()

    wanderer = None
    if wander_enabled(settings):
        wanderer = Wanderer(
            speed=wander_speed(settings), scale=face_scale(settings)
        )

    style = _face_style(settings)
    options = _options(settings)

    surface = Surface(width, height)
    canvas = matrix.CreateFrameCanvas()

    running = True

    def _stop_handler(_signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, _stop_handler)
    signal.signal(signal.SIGINT, _stop_handler)

    print(f"Bot display running ({width}x{height}, style={style})")

    last_status = 0.0

    try:
        while running:
            frame_start = time.time()

            new_mtime = _settings_mtime()
            if new_mtime != settings_mtime:
                settings_mtime = new_mtime
                reloaded = read_settings()
                if reloaded:
                    settings = reloaded
                    engine.apply_settings(settings)
                    style = _face_style(settings)
                    options = _options(settings)
                    if wander_enabled(settings):
                        if wanderer is None:
                            wanderer = Wanderer(
                                speed=wander_speed(settings),
                                scale=face_scale(settings),
                            )
                        else:
                            wanderer.speed = wander_speed(settings)
                            wanderer.scale = min(face_scale(settings), MAX_WANDER_SCALE)
                    else:
                        wanderer = None
                    print(f"Bot display: reloaded settings (style={style})")

            now = time.time()
            engine.update(now)

            paused = engine.active is not None or engine.sleeping
            rect = _face_rect(now, width, height, settings, wanderer, paused=paused)

            surface.clear(_color_setting(settings, "botBackground", DEFAULT_BACKGROUND))
            draw_face(surface, rect, engine.model, style=style, options=options)

            canvas.SetImage(surface.image)
            canvas = matrix.SwapOnVSync(canvas)

            if now - last_status >= STATUS_INTERVAL:
                last_status = now
                state = engine.state()
                write_status({
                    "mode": "fullscreen",
                    "mood": state.get("mood"),
                    "sleeping": bool(state.get("sleeping")),
                    "active": state.get("active"),
                    "queued": state.get("queued", 0),
                    "style": style,
                    "wandering": wanderer is not None,
                })

            remaining = FRAME_INTERVAL - (time.time() - frame_start)
            if remaining > 0:
                time.sleep(remaining)
    finally:
        write_status({
            "mode": "stopped",
            "mood": engine.model.mood,
            "sleeping": bool(engine.sleeping),
            "active": None,
            "queued": 0,
            "style": style,
        })
        try:
            matrix.Clear()
        except Exception:
            pass
        print("Bot display stopped")


if __name__ == "__main__":
    try:
        run()
    except Exception as error:  # pragma: no cover - startup failures
        print(f"Bot display failed to start: {error}", file=sys.stderr)
        sys.exit(1)
