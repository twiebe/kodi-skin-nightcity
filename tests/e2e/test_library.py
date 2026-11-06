import re
import time

import pytest

from conftest import action, builtin, cond, info, rpc, screenshot, seed, wait_for

pytestmark = pytest.mark.e2e

LIST, WALL = 50, 51


@pytest.fixture
def movies(home):
    builtin('ActivateWindow(Videos,videodb://movies/titles/,return)')
    wait_for('Window.IsActive(videos)')
    wait_for('Integer.IsGreater(Container.NumItems,0)')
    yield
    builtin('Container.SetViewMode({})'.format(LIST))


def focus_first_movie():
    builtin('SetFocus({},0,absolute)'.format(current_view()))
    if cond('ListItem.IsParentFolder')['ListItem.IsParentFolder']:
        action('down')


def current_view():
    for view in (LIST, WALL):
        if cond('Control.IsVisible({})'.format(view))['Control.IsVisible({})'.format(view)]:
            return view
    raise AssertionError('no library view visible')


def test_movies_list_view(movies):
    assert current_view() in (LIST, WALL)
    assert int(info('Container.NumItems')['Container.NumItems']) > 0
    screenshot('library-list')


def test_view_switch(movies):
    for view in (WALL, LIST):
        builtin('Container.SetViewMode({})'.format(view))
        wait_for('Control.IsVisible({})'.format(view))
        if view == WALL:
            screenshot('library-wall')


def test_info_dialog(movies):
    focus_first_movie()
    action('info', delay=1)
    try:
        wait_for('Window.IsActive(DialogVideoInfo.xml)')
        assert info('ListItem.Title')['ListItem.Title']
        screenshot('video-info')
    finally:
        action('back', delay=1)


def test_play_from_info(movies):
    focus_first_movie()
    action('info', delay=1)
    wait_for('Window.IsActive(DialogVideoInfo.xml)')
    # Control.* booleans over JSON-RPC look at the window below the dialog, so rely on the
    # dialog's default control (8, play) instead of checking focus.
    action('select', delay=1)
    try:
        wait_for('Player.HasVideo', timeout=20)
    finally:
        if rpc('Player.GetActivePlayers'):
            rpc('Player.Stop', {'playerid': 1})
            time.sleep(1)


def test_view_button_switches_to_wall(movies):
    """Review I5: the poster wall is reachable from the remote via the view button (2)."""
    builtin('Container.SetViewMode({})'.format(LIST))
    wait_for('Control.IsVisible({})'.format(LIST))
    builtin('SetFocus({},1,absolute)'.format(LIST))
    action('right')
    assert info('System.CurrentControlId')['System.CurrentControlId'] == '2'
    action('select', delay=1)
    wait_for('Control.IsVisible({})'.format(WALL))


def test_videonav_path_line(movies):
    """The window title is a path line; the n/N counter sits on its right, not in a frame line."""
    path, counter = (info('Control.GetLabel({})'.format(i))['Control.GetLabel({})'.format(i)] for i in (9026, 9028))
    assert re.sub(r'\[/?[A-Z]+[^\]]*\]', '', path).strip(), path
    assert re.fullmatch(r'\d+/\d+', counter), counter
    screenshot('videonav')


@pytest.mark.parametrize('view, step', ((LIST, 'down'), (WALL, 'right')))
def test_click_opens_the_info_page_of_an_item_of_the_jellyfin_addon(home, view, step):
    """A listing of the add-on (a playlist, its dynamic views), with a show synced: its root is then
    a tvshows path, and Kodi ignores the info action on anything below that. Play on the page plays
    the file: an item outside the library has no database id."""
    library = seed()['libraries']['Movies']
    builtin('ActivateWindow(Videos,plugin://plugin.video.jellyfin/?mode=browse&type=movies&id={0}&folder={0},return)'.format(library))
    wait_for('Window.IsActive(videos) + Integer.IsGreater(Container.NumItems,0)')
    builtin('Container.SetViewMode({})'.format(view))
    wait_for('Control.IsVisible({})'.format(view))
    builtin('SetFocus({},0,absolute)'.format(view))
    if cond('ListItem.IsParentFolder')['ListItem.IsParentFolder']:
        action(step)
    wait_for('String.IsEqual(ListItem.Property(IsPlayable),true)')
    try:
        action('select')
        wait_for('Window.IsActive(movieinformation)')
        wait_for('String.IsEmpty(ListItem.DBID)')
        wait_for('Control.HasFocus(9001)')
        action('select')
        wait_for('Player.HasVideo', timeout=20)
    finally:
        if rpc('Player.GetActivePlayers'):
            rpc('Player.Stop', {'playerid': 1})
            time.sleep(1)
        builtin('Dialog.Close(movieinformation,true)')
        builtin('Container.SetViewMode({})'.format(LIST))


def test_click_plays_a_track_of_the_jellyfin_addon(home):
    """Kodi has no info page for a track in the Videos window, select would do nothing."""
    album = seed()['items']['Blue Satellite']
    builtin('ActivateWindow(Videos,plugin://plugin.video.jellyfin/?mode=browse&type=songs&folder={},return)'.format(album))
    wait_for('Window.IsActive(videos) + Integer.IsGreater(Container.NumItems,0)')
    builtin('Container.SetViewMode({})'.format(LIST))
    wait_for('Control.IsVisible({})'.format(LIST))
    builtin('SetFocus({},0,absolute)'.format(LIST))
    if cond('ListItem.IsParentFolder')['ListItem.IsParentFolder']:
        action('down')
    wait_for('!ListItem.IsParentFolder')
    try:
        action('select')
        wait_for('Player.HasAudio', timeout=20)
    finally:
        if rpc('Player.GetActivePlayers'):
            rpc('Player.Stop', {'playerid': 0})
            time.sleep(1)
