#!/usr/bin/env python3
"""Take the screenshots for README.md and addon.xml: python tools/screenshots.py [options] [SHOT ...]

Starts its own kodi-dev instance `shots` at 1920x1080 as a copy of the kodi-dev pool template
(run tools/kodidev_setup.py and `kdev pool up` once before) with this checkout as the skin, or
with --skin confuse the overlay assembled into _build/confuse. Its
library becomes a showcase: films and shows TMDb knows, with their metadata and artwork from TMDb
(see MOVIES and SHOWS). Then it opens each view and saves it as a 1280x720 JPEG in
resources/screenshots/, and removes the instance again. Needs ffmpeg and internet access;
`make screenshots` runs it in a container with both (Makefile, tools/screenshots.Dockerfile).

  SHOT ...          only these shots (home movies info person player music settings quick)
  --keep            keep the instance for the next run or a look over VNC
  --instance NAME   use the running instance a run with --keep left, as it is
  --skin NAME       nightcity (default) or confuse
  --out DIR         where the JPEGs go (default resources/screenshots, for confuse
                    skins/confuse/resources/screenshots)
  --png DIR         also save the 1920x1080 PNGs there

Ratings: TMDb Helper fetches IMDb, Rotten Tomatoes, Metacritic and the like only with an API
key. MDBLIST_API_KEY and OMDB_API_KEY from the environment go into TMDb Helper's settings
mdblist_apikey and omdb_apikey of the instance for the run (a kept instance gets its old values
back at the end). Without them the pages show TMDb's own rating. The keys are never printed,
logged or written to this checkout.
"""
import argparse
import importlib.machinery
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from build import assemble
from kodidev_setup import select_skin

ROOT = pathlib.Path(__file__).resolve().parents[1]
KODI_DEV = pathlib.Path(os.environ.get('KODI_DEV', '/workspaces/kodi-dev'))
SIZE = '1920x1080'
# what ships in the zip: Kodi's add-on browser and the README show them smaller anyway, and
# 1280x720 at 85 keeps the eight at about 750 KB (1920x1080: 1.4 MB)
SHIP_SIZE = (1280, 720)
JPEG_QUALITY = 85
WEATHER = 'weather.nightcity.fake'


def load_kdev():
    """kdev as a module: its instance and pool code makes the instance."""
    loader = importlib.machinery.SourceFileLoader('kdev', str(KODI_DEV / 'kdev'))
    spec = importlib.util.spec_from_loader('kdev', loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules['kdev'] = module  # its add-on profiles look it up there
    loader.exec_module(module)
    return module


class Kodi:
    """JSON-RPC and kdev calls on one kodi-dev instance."""

    def __init__(self, instance):
        self.instance = instance
        ports = (KODI_DEV / 'instances' / instance / 'ports.env').read_text()
        port = dict(line.split('=', 1) for line in ports.split())['KODI_RPC_PORT']
        self.url = 'http://localhost:{}/jsonrpc'.format(port)
        self.data = KODI_DEV / 'instances' / instance / 'data'
        self.container = 'kodi-dev-{}-kodi-1'.format(instance)
        self._sync = 0

    def rpc(self, method, params=None):
        body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}}).encode()
        req = urllib.request.Request(self.url, body, {'Content-Type': 'application/json'})
        res = json.load(urllib.request.urlopen(req, timeout=30))
        if 'error' in res:
            raise RuntimeError('{}: {}'.format(method, res['error']))
        return res['result']

    def up(self):
        try:
            self.rpc('JSONRPC.Ping')
            return True
        except (urllib.error.URLError, OSError, RuntimeError):
            return False

    def info(self, label):
        return self.rpc('XBMC.GetInfoLabels', {'labels': [label]})[label]

    def cond(self, condition):
        return self.rpc('XBMC.GetInfoBooleans', {'booleans': [condition]})[condition]

    def action(self, *names, delay=0.4):
        for name in names:
            self.rpc('Input.ExecuteAction', {'action': name})
            time.sleep(delay)

    def kdev(self, *args):
        return subprocess.run([str(KODI_DEV / 'kdev'), '-i', self.instance, *args], cwd=KODI_DEV,
                              check=True, capture_output=True, text=True).stdout

    def builtin(self, command):
        """Run a builtin through the event server and return once Kodi ran it (as the e2e
        conftest does: a marker property queued behind it)."""
        self._sync += 1
        send = ('import socket, sys\n'
                'from kodi.xbmcclient import PacketACTION, ACTION_EXECBUILTIN\n'
                'sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)\n'
                'for command in sys.argv[1:]:\n'
                "    PacketACTION(actionmessage=command, actiontype=ACTION_EXECBUILTIN).send(sock, ('127.0.0.1', 9777), uid=0)\n")
        subprocess.run(['docker', 'exec', self.container, 'python3', '-c', send, command,
                        'SetProperty(nc.shots.sync,{},home)'.format(self._sync)],
                       check=True, capture_output=True, text=True)
        self.wait('String.IsEqual(Window(Home).Property(nc.shots.sync),{})'.format(self._sync))

    def wait(self, condition, timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            if self.cond(condition):
                return
            time.sleep(0.1)
        raise RuntimeError('timed out waiting for ' + condition)

    def steady(self, condition, seconds=1.5, timeout=30):
        """Wait until CONDITION holds for SECONDS in a row (lists in, art loaded)."""
        end = time.time() + timeout
        since = None
        while time.time() < end:
            if self.cond(condition):
                since = since or time.time()
                if time.time() - since >= seconds:
                    return
            else:
                since = None
            time.sleep(0.1)
        raise RuntimeError('{} did not hold for {} s'.format(condition, seconds))

    def screenshot(self, name):
        return pathlib.Path(self.kdev('screenshot', name).strip().splitlines()[-1])


def _skin_folder(skin):
    return ROOT if skin == 'nightcity' else ROOT / '_build' / skin


def skin_mount(skin):
    return '{}:/home/kodi/.kodi/addons/skin.{}'.format(_skin_folder(skin), skin)


def start_instance(name, skin='nightcity'):
    """A fresh copy of the pool template as instance NAME, SKIN as its skin, at SIZE."""
    kdev = load_kdev()
    if not (KODI_DEV / 'instances' / 'pool' / 'data' / 'seed.json').exists():
        raise SystemExit('no kodi-dev pool template: run tools/kodidev_setup.py, then `kdev pool up` once')
    kdev.use_instance(name)
    folder = KODI_DEV / 'instances' / name
    (folder / '.env').write_text('KODI_RESOLUTION={}\n'.format(SIZE))
    if skin != 'nightcity':
        assemble(skin, _skin_folder(skin))
    kdev.pool_worker(name, [skin_mount(skin)], fresh=True)
    select_skin(folder / 'data' / 'kodi' / 'userdata' / 'guisettings.xml', skin)
    kdev.pool_start([name])


def remove_instance(name):
    subprocess.run([str(KODI_DEV / 'kdev'), '-i', name, 'remove', '--yes'], cwd=KODI_DEV, check=True)


# --- showcase library -------------------------------------------------------------------------
# kodi-dev's library is test clips without artwork. The instance this script starts gets real
# titles instead: placeholder clips (a dark gradient, chapters, 5.1 silence) named after films and
# shows TMDb knows, whose metadata and artwork the instance's Jellyfin fetches from TMDb.

MOVIES = [  # title, year, TMDb id
    ('The Matrix', 1999, 603), ('Blade Runner 2049', 2017, 335984), ('Blade Runner', 1982, 78),
    ('Ghost in the Shell', 1995, 9323), ('Akira', 1988, 149), ('Dune', 2021, 438631),
    ('Dune: Part Two', 2024, 693134), ('TRON: Legacy', 2010, 20526), ('Interstellar', 2014, 157336),
    ('Inception', 2010, 27205), ('Mad Max: Fury Road', 2015, 76341), ('Arrival', 2016, 329865),
    ('Ex Machina', 2015, 264660), ('Alita: Battle Angel', 2019, 399579),
    ('The Fifth Element', 1997, 18), ('Minority Report', 2002, 180),
]
SHOWS = [
    ('Cyberpunk: Edgerunners', 2022, 105248), ('Arcane', 2021, 94605), ('Severance', 2022, 95396),
    ('Breaking Bad', 2008, 1396), ('Mr. Robot', 2015, 62560), ('Black Mirror', 2011, 42009),
    ('Altered Carbon', 2018, 69050), ('Westworld', 2016, 63247),
]
EPISODES = 4
CLIPS = {'movie': (2 * 3600 + 16 * 60, 9), 'episode': (52 * 60, 5)}  # seconds, chapters


def folder_name(title, year=None):
    name = title.replace(':', '')
    return '{} ({})'.format(name, year) if year else name


def make_clip(path, seconds, chapters):
    """A 1080p clip of a slow dark gradient with CHAPTERS chapters and silent 5.1 audio."""
    with tempfile.TemporaryDirectory() as tmp:
        meta = pathlib.Path(tmp) / 'chapters.txt'
        step = seconds // chapters
        meta.write_text(';FFMETADATA1\n' + ''.join(
            '[CHAPTER]\nTIMEBASE=1/1000\nSTART={}\nEND={}\ntitle=Chapter {}\n'.format(
                n * step * 1000, min((n + 1) * step, seconds) * 1000, n + 1) for n in range(chapters)))
        subprocess.run([
            'ffmpeg', '-y', '-loglevel', 'error',
            '-f', 'lavfi', '-i', 'gradients=s=1920x1080:r=1:speed=0.002:n=3:type=radial:'
                                 'c0=0x050812:c1=0x0b3a4f:c2=0x3b0b33,format=yuv420p',
            '-f', 'lavfi', '-i', 'anullsrc=cl=5.1:r=48000', '-i', str(meta),
            '-map', '0:v', '-map', '1:a', '-map_chapters', '2', '-t', str(seconds),
            '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'stillimage', '-crf', '30',
            '-c:a', 'aac', '-b:a', '32k', str(path)], check=True)


def nfo(kind, title, year, tmdb):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<{0}><title>{1}</title><year>{2}</year>'
            '<uniqueid type="tmdb" default="true">{3}</uniqueid></{0}>\n').format(
                kind, title.replace('&', '&amp;'), year, tmdb)


def write_media(media):
    """MEDIA (the instance's media folder) gets the showcase titles in movies/ and shows/. The
    folders are hard links of the pool template's: unlink, never write into a file there."""
    clips = media / 'showcase'
    clips.mkdir(exist_ok=True)
    for kind, (seconds, chapters) in CLIPS.items():
        if not (clips / (kind + '.mkv')).exists():
            print('screenshots: making the {} clip'.format(kind))
            make_clip(clips / (kind + '.mkv'), seconds, chapters)
    for lib in ('movies', 'shows'):
        shutil.rmtree(media / lib, ignore_errors=True)
    for title, year, tmdb in MOVIES:
        folder = media / 'movies' / folder_name(title, year)
        folder.mkdir(parents=True)
        os.link(clips / 'movie.mkv', folder / (folder.name + '.mkv'))
        (folder / (folder.name + '.nfo')).write_text(nfo('movie', title, year, tmdb))
    for title, year, tmdb in SHOWS:
        folder = media / 'shows' / folder_name(title)
        (folder / 'Season 01').mkdir(parents=True)
        (folder / 'tvshow.nfo').write_text(nfo('tvshow', title, year, tmdb))
        for n in range(1, EPISODES + 1):
            os.link(clips / 'episode.mkv', folder / 'Season 01' / '{} S01E{:02d}.mkv'.format(folder.name, n))


def jellyfin_showcase(kdev, kodi):
    """The instance's Jellyfin fetches the showcase titles from TMDb, its Kodi syncs them and drops
    the bulk libraries of the performance tests."""
    token = kdev.load_seed()['admin']['api_key']

    def jf(method, path, body=None):
        return kdev.jf_ok(method, path, body, token=token)

    folders = {f['Name']: f for f in jf('GET', '/Library/VirtualFolders')}
    for name in ('Bulk', 'BulkShows'):
        if name in folders:
            kodi.builtin('RunPlugin(plugin://plugin.video.jellyfin/?mode=removelib&id={})'.format(folders[name]['ItemId']))
            jf('DELETE', '/Library/VirtualFolders?name={}&refreshLibrary=false'.format(name))
    for name in ('Movies', 'Shows'):
        options = folders[name]['LibraryOptions']
        for kind in options['TypeOptions']:
            kind['MetadataFetchers'] = ['TheMovieDb']
            kind['ImageFetchers'] = ['TheMovieDb']
        jf('POST', '/Library/VirtualFolders/LibraryOptions', {'Id': folders[name]['ItemId'], 'LibraryOptions': options})
    jf('POST', '/Library/Refresh')
    wait_until(lambda: len(jf('GET', '/Items?Recursive=true&IncludeItemTypes=Movie,Series')['Items'])
               == len(MOVIES) + len(SHOWS) and scan_idle(jf), 300, 'the library scan')
    items = jf('GET', '/Items?Recursive=true&IncludeItemTypes=Movie,Series')['Items']
    for item in items:
        jf('POST', '/Items/{}/Refresh?Recursive=true&MetadataRefreshMode=FullRefresh'
                   '&ImageRefreshMode=FullRefresh&ReplaceAllImages=true'.format(item['Id']))
    wait_until(lambda: scan_idle(jf) and all(
        i.get('ImageTags', {}).get('Primary') and i.get('BackdropImageTags')
        for i in jf('GET', '/Items?Recursive=true&IncludeItemTypes=Movie,Series&Fields=BackdropImageTags')['Items']),
        300, 'the artwork from TMDb')
    time.sleep(10)  # episodes and people come after their show
    for name in ('Movies', 'Shows'):
        kodi.builtin('RunPlugin(plugin://plugin.video.jellyfin/?mode=repairlib&id={})'.format(folders[name]['ItemId']))
        time.sleep(5)

    def gaps():
        return library_gaps(kodi.rpc('VideoLibrary.GetMovies', {'properties': ['art']}).get('movies', []),
                            kodi.rpc('VideoLibrary.GetTVShows', {'properties': ['art']}).get('tvshows', []))
    wait_until(lambda: not gaps(), 300, 'the Kodi library', state=gaps)
    # then it works through the updates of the sync for a while, with a progress bar and a
    # notification per new title
    kodi.steady(QUIET, seconds=10, timeout=600)


def scan_idle(jf):
    return all(t['State'] == 'Idle' for t in jf('GET', '/ScheduledTasks?isHidden=false')
               if t['Key'] == 'RefreshLibrary')


def library_gaps(movies, shows):
    """What the Kodi library still lacks of the showcase, '' when it has it all."""
    missing = ['{} ({})'.format(item['label'], ', '.join(art for art in ('poster', 'fanart') if art not in item['art']))
               for item in movies + shows if not {'poster', 'fanart'} <= set(item['art'])]
    if (len(movies), len(shows)) == (len(MOVIES), len(SHOWS)) and not missing:
        return ''
    return 'Kodi has {} of {} films and {} of {} shows{}'.format(
        len(movies), len(MOVIES), len(shows), len(SHOWS), '; no ' + ', '.join(missing[:5]) + (
            ' and {} more'.format(len(missing) - 5) if len(missing) > 5 else '') if missing else '')


def wait_until(check, timeout, what, state=None):
    """Polls CHECK until it holds; a timeout names WHAT and, with STATE, what it saw last."""
    end = time.time() + timeout
    while time.time() < end:
        if check():
            return
        time.sleep(2)
    raise RuntimeError('timed out waiting for ' + what + (': ' + state() if state else ''))


# --- ratings keys -----------------------------------------------------------------------------

KEYS = {'MDBLIST_API_KEY': 'mdblist_apikey', 'OMDB_API_KEY': 'omdb_apikey'}  # env: TMDb Helper setting
# Runs in Kodi: sets TMDb Helper's settings from a file the host wrote and removes the file at once.
# The values never pass through a builtin, so they do not end up in kodi.log.
SET_KEYS = '''import json, os, xbmcaddon, xbmcgui, xbmcvfs
path = xbmcvfs.translatePath('special://home/nc-shots-keys.json')
with open(path) as f:
    keys = json.load(f)
os.remove(path)
addon = xbmcaddon.Addon('plugin.video.themoviedb.helper')
for setting, value in keys.items():
    addon.setSetting(setting, value)
xbmcgui.Window(10000).setProperty('nc.shots.keys', '{}'.format(len(keys)))
'''


def set_keys(kodi, keys):
    """Put KEYS ({setting id: value}) into TMDb Helper's settings of the instance; returns the
    values they had. TMDb Helper reads its keys once when its service starts: restart Kodi after."""
    home = kodi.data / 'kodi'
    settings = kodi.data / 'kodi' / 'userdata' / 'addon_data' / 'plugin.video.themoviedb.helper' / 'settings.xml'
    values = {s.get('id'): s.text or '' for s in ET.parse(settings).getroot().iter('setting')} if settings.exists() else {}
    before = {setting: values.get(setting, '') for setting in keys}
    (home / 'nc-shots-keys.py').write_text(SET_KEYS)
    fd = os.open(home / 'nc-shots-keys.json', os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(keys, f)
    kodi.builtin('ClearProperty(nc.shots.keys,home)')
    kodi.builtin('RunScript(special://home/nc-shots-keys.py)')
    kodi.wait('String.IsEqual(Window(Home).Property(nc.shots.keys),{})'.format(len(keys)))
    (home / 'nc-shots-keys.py').unlink()
    return before


# --- the views --------------------------------------------------------------------------------

QUIET = ('!Window.IsVisible(notification) + !Window.IsVisible(extendedprogressdialog) + '
         '!Window.IsVisible(busydialog) + !Window.IsVisible(busydialognocancel)')
TMDB_IDLE = 'String.IsEmpty(Window(Home).Property(TMDbHelper.Instance))'


def prepare(kodi):
    """Once per run: fake weather, a still spotlight, some titles in progress and watched."""
    home(kodi)  # a skin reload with a dialog open leaves it stuck half-closed
    target = kodi.data / 'kodi' / 'addons' / WEATHER
    if not target.exists():
        shutil.copytree(ROOT / 'tests' / 'e2e' / 'fixtures' / WEATHER, target)
        kodi.builtin('UpdateLocalAddons')
        wait_until(lambda: any(a['addonid'] == WEATHER for a in kodi.rpc('Addons.GetAddons')['addons']), 30, WEATHER)
    kodi.rpc('Addons.SetAddonEnabled', {'addonid': WEATHER, 'enabled': True})
    kodi.rpc('Settings.SetSettingValue', {'setting': 'weather.addon', 'value': WEATHER})
    # a still spotlight: each shot picks its title (Kodi reads the interval when Home loads)
    for name in ('SpotlightInterval', 'nc.shows.interval', 'nc.music.interval'):
        kodi.builtin('Skin.SetString({},off)'.format(name))
    # TMDb's own rating next to the ones the API keys bring
    kodi.builtin('Skin.SetBool(nc.ratings.show.tmdb)')
    movies = {m['title']: m for m in kodi.rpc('VideoLibrary.GetMovies', {'properties': ['title', 'runtime']})['movies']}
    for title, part in (('Blade Runner 2049', 0.42), ('Ghost in the Shell', 0.68), ('Arrival', 0.25)):
        movie = movies[title]
        kodi.rpc('VideoLibrary.SetMovieDetails', {'movieid': movie['movieid'], 'resume': {
            'position': int(movie['runtime'] * part), 'total': movie['runtime']}})
    episodes = kodi.rpc('VideoLibrary.GetEpisodes', {'properties': ['showtitle', 'episode', 'runtime']})['episodes']
    for ep in episodes:
        if (ep['showtitle'], ep['episode']) in (('Cyberpunk: Edgerunners', 1), ('Cyberpunk: Edgerunners', 2),
                                                ('Arcane', 1), ('Severance', 1)):
            kodi.rpc('VideoLibrary.SetEpisodeDetails', {'episodeid': ep['episodeid'], 'playcount': 1})
        if (ep['showtitle'], ep['episode']) == ('Severance', 2):
            kodi.rpc('VideoLibrary.SetEpisodeDetails', {'episodeid': ep['episodeid'], 'resume': {
                'position': int(ep['runtime'] * 0.3), 'total': ep['runtime']}})
    kodi.builtin('Dialog.Close(all,true)')
    kodi.builtin('ReloadSkin()')
    time.sleep(3)
    kodi.wait('Window.IsActive(home)', timeout=30)
    kodi.wait('Weather.IsFetched', timeout=30)


def home(kodi, page='home'):
    """Home with nothing playing and no dialog, on PAGE (as the e2e `home` fixture)."""
    for _ in range(5):
        if not kodi.cond('System.HasActiveModalDialog'):
            break
        kodi.action('back', delay=1)
    for player in kodi.rpc('Player.GetActivePlayers'):
        kodi.rpc('Player.Stop', {'playerid': player['playerid']})
        time.sleep(1)
    if kodi.cond('!' + TMDB_IDLE):
        kodi.builtin('SetProperty(TMDbHelper.Command,exit,home)')
        kodi.wait(TMDB_IDLE, timeout=20)
    kodi.builtin('Dialog.Close(all,true)')
    kodi.builtin('ReplaceWindow(Home)')
    kodi.wait('Window.IsActive(home)')
    entry = {'home': 9101, 'movies': 9102, 'shows': 9103, 'music': 9107}[page]
    kodi.builtin('SetFocus({})'.format(entry))
    kodi.wait('String.IsEqual(Window(Home).Property(nc.page),{})'.format(page))


def spotlight_on(kodi, container, title):
    """Move the (still) spotlight CONTAINER to TITLE."""
    kodi.wait('Integer.IsGreater(Container({}).NumItems,0) + !Container({}).IsUpdating'.format(container, container))
    total = int(kodi.info('Container({}).NumItems'.format(container)))
    for offset in range(total):
        if kodi.info('Container({}).ListItem({}).Label'.format(container, offset)) == title:
            if offset:
                kodi.builtin('Control.Move({},{})'.format(container, offset))
            kodi.wait('String.IsEqual(Container({}).ListItem.Label,{})'.format(container, title))
            return
    raise RuntimeError('{} is not in spotlight {}'.format(title, container))


def settle(kodi, seconds=3):
    """Wait for notifications, busy dialogs and TMDb Helper's lookups to end, then give the
    artwork time to load and fade in."""
    kodi.steady(QUIET, seconds=2, timeout=180)
    time.sleep(seconds)


def shot_home(kodi):
    home(kodi)
    spotlight_on(kodi, 9000, 'Blade Runner 2049')
    kodi.builtin('SetFocus(9010)')
    kodi.wait('Control.HasFocus(9010)')
    settle(kodi)


def shot_movies(kodi):
    home(kodi, 'movies')
    spotlight_on(kodi, 9000, 'Dune: Part Two')
    kodi.builtin('SetFocus(9010)')
    kodi.wait('Control.HasFocus(9010)')
    kodi.action('down', delay=1)  # the first row, on its first title
    kodi.action('right', 'right', delay=0.6)
    settle(kodi)


def matrix_info(kodi):
    movie = kodi.rpc('VideoLibrary.GetMovies', {'filter': {'field': 'title', 'operator': 'is', 'value': 'The Matrix'}})['movies'][0]
    kodi.builtin('NotifyAll(nightcity,info:movie:{})'.format(movie['movieid']))
    kodi.wait('Window.IsActive(movieinformation)', timeout=20)
    kodi.wait('String.IsEqual(Container(5500).ListItem(0).Property(param.info),cast) + '
              '!Container(5500).IsUpdating + Integer.IsGreater(Container(5500).NumItems,0)', timeout=30)


def shot_info(kodi):
    home(kodi)
    matrix_info(kodi)
    settle(kodi, 4)


def shot_person(kodi):
    home(kodi)
    matrix_info(kodi)
    kodi.builtin('SetFocus(5500,0,absolute)')
    kodi.action('select')
    kodi.wait('String.IsEqual(Window(Home).Property(TMDbHelper.Position),2)', timeout=30)
    kodi.wait('Window.IsActive(movieinformation)', timeout=20)
    kodi.wait('!Container(5510).IsUpdating + Integer.IsGreater(Container(5510).NumItems,0)', timeout=30)
    # the films come newest first, the announced ones without a poster yet: past the first
    # screen to the first nine with posters in a row, the focus to the last of them scrolls them
    # in, then back into their middle
    posters = [bool(kodi.info('Container(5510).ListItemAbsolute({}).Art(poster)'.format(i)))
               for i in range(int(kodi.info('Container(5510).NumItems')))]
    last = next((i for i in range(9, len(posters)) if all(posters[i - 8:i + 1])), 0)
    kodi.builtin('SetFocus(5510,{},absolute)'.format(last))
    kodi.wait('Control.HasFocus(5510)')
    time.sleep(1)
    kodi.action('left', 'left', 'left', 'left', delay=0.5)
    settle(kodi, 4)


def shot_player(kodi):
    home(kodi)
    movie = kodi.rpc('VideoLibrary.GetMovies', {'filter': {'field': 'title', 'operator': 'is', 'value': 'Blade Runner 2049'}})['movies'][0]
    kodi.rpc('Player.Open', {'item': {'movieid': movie['movieid']}})
    kodi.wait('Player.HasVideo + Window.IsActive(fullscreenvideo)', timeout=30)
    kodi.wait('!Window.IsVisible(busydialog)', timeout=30)
    time.sleep(2)
    # the resume point prepare() set; stopping there later keeps it
    kodi.rpc('Player.Seek', {'playerid': 1, 'value': {'percentage': 42}})
    kodi.wait('Integer.IsGreater(Player.Progress,30)')  # to the keyframe before
    time.sleep(2)
    kodi.action('pause', delay=1)
    kodi.wait('Player.Paused + Window.IsActive(videoosd)')
    settle(kodi)


def shot_music(kodi):
    home(kodi, 'music')
    spotlight_on(kodi, 9002, 'Pulse City')
    settle(kodi)


def shot_settings(kodi):
    """The settings console: the first group tile of the settings page opens its rail."""
    home(kodi)
    kodi.builtin('SetProperty(nc.page,system,home)')
    kodi.builtin('SetFocus(9601,0,absolute)')
    kodi.wait('Control.HasFocus(9601)')
    kodi.action('select', delay=1)
    kodi.wait('Window.IsActive(settings) + Control.HasFocus(9211)')
    settle(kodi)


def shot_quick(kodi):
    home(kodi)
    spotlight_on(kodi, 9000, 'TRON: Legacy')
    kodi.builtin('SetFocus(9109)')
    kodi.wait('Control.HasFocus(9109)')
    time.sleep(0.5)
    kodi.action('down')
    settle(kodi)


SHOTS = {  # name: (file, take)
    'home': ('01-home', shot_home),
    'movies': ('02-movies', shot_movies),
    'info': ('03-info', shot_info),
    'person': ('04-person', shot_person),
    'player': ('05-player', shot_player),
    'music': ('06-music', shot_music),
    'settings': ('07-settings', shot_settings),
    'quick': ('08-quick-menu', shot_quick),
}


def save(png, target, png_dir=None):
    from PIL import Image
    target.parent.mkdir(parents=True, exist_ok=True)
    image = Image.open(png).convert('RGB').resize(SHIP_SIZE, Image.LANCZOS)
    image.save(target, 'JPEG', quality=JPEG_QUALITY, optimize=True, progressive=True)
    if png_dir:
        pathlib.Path(png_dir).mkdir(parents=True, exist_ok=True)
        shutil.copy(png, pathlib.Path(png_dir) / (target.stem + '.png'))
    print('screenshots: {} ({} KB)'.format(target.relative_to(ROOT) if target.is_relative_to(ROOT) else target,
                                           target.stat().st_size // 1024))


def restart(kodi):
    kodi.kdev('restart')
    kodi.kdev('wait')
    kodi.wait('Window.IsActive(home)', timeout=60)
    # jellyfin-kodi may ask to resume its sync a few seconds after the start: Back answers no
    end = time.time() + 15
    while time.time() < end:
        if kodi.cond('System.HasActiveModalDialog'):
            kodi.action('back', delay=1)
        time.sleep(0.5)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('shots', nargs='*', metavar='SHOT', help='only these: ' + ' '.join(SHOTS))
    parser.add_argument('--instance', help='use this running instance (one a run with --keep left)')
    parser.add_argument('--keep', action='store_true', help='keep the instance this run starts')
    parser.add_argument('--skin', choices=('nightcity', 'confuse'), default='nightcity')
    parser.add_argument('--out', help='default: the resources/screenshots of the skin')
    parser.add_argument('--png', help='also save the full PNGs in this folder')
    args = parser.parse_args(argv)
    if not args.out:
        overlay = ROOT if args.skin == 'nightcity' else ROOT / 'skins' / args.skin
        args.out = str(overlay / 'resources' / 'screenshots')
    unknown = set(args.shots) - set(SHOTS)
    if unknown:
        parser.error('unknown shots: {} (known: {})'.format(' '.join(sorted(unknown)), ' '.join(SHOTS)))
    return args


def main():
    args = parse_args()
    own = not args.instance
    name = args.instance or 'shots'
    if own:
        start_instance(name, args.skin)
    kodi = Kodi(name)
    if not kodi.up():
        raise SystemExit('kodi-dev instance {} is not running'.format(name))
    if own and args.skin != 'nightcity':
        # the template knows the overlay as disabled or not at all: Kodi has gone to Estuary
        kodi.rpc('Addons.SetAddonEnabled', {'addonid': 'skin.' + args.skin, 'enabled': True})
        restart(kodi)
    if own:
        kdev = load_kdev()
        kdev.use_instance(name)
        write_media(kodi.data / 'media')
        jellyfin_showcase(kdev, kodi)
    titles = {m['label'] for m in kodi.rpc('VideoLibrary.GetMovies').get('movies', [])}
    if not {title for title, _, _ in MOVIES} <= titles:
        raise SystemExit('instance {} has no showcase library: run without --instance'.format(name))
    if not kodi.info('System.ScreenResolution').startswith(SIZE):
        print('screenshots: instance {} runs at {}, not {}'.format(name, kodi.info('System.ScreenResolution'), SIZE))
    keys = {setting: os.environ[env] for env, setting in KEYS.items() if os.environ.get(env)}
    print('screenshots: ratings keys from the environment: {}'.format(
        ', '.join(env for env in KEYS if os.environ.get(env)) or 'none, TMDb ratings only'))
    before = None
    try:
        if keys:
            before = set_keys(kodi, keys)
            restart(kodi)
        prepare(kodi)
        for shot in args.shots or SHOTS:
            file, take = SHOTS[shot]
            take(kodi)
            save(kodi.screenshot('nc-' + file), pathlib.Path(args.out) / (file + '.jpg'), args.png)
        home(kodi)
    finally:
        if own and not args.keep:
            remove_instance(name)
        elif before is not None:
            set_keys(kodi, before)
            print('screenshots: TMDb Helper keys of {} set back; Kodi reads them on its next start'.format(name))


if __name__ == '__main__':
    main()
