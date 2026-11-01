"""The trailer on a movie's info page (button 9008), end to end: it plays in full screen over the
page, which stays, and Back ends it on its button.

The Matrix (test_tmdb_chain.py) gets the clip of the track tests (tools/make_tracks_clip.py) as
its trailer for the time of a test.
"""
import pathlib
import subprocess
import sys
import time

import pytest

from conftest import _data, action, builtin, info, rpc, wait_for
from test_tmdb_chain import _page, _settle, matrix  # noqa: F401 (fixture)

pytestmark = pytest.mark.e2e

CLIP = '/home/kodi/.kodi/media/nc-tracks.mkv'
OVER_THE_PAGE = ('Window.IsActive(movieinformation) + !Window.IsActive(fullscreenvideo) + '
                 '!String.IsEmpty(Window(Home).Property(nc.trailer)) + Control.IsVisible(9095)')


@pytest.fixture
def trailer(matrix):  # noqa: F811
    clip = _data() / 'kodi' / 'media' / 'nc-tracks.mkv'  # this Kodi's, also on a pool worker
    if not clip.is_file():
        clip.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, str(pathlib.Path(__file__).parents[2] / 'tools' / 'make_tracks_clip.py'),
                        str(clip)], check=True)
    before = rpc('VideoLibrary.GetMovieDetails', {'movieid': matrix, 'properties': ['trailer']})['moviedetails']['trailer']
    rpc('VideoLibrary.SetMovieDetails', {'movieid': matrix, 'trailer': CLIP})
    yield matrix
    if rpc('Player.GetActivePlayers'):
        rpc('Player.Stop', {'playerid': 1})
        wait_for('!Player.HasMedia', timeout=10)
    rpc('VideoLibrary.SetMovieDetails', {'movieid': matrix, 'trailer': before})


def _back_on_the_button(timeout=10):
    """The trailer is over and the focus on its button; else say where the focus is."""
    try:
        wait_for('Window.IsActive(movieinformation) + Control.HasFocus(9008) + !Control.IsVisible(9095)', timeout=timeout)
    except AssertionError:
        raise AssertionError('not back on the trailer button: {}'.format(info(
            'System.CurrentWindow', 'System.CurrentControlId', 'Player.HasVideo', 'ListItem.Label',
            'Window(Home).Property(nc.trailer)', 'Window(Home).Property(TMDbHelper.Position)')))


def _open(movieid):
    builtin('NotifyAll(nightcity,info:movie:{})'.format(movieid))
    wait_for('Window.IsActive(movieinformation) + Control.IsVisible(9008)', timeout=20)
    builtin('SetFocus(9008)')
    wait_for('Control.HasFocus(9008)')


def test_trailer_plays_over_the_page_and_back_ends_it_on_its_button(trailer):
    _open(trailer)
    action('select', delay=0)
    wait_for('Player.HasVideo + ' + OVER_THE_PAGE, timeout=20)
    assert info('System.CurrentControlId')['System.CurrentControlId'] == '9099'
    time.sleep(1)
    # OK pauses, OK again plays on
    action('select')
    wait_for('Player.Paused + ' + OVER_THE_PAGE)
    action('select')
    wait_for('!Player.Paused + ' + OVER_THE_PAGE)
    action('back')
    wait_for('!Player.HasVideo + String.IsEmpty(Window(Home).Property(nc.trailer))', timeout=10)
    _back_on_the_button()
    _settle()


def test_trailer_that_ends_hands_the_page_back(trailer):
    _open(trailer)
    action('select', delay=0)
    wait_for('Player.HasVideo + ' + OVER_THE_PAGE, timeout=20)
    # the stop key, or the end of the trailer: the same for the page
    rpc('Player.Stop', {'playerid': 1})
    _back_on_the_button()
    _settle()


def test_trailer_in_a_chain_keeps_the_chain(trailer):
    """On a page of a TMDb chain the trailer plays over the page; Back ends it there, the chain
    goes on (the manager would take a closing page for Back)."""
    _open(trailer)
    wait_for('Integer.IsGreater(Container(5500).NumItems,0) + !Container(5500).IsUpdating', timeout=30)
    builtin('SetFocus(5500,0,absolute)')
    action('select')
    _page(2)
    action('back', delay=0)
    _page(1)
    wait_for('Control.IsVisible(9008)', timeout=20)
    builtin('SetFocus(9008)')
    wait_for('Control.HasFocus(9008)')
    action('select', delay=0)
    wait_for('Player.HasVideo + ' + OVER_THE_PAGE, timeout=20)
    action('back')
    wait_for('!Player.HasVideo', timeout=10)
    _back_on_the_button()
    assert info('Window(Home).Property(TMDbHelper.Position)')['Window(Home).Property(TMDbHelper.Position)'] == '1'
