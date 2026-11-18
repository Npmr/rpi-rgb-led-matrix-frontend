# modules/bot/status.py
"""Tiny status file shared by the renderers and the Flask process.

The renderer owns the matrix and therefore the authoritative mood/sleep state,
but the web UI and Home Assistant live in the Flask process. Writing one small
JSON file (atomically, like the event spool) lets both sides agree without a
socket or a second MQTT connection.
"""
import json
import os
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_STATUS_PATH = os.path.join(PROJECT_ROOT, "runtime", "bot", "state.json")

_MAX_AGE = 30.0


def status_path():
    return os.environ.get("BOT_STATUS_PATH", DEFAULT_STATUS_PATH)


def write_status(fields):
    """Write ``fields`` plus an ``updatedAt`` timestamp atomically."""
    path = status_path()
    payload = dict(fields or {})
    payload["updatedAt"] = time.time()
    directory = os.path.dirname(path)
    try:
        os.makedirs(directory, exist_ok=True)
        temporary = f"{path}.{os.getpid()}.tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"), ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError as error:
        print(f"Bot status: could not write {path}: {error}")
        return None
    return payload


def read_status(max_age=_MAX_AGE):
    """Return the last status or ``{}`` when missing, broken or stale."""
    try:
        with open(status_path(), "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    if max_age is not None:
        updated = payload.get("updatedAt")
        if not isinstance(updated, (int, float)) or time.time() - updated > max_age:
            return {}
    return payload


def clear_status():
    try:
        os.unlink(status_path())
    except OSError:
        pass
