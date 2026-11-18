# modules/update_handler.py
import os
import re
import subprocess
import threading

import requests

# Update channels offered to the user. Keep in sync with update_application.sh
# and the validation in app.py.
BRANCHES = ('main', 'dev')
BRANCH_LABELS = {
    'main': 'Main (Stable Releases)',
    'dev': 'Dev (Development)',
}

INFO_URL = ("https://raw.githubusercontent.com/Npmr/rpi-rgb-led-matrix-frontend"
            "/refs/heads/{branch}/info.json")

# Guards against starting two updates at once (double click, two browsers).
_update_lock = threading.Lock()
_update_running = False


def update_script_path():
    """Absolute path of ``update_application.sh`` in the project root."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "update_application.sh",
    )


def is_update_running():
    """True while the update script is being executed."""
    return _update_running


def trigger_update(branch="main"):
    """Run the update script (blocking) and return a status message."""
    global _update_running
    with _update_lock:
        if _update_running:
            return "Update already running"
        _update_running = True
    try:
        subprocess.run(['sh', update_script_path(), branch])
    finally:
        with _update_lock:
            _update_running = False
    return "Update triggered successfully!"


def fetch_update_info(branch="main"):
    """Return the parsed info.json of a branch, or None when unavailable."""
    info, _error = fetch_branch_info(branch)
    return info


def fetch_branch_info(branch="main"):
    """Fetch a branch's info.json.

    Returns ``(info, error)`` where ``error`` is ``None`` on success,
    ``'not-found'`` when the branch (or its info.json) does not exist and
    ``'network'`` for any other failure. The distinction lets the UI say
    "branch not found" instead of pretending everything is up to date.
    """
    uri = INFO_URL.format(branch=branch)
    try:
        uResponse = requests.get(uri, timeout=10)
        if uResponse.status_code == 404:
            return None, 'not-found'
        uResponse.raise_for_status()  # Raise an exception for bad status codes
        return uResponse.json(), None
    except ValueError:
        # Branch exists but info.json is not valid JSON.
        print(f"Error parsing update info from {branch}: invalid JSON")
        return None, 'network'
    except requests.exceptions.RequestException as e:
        print(f"Error fetching update info: {e}")
        return None, 'network'


def parse_version(version):
    """Turn ``'v0.0.66'`` into ``(0, 0, 66)``; ``()`` when unparseable."""
    numbers = re.findall(r'\d+', str(version or ''))
    return tuple(int(number) for number in numbers)


def compare_versions(left, right):
    """Compare two version strings.

    Returns ``1`` when ``left`` is newer, ``-1`` when it is older and ``0``
    when they match. Unparseable versions only count as an update when the
    remote has numbers and the installed version does not.
    """
    left_parts = parse_version(left)
    right_parts = parse_version(right)
    if not left_parts or not right_parts:
        if str(left) == str(right):
            return 0
        # Unknown local version: prefer showing the remote as an update,
        # unknown remote version: nothing trustworthy to install.
        return 1 if left_parts else -1

    length = max(len(left_parts), len(right_parts))
    left_padded = left_parts + (0,) * (length - len(left_parts))
    right_padded = right_parts + (0,) * (length - len(right_parts))
    if left_padded > right_padded:
        return 1
    if left_padded < right_padded:
        return -1
    return 0


def normalize_branch(branch):
    """Return a supported branch name, falling back to ``main``."""
    return branch if branch in BRANCHES else 'main'


def check_branch_update(branch, current_version):
    """Check one branch against the installed version.

    Returns a report with ``version``, ``whatChanged``, ``updateAvailable``,
    ``relation`` (``available``/``up-to-date``/``local-newer``/``unknown``)
    and ``error`` (``None``/``not-found``/``network``).
    """
    branch = normalize_branch(branch)
    report = {
        'branch': branch,
        'version': None,
        'whatChanged': '',
        'updateAvailable': False,
        'relation': 'unknown',
        'error': None,
    }

    info, error = fetch_branch_info(branch)
    if error:
        report['error'] = error
        return report

    remote_version = info.get('currentApplicationVersion')
    if not remote_version:
        report['error'] = 'network'
        return report

    report['version'] = remote_version
    report['whatChanged'] = info.get('whatChanged', '')
    relation = compare_versions(remote_version, current_version)
    if relation > 0:
        report['updateAvailable'] = True
        report['relation'] = 'available'
    elif relation < 0:
        report['relation'] = 'local-newer'
    else:
        report['relation'] = 'up-to-date'
    return report


def branch_view(branch, report, current_version):
    """Build the display data for one branch row in the changelog page."""
    branch = normalize_branch(branch)
    view = {
        'key': branch,
        'label': BRANCH_LABELS[branch],
        'checked': report is not None,
        'version': None,
        'whatChanged': '',
        'updateAvailable': False,
        'stateClass': 'unchecked',
        'stateText': 'Not checked',
        'note': 'Run a check to see whether a newer version exists.',
    }
    if report is None:
        return view

    view['version'] = report.get('version')
    view['whatChanged'] = report.get('whatChanged', '')
    view['updateAvailable'] = bool(report.get('updateAvailable'))

    error = report.get('error')
    if error == 'not-found':
        view['stateClass'] = 'missing'
        view['stateText'] = 'Branch not found'
        view['note'] = (f'The {branch} branch does not exist on origin yet, '
                        f'so there is nothing to install from it.')
        return view
    if error:
        view['stateClass'] = 'unknown'
        view['stateText'] = 'Check failed'
        view['note'] = (f'Could not read info.json from the {branch} branch. '
                        f'Check the network connection and try again.')
        return view

    if view['updateAvailable']:
        view['stateClass'] = 'available'
        view['stateText'] = 'Update available'
        view['note'] = (f'Version {view["version"]} is available on the '
                        f'{branch} branch.')
        if view['whatChanged']:
            view['note'] += f' {view["whatChanged"]}'
    elif report.get('relation') == 'local-newer':
        view['stateClass'] = 'local-newer'
        view['stateText'] = 'Local build is newer'
        view['note'] = (f'The {branch} branch is on {view["version"]}, older '
                        f'than the installed {current_version}.')
    else:
        view['stateClass'] = 'up-to-date'
        view['stateText'] = 'Up to date'
        view['note'] = (f'The {branch} branch is on {view["version"]}, the '
                        f'installed version.')
    return view
