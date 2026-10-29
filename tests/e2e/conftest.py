"""Helpers for end-to-end tests against the kodi-dev environment (/workspaces/kodi-dev).

Prepare it once with `python tools/kodidev_setup.py`. Without a reachable Kodi the tests are skipped.
Another kodi-dev instance: set KDEV_INSTANCE (kdev reads it) and KODI_RPC_URL to its JSON-RPC port.
"""
import json
import os
import pathlib
import subprocess
import time
import urllib.error
import urllib.request

import pytest

KODI_DEV = pathlib.Path(os.environ.get('KODI_DEV', '/workspaces/kodi-dev'))

if os.environ.get('KDEV_POOL'):
    # Set before any kdev call: the kdev subprocesses read it too
    os.environ['KDEV_INSTANCE'] = 'pool-{}'.format(os.environ.get('PYTEST_XDIST_WORKER', 'gw0')[2:])


def _data():
    name = os.environ.get('KDEV_INSTANCE')
    return KODI_DEV / 'instances' / name / 'data' if name else KODI_DEV / 'data'


def _rpc_port():
    """8080, or the port of the kodi-dev instance named in KDEV_INSTANCE (kdev reads it too)."""
    name = os.environ.get('KDEV_INSTANCE')
    if not name:
        return 8080
    ports = (KODI_DEV / 'instances' / name / 'ports.env').read_text()
    return int(dict(line.split('=', 1) for line in ports.split()).get('KODI_RPC_PORT', 8080))


def seed():
    """kodi-dev's seed data (Jellyfin users, item ids) of this Kodi; 'user' is the Jellyfin user
    its add-ons are signed in with."""
    data = json.loads((_data() / 'seed.json').read_text())
    data.setdefault('user', 'tester')
    return data


RPC_URL = os.environ.get('KODI_RPC_URL') or 'http://localhost:{}/jsonrpc'.format(_rpc_port())


def rpc(method, params=None):
    body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}}).encode()
    req = urllib.request.Request(RPC_URL, body, {'Content-Type': 'application/json'})
    res = json.load(urllib.request.urlopen(req, timeout=30))
    if 'error' in res:
        raise RuntimeError('{}: {}'.format(method, res['error']))
    return res['result']


def info(*labels):
    return rpc('XBMC.GetInfoLabels', {'labels': list(labels)})


def cond(*conditions):
    return rpc('XBMC.GetInfoBooleans', {'booleans': list(conditions)})


def action(*names, delay=0.3):
    for name in names:
        rpc('Input.ExecuteAction', {'action': name})
        time.sleep(delay)


def kdev(*args):
    return subprocess.run([str(KODI_DEV / 'kdev'), *args], cwd=KODI_DEV, check=True,
                          capture_output=True, text=True).stdout


_sync = [0]

# Sends each argument to Kodi's event server as a builtin to execute (ACTION_EXECBUILTIN), in order.
# kodi-send (kdev builtin) sends a builtin as a button action instead: that goes through the
# windows like a key press, and Kodi drops every action while the topmost modal dialog plays its
# close animation ("ignoring action 122" in kodi.log), so a builtin sent right after such a dialog
# closed never ran, nor did the marker behind it.
_SEND_BUILTINS = '''import socket, sys
from kodi.xbmcclient import PacketACTION, ACTION_EXECBUILTIN
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for command in sys.argv[1:]:
    PacketACTION(actionmessage=command, actiontype=ACTION_EXECBUILTIN).send(sock, ('127.0.0.1', 9777), uid=0)
'''


def _kodi_container():
    """The Kodi container of kodi-dev (compose project kodi-dev or kodi-dev-INSTANCE)."""
    name = os.environ.get('KDEV_INSTANCE')
    return 'kodi-dev-{}-kodi-1'.format(name) if name else 'kodi-dev-kodi-1'


def builtin(command):
    """Run a builtin and return once Kodi has run it.

    The event server only queues the builtin, so a marker property is queued right behind it and
    waited for: builtins run in order, so the marker means the command ran (no fixed sleep).
    """
    _sync[0] += 1
    subprocess.run(['docker', 'exec', _kodi_container(), 'python3', '-c', _SEND_BUILTINS, command,
                    'SetProperty(nc.test.sync,{},home)'.format(_sync[0])],
                   check=True, capture_output=True, text=True)
    wait_for('String.IsEqual(Window(Home).Property(nc.test.sync),{})'.format(_sync[0]))


def wait_for(condition, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        if cond(condition)[condition]:
            return
        time.sleep(0.05)
    raise AssertionError('timed out waiting for {}'.format(condition))


def screenshot(name):
    return pathlib.Path(kdev('screenshot', name).strip().splitlines()[-1])


def kodi_log(pattern):
    return kdev('log', '-g', pattern)


def _kodi_up():
    try:
        rpc('JSONRPC.Ping')
        return True
    except (urllib.error.URLError, OSError, RuntimeError):
        return False


def pytest_xdist_auto_num_workers(config):
    """-n auto on the pool: one xdist worker per pool Kodi."""
    if os.environ.get('KDEV_POOL'):
        return len(list((KODI_DEV / 'instances').glob('pool-[0-9]*/ports.env'))) or 1
    return None


def pytest_collection_modifyitems(config, items):
    if _kodi_up():
        return
    skip = pytest.mark.skip(reason='kodi-dev not running (python tools/kodidev_setup.py)')
    for item in items:
        if 'e2e' in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def home():
    """Start each test from Home with nothing playing and no dialog open.

    System.HasModalDialog stays false for some code-opened dialogs (DialogVideoInfo), so check
    System.HasActiveModalDialog.

    kodi-dev's jellyfin-kodi asks "Resume the previous sync?" after a restart; back answers no.
    """
    if not _kodi_up():
        # Kodi crashed and its container starts it again: wait, so only the test that crashed it fails
        kdev('wait')
    for _ in range(5):
        if not cond('System.HasActiveModalDialog')['System.HasActiveModalDialog']:
            break
        action('back', delay=1)
    players = rpc('Player.GetActivePlayers')
    for player in players:  # video 1, music 0
        rpc('Player.Stop', {'playerid': player['playerid']})
    if players:
        time.sleep(1)
    builtin('ReplaceWindow(Home)')
    wait_for('Window.IsActive(home)')
    # nc.page outlives the window, so a test that ends on another page would hide the home rows
    if not cond('String.IsEqual(Window(Home).Property(nc.page),home)')['String.IsEqual(Window(Home).Property(nc.page),home)']:
        builtin('SetFocus(9101)')
        wait_for('String.IsEqual(Window(Home).Property(nc.page),home)')
    builtin('SetFocus(9010)')
    wait_for('Control.HasFocus(9010)')


@pytest.fixture(scope='session', autouse=True)
def reload_skin():
    """Kodi caches the skin XML, so pick up the working tree once per test run.

    A pool Kodi runs for days: restart it, so the skin's startup (keymaps, properties) is the
    working tree's too. Elsewhere reload the skin; reloading with a dialog open leaves that
    dialog stuck half-closed (no Deinit, later opens are ignored), so close all dialogs first.
    """
    if os.environ.get('KDEV_POOL') and _kodi_up():
        kdev('restart')
    elif _kodi_up():
        builtin('Dialog.Close(all,true)')
        builtin('ReloadSkin()')
        time.sleep(3)
