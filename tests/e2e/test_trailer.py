"""The trailer on a movie's info page (button 9008), end to end: it plays in full screen over the
page, which stays, and Back ends it on its button.

The trailer is IMDb's, by the movie's IMDb id, so these tests need the internet: The Matrix
(test_tmdb_chain.py) keeps its IMDb id and loses its own trailer for the time of a test, or gets
the id of a title IMDb has no trailer of.
"""
import contextlib
import time

import pytest

from conftest import action, builtin, cond, info, rpc, wait_for
from test_tmdb_chain import _page, _settle, matrix  # noqa: F401 (fixture)

pytestmark = pytest.mark.e2e

MATRIX_IMDB = 'tt0133093'
IMDB_VIDEO_HOST = '.media-imdb.com/'
OVER_THE_PAGE = ('Window.IsActive(movieinformation) + !Window.IsActive(fullscreenvideo) + '
                 '!String.IsEmpty(Window(Home).Property(nc.trailer)) + Control.IsVisible(9095)')


@pytest.fixture
def trailer(matrix):  # noqa: F811
    """The Matrix with its IMDb id and no trailer of its own: IMDb's plays."""
    with _details(matrix, trailer='', uniqueid={'imdb': MATRIX_IMDB}):
        yield matrix


@pytest.fixture
def no_trailer(matrix):  # noqa: F811
    """The Matrix as a title IMDb has no trailer of (Carmencita, 1894), and none of its own."""
    with _details(matrix, trailer='', uniqueid={'imdb': 'tt0000001'}):
        yield matrix


@contextlib.contextmanager
def _details(movieid, **details):
    """The movie with DETAILS for the time of a test, its own back after it."""
    before = rpc('VideoLibrary.GetMovieDetails', {'movieid': movieid, 'properties': ['trailer', 'uniqueid']})['moviedetails']
    rpc('VideoLibrary.SetMovieDetails', dict(details, movieid=movieid))
    try:
        yield
    finally:
        if rpc('Player.GetActivePlayers'):
            rpc('Player.Stop', {'playerid': 1})
            wait_for('!Player.HasMedia', timeout=10)
        rpc('VideoLibrary.SetMovieDetails', {'movieid': movieid, 'trailer': before['trailer'], 'uniqueid': before['uniqueid']})


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


def test_trailer_is_imdbs(trailer):
    """IMDb's trailer of the movie, by its IMDb id: an MP4 of IMDb's video host, over the page."""
    _open(trailer)
    start = time.time()
    action('select', delay=0)
    wait_for('Player.HasVideo + ' + OVER_THE_PAGE, timeout=20)
    print('IMDb trailer playing after {:.1f} s'.format(time.time() - start))
    path = info('Player.FilenameAndPath')['Player.FilenameAndPath']
    assert path.startswith('https://') and IMDB_VIDEO_HOST in path and '.mp4' in path, path
    wait_for('Integer.IsGreater(Player.Time,0)', timeout=10)
    action('back')
    wait_for('!Player.HasVideo + String.IsEmpty(Window(Home).Property(nc.trailer))', timeout=10)
    _back_on_the_button()
    _settle()


def test_no_trailer_says_so_and_hands_the_page_back(no_trailer):
    """Neither IMDb nor the item has a trailer: a notification, the focus back on the button at
    once, no 30 s wait."""
    _open(no_trailer)
    start = time.time()
    action('select', delay=0)
    wait_for('Window.IsVisible(notification)', timeout=10)
    _back_on_the_button(timeout=5)
    assert time.time() - start < 10
    assert not cond('Player.HasVideo')['Player.HasVideo']
    _settle()
