"""Chapter row of http streams (VideoOSDBookmarks.xml): Kodi cuts no thumbnails from them. A
Jellyfin stream shows the server's chapter images, another stream Kodi's own thumbnails.

Puts the chapter clip of the track tests (tools/make_tracks_clip.py) into kodi-dev's Jellyfin
movie library and switches its chapter image extraction on."""
import json
import pathlib
import shutil
import subprocess
import sys
import time

import pytest

from conftest import _data, action, builtin, kdev, rpc, screenshot, seed, wait_for

pytestmark = pytest.mark.e2e

TITLE = 'Kdev Chapters (2003)'
REMOTE = '!String.IsEmpty(Window(Home).Property(nc.chapters.remote))'


def _jf(method, path, body=None):
    out = kdev('jf', method, path, *([json.dumps(body)] if body is not None else []))
    return json.loads(out) if out.strip() else None


def _chapter_item():
    items = _jf('GET', '/Items?Recursive=true&IncludeItemTypes=Movie&SearchTerm=Chapters&Fields=Chapters')['Items']
    return items[0] if items else None


@pytest.fixture(scope='module')
def chapter_clip():
    """Id of the clip in Jellyfin, once the server has its chapter images; removed afterwards."""
    clip = _data() / 'media' / 'movies' / TITLE / (TITLE + '.mkv')
    if not clip.is_file():
        clip.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, str(pathlib.Path(__file__).parents[2] / 'tools' / 'make_tracks_clip.py'),
                        str(clip)], check=True)
    for folder in _jf('GET', '/Library/VirtualFolders'):
        options = folder['LibraryOptions']
        if folder['Name'] == 'Movies' and not options.get('EnableChapterImageExtraction'):
            options.update(EnableChapterImageExtraction=True, ExtractChapterImagesDuringLibraryScan=True)
            _jf('POST', '/Library/VirtualFolders/LibraryOptions', {'Id': folder['ItemId'], 'LibraryOptions': options})
            _jf('POST', '/Library/Refresh')
    try:
        end = time.time() + 120
        while time.time() < end:
            item = _chapter_item()
            if item is None:
                _jf('POST', '/Library/Refresh')
            elif item.get('Chapters') and all(c.get('ImageTag') for c in item['Chapters']):
                break
            time.sleep(3)
        else:
            raise AssertionError('Jellyfin extracted no chapter images')
        yield item['Id']
    finally:
        # out of the library again: Jellyfin for Kodi syncs it into Kodi's, where it would take a
        # movie id other tests count on (test_playback.py MOVIE_ID)
        shutil.rmtree(clip.parent, ignore_errors=True)
        _jf('POST', '/Library/Refresh')


def _play(path):
    rpc('Player.Open', {'item': {'file': path}})
    wait_for('Player.HasVideo', timeout=30)
    wait_for('Window.IsActive(fullscreenvideo)')
    action('osd', delay=1)
    wait_for('Window.IsActive(VideoOSD.xml)')
    wait_for('!String.IsEmpty(Window(Home).Property(nc.chapters.file))')


def _chapter_row():
    action('down')
    wait_for('Window.IsActive(videobookmarks)')
    wait_for('Integer.IsEqual(Container(11).NumItems,3)')
    wait_for('Control.HasFocus(11)')


def _stop():
    for player in rpc('Player.GetActivePlayers'):  # a stream without extension plays as 0
        rpc('Player.Stop', {'playerid': player['playerid']})
        time.sleep(1)


def test_jellyfin_stream_shows_the_servers_chapter_images(home, chapter_clip):
    """JellyCon plays http://<server>/Videos/<id>/stream."""
    try:
        _play('plugin://plugin.video.jellycon/?item_id={}&mode=PLAY'.format(chapter_clip))
        wait_for(REMOTE)
        wait_for('String.EndsWith(Window(Home).Property(nc.chapter.1),/Items/{}/Images/Chapter/0)'.format(chapter_clip))
        wait_for('String.EndsWith(Window(Home).Property(nc.chapter.3),/Images/Chapter/2)')
        wait_for('String.IsEmpty(Window(Home).Property(nc.chapter.4))')
        _chapter_row()
        screenshot('chapters-server-images')
    finally:
        action('back', delay=1)
        _stop()


def test_jellyfin_for_kodi_stream_shows_the_servers_chapter_images(home, chapter_clip):
    """Jellyfin for Kodi in add-on mode streams (playFromStream, playutils.direct_url) this
    path; played directly here, it needs no sign-in to the add-on."""
    key = seed()['admin']['api_key']
    try:
        _play('http://jellyfin:8096/Videos/{0}/stream?static=true&MediaSourceId={0}&ApiKey={1}'.format(chapter_clip, key))
        wait_for('String.EndsWith(Window(Home).Property(nc.chapter.2),/Items/{}/Images/Chapter/1)'.format(chapter_clip))
        _chapter_row()
        screenshot('chapters-server-images-jellyfin')
    finally:
        action('back', delay=1)
        _stop()


def test_stream_without_server_images_keeps_kodis_cards(home, chapter_clip):
    """The same clip from a path the script does not know (lower case, Jellyfin does not mind):
    no server images, the 16:9 cards with Kodi's own thumbnail (Kodi cuts some from http
    streams, seen on CoreELEC)."""
    key = seed()['admin']['api_key']
    try:
        _play('http://jellyfin:8096/videos/{0}/stream.mkv?static=true&api_key={1}'.format(chapter_clip, key))
        wait_for(REMOTE + ' + String.IsEmpty(Window(Home).Property(nc.chapter.1))')
        _chapter_row()
        screenshot('chapters-kodi-thumbs')
    finally:
        action('back', delay=1)
        _stop()


def test_local_file_keeps_kodis_thumbnails(home, chapter_clip):
    local = _data() / 'kodi' / 'media' / 'nc-tracks.mkv'
    if not local.is_file():
        local.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, str(pathlib.Path(__file__).parents[2] / 'tools' / 'make_tracks_clip.py'),
                        str(local)], check=True)
    try:
        _play('/home/kodi/.kodi/media/nc-tracks.mkv')
        wait_for('String.IsEmpty(Window(Home).Property(nc.chapters.remote))')
        wait_for('String.IsEmpty(Window(Home).Property(nc.chapter.1))')
    finally:
        _stop()
