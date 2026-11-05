"""Helpers for end-to-end tests against the kodi-dev environment (/workspaces/kodi-dev).

Prepare it once with `python tools/kodidev_setup.py`. Without a reachable Kodi the tests are skipped.
Another kodi-dev instance: set KDEV_INSTANCE (kdev reads it) and KODI_RPC_URL to its JSON-RPC port.
"""
import fcntl
import json
import os
import pathlib
import re
import shutil
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
import warnings

import pytest

KODI_DEV = pathlib.Path(os.environ.get('KODI_DEV', '/workspaces/kodi-dev'))
# the skin checkout, as in tests/static/conftest.py: tests/static/navigation.py reads it from here
# when an e2e test builds a window with it
ROOT = pathlib.Path(__file__).resolve().parents[2]

# KDEV_POOL=1 is kdev's default pool, KDEV_POOL=NAME a pool of its own (kdev reads it too)
POOL = os.environ.get('KDEV_POOL')
POOL = 'pool' if POOL == '1' else POOL
if POOL:
    # Set before any kdev call: the kdev subprocesses read it too
    os.environ['KDEV_INSTANCE'] = '{}-{}'.format(POOL, os.environ.get('PYTEST_XDIST_WORKER', 'gw0')[2:])


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


def movie_rating(movieid, rating):
    """Set or (RATING 0 or None) remove a movie's rating: SetMovieDetails ignores a rating of
    0.0, so a test that "restored" one with it left it behind for the next file on the Kodi."""
    if rating:
        rpc('VideoLibrary.SetMovieDetails', {'movieid': movieid, 'rating': rating})
    else:
        rpc('VideoLibrary.SetMovieDetails', {'movieid': movieid, 'ratings': {'default': None}})


BULK_FROM = 1000  # ids of movie rows tests add to the video database and remove again


def reset_library():
    """What tests change in this Kodi's video library and a stopped run leaves behind: added
    movie rows, ratings and genres. Fast (a few RPCs), run once per worker at session start."""
    database = sorted((_data() / 'kodi' / 'userdata' / 'Database').glob('MyVideos*.db'))
    if database:
        with sqlite3.connect(str(database[-1]), timeout=30) as connection:
            for table, key in (('videoversion', 'idFile'), ('movie', 'idMovie'), ('files', 'idFile')):
                connection.execute('DELETE FROM {} WHERE {} >= ?'.format(table, key), (BULK_FROM,))
        connection.close()
    for movie in rpc('VideoLibrary.GetMovies', {'properties': ['rating', 'genre']}).get('movies', []):
        if movie['rating']:
            movie_rating(movie['movieid'], None)
        if movie['genre']:
            rpc('VideoLibrary.SetMovieDetails', {'movieid': movie['movieid'], 'genre': []})


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

# Sends each line of its stdin to Kodi's event server as a builtin to execute (ACTION_EXECBUILTIN),
# in order. kodi-send (kdev builtin) sends a builtin as a button action instead: that goes through
# the windows like a key press, and Kodi drops every action while the topmost modal dialog plays
# its close animation ("ignoring action 122" in kodi.log), so a builtin sent right after such a
# dialog closed never ran, nor did the marker behind it.
_SEND_BUILTINS = '''import socket, sys
from kodi.xbmcclient import PacketACTION, ACTION_EXECBUILTIN
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
print('ready', flush=True)
for line in sys.stdin:
    PacketACTION(actionmessage=line.rstrip('\\n'), actiontype=ACTION_EXECBUILTIN).send(sock, ('127.0.0.1', 9777), uid=0)
'''


def _kodi_container():
    """The Kodi container of kodi-dev (compose project kodi-dev or kodi-dev-INSTANCE)."""
    name = os.environ.get('KDEV_INSTANCE')
    return 'kodi-dev-{}-kodi-1'.format(name) if name else 'kodi-dev-kodi-1'


_sender = [None]


def _send_builtins(*commands):
    """Hand COMMANDS to a sender kept running in the Kodi container: a docker exec and a Python
    start for each builtin cost 0.1 to 0.3 s, and tests send hundreds. It outlives Kodi restarts."""
    text = ''.join(command + '\n' for command in commands)
    for _ in range(2):
        sender = _sender[0]
        if sender is None or sender.poll() is not None:
            sender = _sender[0] = subprocess.Popen(
                ['docker', 'exec', '-i', _kodi_container(), 'python3', '-u', '-c', _SEND_BUILTINS],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            if sender.stdout.readline().strip() != 'ready':
                raise RuntimeError('builtin sender did not start in {}'.format(_kodi_container()))
        try:
            sender.stdin.write(text)
            sender.stdin.flush()
            return
        except BrokenPipeError:  # the container was restarted: start a new sender
            _sender[0] = None
    raise RuntimeError('builtin sender keeps dying in {}'.format(_kodi_container()))


def builtin(command):
    """Run a builtin and return once Kodi has run it.

    The event server only queues the builtin, so a marker property is queued right behind it and
    waited for: builtins run in order, so the marker means the command ran (no fixed sleep).
    """
    builtins(command)


def builtins(*commands):
    """Run several builtins in order and return once Kodi has run them all: one marker at the end,
    so a long row of them takes no round trip each."""
    _sync[0] += 1
    marker = 'String.IsEqual(Window(Home).Property(nc.test.sync),{})'.format(_sync[0])
    _send_builtins(*commands, 'SetProperty(nc.test.sync,{},home)'.format(_sync[0]))
    # 15 s: the marker waits behind the command and whatever blocks Kodi's main thread at the
    # time (a window loading plugin content, a dialog closing); this is a sync, not a check.
    # The event server is UDP: a datagram is lost now and then (one in a few thousand on a
    # loaded box), so the batch goes once more; its builtins are set, clear, open and close
    try:
        wait_for(marker, timeout=15)
    except AssertionError:
        warnings.warn('builtin marker {} not seen in 15 s on {}, sending again: {}'.format(
            _sync[0], os.environ.get('KDEV_INSTANCE', 'kodi-dev'), ' '.join(commands)))
        _send_builtins(*commands, 'SetProperty(nc.test.sync,{},home)'.format(_sync[0]))
        wait_for(marker, timeout=15)


def respelled(condition):
    """CONDITION with a number written anew, 5200 as 05200; the same value to Kodi, a new string."""
    def number(match):
        return match.group(1) + '0' + match.group(2) + ')'
    if 'String.' in condition:
        return condition
    return re.sub(r'([,(])(\d+)\)', number, condition)


def wait_for(condition, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        if cond(condition)[condition]:
            return
        time.sleep(0.05)
    # A condition Kodi first saw while another thread added an info string can be false for good:
    # AddMultiInfo has no lock and its id can be the other thread's. A whole file fails on it, when
    # its helper waits for the focus by the same words (reproduced: 3% of new conditions with three
    # script threads adding strings, 0 of 4600 without; the same condition written anew holds).
    other = respelled(condition)
    if other != condition and cond(other)[other]:
        warnings.warn('condition stuck false in Kodi {}: {}'.format(os.environ.get('KDEV_INSTANCE', 'kodi-dev'), condition))
        return
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


def _worker_answers(name):
    try:
        port = int(dict(line.split('=', 1) for line in (KODI_DEV / 'instances' / name / 'ports.env').read_text().split())['KODI_RPC_PORT'])
        body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'JSONRPC.Ping'}).encode()
        req = urllib.request.Request('http://localhost:{}/jsonrpc'.format(port), body, {'Content-Type': 'application/json'})
        return 'pong' in json.load(urllib.request.urlopen(req, timeout=3)).get('result', '')
    except (OSError, ValueError, KeyError):
        return False


def pytest_xdist_auto_num_workers(config):
    """-n auto on the pool: one xdist worker per pool Kodi that answers, counted from NAME-0 up
    (a pool brought up smaller than before keeps the folders of the workers it stopped)."""
    if not POOL:
        return None
    count = 0
    while _worker_answers('{}-{}'.format(POOL, count)):
        count += 1
    return count or len(list((KODI_DEV / 'instances').glob(POOL + '-[0-9]*/ports.env'))) or 1


_lock = [None]
_run_start = [None]


def pytest_configure(config):
    """One run per pool at a time: hold its run lock (kdev's pool commands check it too) for
    the whole run, so a second run on the same pool fails at once instead of two runs
    restarting each other's Kodis for minutes. The lock goes with the process, so a killed run
    leaves nothing behind."""
    if not POOL or os.environ.get('PYTEST_XDIST_WORKER'):
        return
    path = KODI_DEV / 'instances' / POOL / 'run.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, 'a+')
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.seek(0)
        holder = handle.read().strip() or 'another run'
        raise pytest.UsageError('pool {} is in use by a test run ({}); wait for it or stop it'.format(POOL, holder))
    handle.seek(0)
    handle.truncate()
    handle.write('pid {} since {}'.format(os.getpid(), time.strftime('%Y-%m-%d %H:%M:%S')))
    handle.flush()
    _lock[0] = handle
    _run_start[0] = int(time.time())


def crash_logs(listing, since):
    """The crash logs of a listing of "mtime path" lines that were written since the time SINCE."""
    logs = []
    for line in listing.splitlines():
        stamp, _, path = line.partition(' ')
        if stamp.isdigit() and int(stamp) >= since:
            logs.append(path.rsplit('/', 1)[-1])
    return logs


def crash_summary(crashes):
    """Lines for the report; CRASHES is {instance: its crash logs, None if it could not be asked}."""
    asked = {name: logs for name, logs in crashes.items() if logs is not None}
    lines = ['Kodi crashes in this run: {} ({} workers looked at)'.format(sum(map(len, asked.values())), len(asked))]
    for name, logs in crashes.items():
        if logs is None:
            lines.append('  {}: not running, its crash logs cannot be read'.format(name))
        for log in logs or []:
            lines.append('  {}: {}'.format(name, log))
    return lines


def _worker_crashes(name, since):
    """Kodi's start script writes a crash log whenever Kodi dies of a signal that dumps core, also
    while it quits. "Kodi exited" in the container's log cannot tell that apart: every kdev restart
    prints it too, and the container's log says nothing of why."""
    done = subprocess.run(['docker', 'exec', 'kodi-dev-{}-kodi-1'.format(name), 'sh', '-c',
                           'stat -c "%Y %n" "$HOME"/kodi_crashlog-*.log 2>/dev/null; true'], capture_output=True, text=True)
    return crash_logs(done.stdout, since) if done.returncode == 0 else None


def pytest_terminal_summary(terminalreporter):
    if not POOL or os.environ.get('PYTEST_XDIST_WORKER') or _run_start[0] is None:
        return
    names = sorted((path.parent.name for path in (KODI_DEV / 'instances').glob(POOL + '-[0-9]*/ports.env')),
                   key=lambda name: int(name.rsplit('-', 1)[1]))
    workers = terminalreporter.config.getoption('numprocesses', None) or 1
    crashes = {name: _worker_crashes(name, _run_start[0]) for name in names[:workers]}
    terminalreporter.write_sep('-', 'Kodi')
    for line in crash_summary(crashes):
        terminalreporter.write_line(line)


# Files whose tests do not rely on each other: under --dist loadfile each of their tests is a work
# unit of its own. A file on one Kodi otherwise sets the length of the whole run.
SPLIT_FILES = {'test_tmdb_chain.py', 'test_home_sections.py', 'test_osd_autohide.py'}


def pytest_xdist_make_scheduler(config, log):
    from xdist.scheduler import LoadFileScheduling

    class FileOrTestScheduling(LoadFileScheduling):
        def _split_scope(self, nodeid):
            path = nodeid.split('::', 1)[0]
            return nodeid if path.rsplit('/', 1)[-1] in SPLIT_FILES else path

    return FileOrTestScheduling(config, log) if config.getvalue('dist') == 'loadfile' else None


# What of kodi.log goes into a failure report: windows, the skin's service and TMDb Helper's
# window manager, dropped actions, errors; not the plugin and texture chatter
LOG_KEEP = re.compile(r'Window (Init|Deinit) \(|Window Manager \[|nightcity|ignoring action|error <general>|'
                      r'EXCEPTION|Traceback|Error|Kodi exited|Segmentation|terminate called|Activating window|'
                      r'CScriptRunner|onExecutionDone|Player:: |CVideoPlayer::(Open|Close)', re.I)
LOG_DROP = re.compile(r'DEBUG::|Skipped \d+ duplicate|CWebserver|CheckIdle|GetImage|Texture|CurlFile|'
                      r'VideoLibrary.GetMovies|XBMC.Get|JSONRPC')


@pytest.fixture(autouse=True)
def _kodi_log_slice(request):
    """The lines of kodi.log a failed test ran against, as a section of its report: the
    window and chain events that explain a timeout, which the assertion alone never does."""
    log = _data() / 'kodi' / 'temp' / 'kodi.log'
    start = log.stat().st_size if log.is_file() else 0
    request.node._kodi_log_start = start
    yield


def _kodi_log_lines(start, limit=120):
    log = _data() / 'kodi' / 'temp' / 'kodi.log'
    if not log.is_file():
        return ''
    with open(log, 'rb') as f:
        if log.stat().st_size < start:  # Kodi restarted: a new log
            start = 0
        f.seek(start)
        text = f.read().decode(errors='replace')
    lines = [line for line in text.splitlines() if LOG_KEEP.search(line) and not LOG_DROP.search(line)]
    if len(lines) > limit:
        lines = ['... {} earlier lines left out'.format(len(lines) - limit)] + lines[-limit:]
    return '\n'.join(line.rstrip()[:220] for line in lines)


# What Kodi stands on when a test fails: a timeout alone says nothing of who has the focus.
KODI_STATE = ['System.CurrentWindow', 'System.CurrentControl', 'System.CurrentControlId', 'Container.FolderPath',
              'Window(Home).Property(nc.library)', 'Window(Home).Property(nc.lib.bar)', 'Skin.String(nc.sort)']
KODI_CONDITIONS = ['System.HasActiveModalDialog', 'System.HasModalDialog', 'Window.IsActive(1110)', 'Window.IsVisible(1110)',
                   'Window.IsActive(home)', 'Control.IsVisible(5100)', 'Control.IsVisible(5101)', 'Control.IsEnabled(5101)',
                   'Control.HasFocus(5101)', 'Control.HasFocus(5000)', 'Container(5000).IsUpdating', 'Player.HasMedia']
KEEP_LOG_AT = 3  # failures in a file: from here on it is not one test's fault


def keep_log_now(seen, name):
    """Whether this failure of the file NAME is the one to keep the whole kodi.log for."""
    seen[name] = seen.get(name, 0) + 1
    return seen[name] == KEEP_LOG_AT


def _kodi_state():
    try:
        return '\n'.join('{} = {!r}'.format(k, v) for result in (info(*KODI_STATE), cond(*KODI_CONDITIONS)) for k, v in result.items())
    except (OSError, RuntimeError, ValueError) as e:
        return 'Kodi does not answer: {}'.format(e)


def _keep_log(name):
    """The whole of kodi.log, the run before it and a picture, by the time a file fails wholesale;
    the next run on this Kodi overwrites them."""
    instance = os.environ.get('KDEV_INSTANCE', 'kodi-dev')
    folder = KODI_DEV / 'instances' / (POOL or instance) / 'kept-logs' / '{}-{}-{}'.format(instance, name, time.strftime('%H%M%S'))
    folder.mkdir(parents=True, exist_ok=True)
    for log in ('kodi.log', 'kodi.old.log'):
        source = _data() / 'kodi' / 'temp' / log
        if source.is_file():
            shutil.copy(source, folder / log)
    try:
        shutil.copy(screenshot('kept-{}'.format(name)), folder / 'screen.png')
    except (OSError, IndexError, subprocess.CalledProcessError):
        pass
    return folder


_failed_in_file = {}


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.failed and getattr(item, '_kodi_log_start', None) is not None:
        try:
            text = _kodi_log_lines(item._kodi_log_start)
        except OSError as e:
            text = 'kodi.log not readable: {}'.format(e)
        if text:
            report.sections.append(('kodi.log of {} ({})'.format(os.environ.get('KDEV_INSTANCE', 'kodi-dev'), call.when), text))
        report.sections.append(('Kodi at the failure ({})'.format(call.when), _kodi_state()))
        if keep_log_now(_failed_in_file, item.path.name):
            report.sections.append(('kept', 'the whole kodi.log is in {}'.format(_keep_log(item.path.stem))))


def pytest_collection_modifyitems(config, items):
    if _kodi_up():
        return
    if POOL:
        # a pool worker's Kodi answers late after pool up or a crash: wait, and fail loudly
        # rather than skip a worker's share of the suite (174 skips in one run, by load)
        end = time.time() + 120
        while time.time() < end and not _kodi_up():
            time.sleep(2)
        if not _kodi_up():
            raise RuntimeError('Kodi of {} does not answer JSON-RPC'.format(os.environ.get('KDEV_INSTANCE')))
        return
    skip = pytest.mark.skip(reason='kodi-dev not running (python tools/kodidev_setup.py)')
    for item in items:
        if 'e2e' in item.keywords:
            item.add_marker(skip)


def _wait_for_service():
    """A Kodi just started: wait for the skin's startup script (nc.startup.ready: keymaps,
    one-off settings; the Startup screen starts it a second in, and a test that went Home
    before that made Home start the service without it, so an older run's keymaps stayed),
    then for the service, since a NotifyAll(nightcity,...) before it listens gets lost."""
    wait_for('!String.IsEmpty(Window(Home).Property(nc.startup.ready))', timeout=60)
    wait_for('!String.IsEmpty(Window(Home).Property(nc.service))', timeout=60)


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
        _wait_for_service()
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
    if POOL and _kodi_up():
        kdev('restart')
        _wait_for_service()
        reset_library()
    elif _kodi_up():
        builtin('Dialog.Close(all,true)')
        builtin('ReloadSkin()')
        time.sleep(3)
