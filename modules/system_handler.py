# modules/system_handler.py
import shutil
import subprocess
import os
import urllib.request
from datetime import datetime
import re

COMMON_TIMEZONES = [
    "UTC",
    "Europe/London",
    "Europe/Berlin",
    "Europe/Paris",
    "Europe/Rome",
    "Europe/Madrid",
    "Europe/Amsterdam",
    "Europe/Stockholm",
    "Europe/Oslo",
    "Europe/Copenhagen",
    "Europe/Helsinki",
    "Europe/Warsaw",
    "Europe/Vienna",
    "Europe/Zurich",
    "Europe/Brussels",
    "Europe/Lisbon",
    "Europe/Dublin",
    "Europe/Athens",
    "Europe/Bucharest",
    "Europe/Sofia",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Anchorage",
    "America/Phoenix",
    "America/Toronto",
    "America/Vancouver",
    "America/Mexico_City",
    "America/Sao_Paulo",
    "America/Argentina/Buenos_Aires",
    "Asia/Tokyo",
    "Asia/Shanghai",
    "Asia/Hong_Kong",
    "Asia/Singapore",
    "Asia/Dubai",
    "Asia/Tel_Aviv",
    "Australia/Sydney",
    "Australia/Melbourne",
    "Australia/Perth",
    "Pacific/Auckland",
]

VALID_STRFTIME_CODES = set('aAbBcdDfFgGhHIjjmMnprRStTuUVwWxXyYzZ%')

_ntpdate_available = None


def getFreeDiskSpace():
    total, used, free = shutil.disk_usage("/")
    return (100 / (total // (2 ** 30))) * (used // (2 ** 30)), (free // (2 ** 30))


def reboot_system():
    os.system('sudo reboot')
    return "Reboot System now!"


def shutdown_system():
    os.system('sudo shutdown -h now')
    return "Shutting down! Bye bye"


def has_internet():
    """Quick non-blocking internet check."""
    try:
        urllib.request.urlopen('http://pool.ntp.org', timeout=3)
        return True
    except Exception:
        return False


def sync_time():
    """Sync system time via NTP. Non-blocking fire-and-forget."""
    global _ntpdate_available
    if _ntpdate_available is None:
        _ntpdate_available = shutil.which('ntpdate') is not None

    if _ntpdate_available:
        subprocess.Popen(
            ['sudo', 'ntpdate', '-s', 'pool.ntp.org'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    else:
        subprocess.Popen(
            ['sudo', 'timedatectl', 'set-ntp', 'true'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        subprocess.Popen(
            ['sudo', 'systemctl', 'restart', 'systemd-timesyncd'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    return "Time synchronization triggered"


def validate_strftime(fmt):
    """Validate strftime format string by checking all %X codes are valid."""
    for match in re.finditer(r'%([a-zA-Z%])', fmt):
        code = match.group(1)
        if code not in VALID_STRFTIME_CODES:
            return False, f"Invalid format code: %{code}"
    return True, ""