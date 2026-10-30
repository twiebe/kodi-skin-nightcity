"""Endless TMDb navigation through TMDb Helper's window manager, end to end.

Needs plugin.video.themoviedb.helper, internet access for TMDb, and a library movie TMDb knows
(The Matrix, 1999, with its IMDb number). Without them the tests are skipped.
"""
import re
import time

import pytest

from conftest import _data, action, builtin, cond, info, kodi_log, rpc, screenshot, wait_for

pytestmark = pytest.mark.e2e

RUNNING = '!String.IsEmpty(Window(Home).Property(TMDbHelper.Instance))'
IDLE = 'String.IsEmpty(Window(Home).Property(TMDbHelper.Instance))'


def _true(condition):
    return cond(condition)[condition]


def _page(position):
    wait_for('String.IsEqual(Window(Home).Property(TMDbHelper.Position),{})'.format(position), timeout=30)
    wait_for('Window.IsActive(movieinformation)', timeout=20)
    time.sleep(1.5)


PYTHON_RUN = re.compile(r'CPythonInvoker\((\d+), ([^)]*)\): start processing|onExecutionDone\((\d+), ')


def _log():
    return _data() / 'kodi' / 'temp' / 'kodi.log'


def _log_since(offset):
    with open(_log(), 'rb') as f:
        f.seek(offset)
        return f.read().decode(errors='replace')


def _python_running():
    """Ids of TMDb Helper's list plugins that started in Kodi's log and have not ended yet. The
    skin's commands run in its service, which never ends, like other services."""
    text = _log_since(max(0, _log().stat().st_size - 4000000))
    running = set()
    for m in PYTHON_RUN.finditer(text):
        if m.group(1) and 'themoviedb.helper/resources/plugin.py' in m.group(2):
            running.add(m.group(1))
        elif m.group(3):
            running.discard(m.group(3))
    return running


def _settle(timeout=20):
    """Wait until no Python starts behind the test's back: after a chain the OSD holds its cast
    row's plugin until a second after the manager ended (nc_osd_chain), and TMDb Helper's list
    plugins may still run. A test that starts the next info page at that moment has two
    interpreters start at once, which crashes Kodi."""
    wait_for(IDLE, timeout=timeout)
    wait_for('String.IsEmpty(Window(Home).Property(nc.osd.chain))', timeout=5)
    _quiet(timeout)


def _quiet(timeout=20):
    end = time.time() + timeout
    quiet = 0
    while quiet < 2:  # twice in a row: a timer's script shows up in the log a moment late
        if time.time() > end:
            raise AssertionError('Python still running: {}'.format(sorted(_python_running())))
        time.sleep(0.4)
        quiet = quiet + 1 if not _python_running() else 0


def _list_in(cid, timeout=30):
    """A TMDb list of the page holds its items and nothing loads. The info page keeps its lists
    between pages: a list that loads again still holds the items of before (NumItems) while it
    reads IsUpdating, and a click on it then does nothing (ChainClick waits for
    !IsUpdating). Its plugin may start a moment after the page opened, so no plugin may run."""
    wait_for('Integer.IsGreater(Container({}).NumItems,0)'.format(cid), timeout=timeout)
    _quiet(timeout)
    wait_for('!Container({}).IsUpdating + Integer.IsGreater(Container({}).NumItems,0)'.format(cid, cid))


def _leave_chain():
    if _true(RUNNING):
        builtin('SetProperty(TMDbHelper.Command,exit,home)')
        wait_for(IDLE, timeout=20)


@pytest.fixture
def matrix(home):
    addons = rpc('Addons.GetAddons', {'type': 'xbmc.python.pluginsource', 'enabled': True})['addons']
    if 'plugin.video.themoviedb.helper' not in [a['addonid'] for a in addons]:
        pytest.skip('TMDb Helper not installed')
    movies = rpc('VideoLibrary.GetMovies', {'filter': {'field': 'title', 'operator': 'is', 'value': 'The Matrix'}})
    if not movies.get('movies'):
        pytest.skip('The Matrix not in the library')
    _settle()  # Home's onload started its script
    yield movies['movies'][0]['movieid']
    _leave_chain()
    if rpc('Player.GetActivePlayers'):
        offset = _log().stat().st_size
        rpc('Player.Stop', {'playerid': 1})
        # Jellyfin for Kodi takes the played movie's new state a few seconds later; the library
        # update that follows reloads every list, a click of the next test in it does nothing
        end = time.time() + 20
        while time.time() < end:
            text = _log_since(offset)
            sync = text.find('jellyfin_kodi/library.py:553 --[ sync/')
            if sync >= 0 and 'CRecentlyAddedJob::UpdateVideos' in text[sync:]:
                break
            time.sleep(0.5)
        time.sleep(1)
    # the OSD's script runs as long as the OSD is open, the info script as long as its page: a
    # test that ends with them open would wait for nothing
    builtin('Dialog.Close(all,true)')
    _settle()


def test_info_cast_opens_person_then_movie_and_back(matrix):
    builtin('NotifyAll(nightcity,info:movie:{})'.format(matrix))
    wait_for('Window.IsActive(movieinformation)', timeout=20)
    _list_in('5500')
    builtin('SetFocus(5500)')
    person = info('Container(5500).ListItem.Label')['Container(5500).ListItem.Label']
    action('select')
    _page(2)  # the library page is the chain's origin
    assert info('ListItem.Label')['ListItem.Label'] == person
    _list_in('5510')
    screenshot('tmdb-person')
    builtin('SetFocus(5510)')
    title = info('Container(5510).ListItem.Label')['Container(5510).ListItem.Label']
    action('select')
    _page(3)
    assert info('ListItem.Property(tmdb_type)')['ListItem.Property(tmdb_type)'] == 'movie'
    assert info('ListItem.Label')['ListItem.Label'] in title  # unreleased titles come coloured
    action('back')
    _page(2)
    action('back')
    _page(1)
    assert info('ListItem.DBID')['ListItem.DBID'] == str(matrix)


def _open_cast_row():
    action('osd', delay=1.5)
    assert _true('Window.IsActive(videoosd)')
    action('down', delay=0.3)
    assert _true('Window.IsActive(videobookmarks)')
    # a movie without chapters: the row focuses its buttons
    wait_for("Control.HasFocus(11) | Control.HasFocus(2)")
    action('down', delay=1)
    wait_for('Window.IsActive(1141)')
    wait_for('Integer.IsGreater(Container(6501).NumItems,0)', timeout=30)


def _play(movieid):
    rpc('Player.Open', {'item': {'movieid': movieid}, 'options': {'resume': False}})
    wait_for('Player.HasVideo', timeout=20)
    wait_for('Window.IsActive(fullscreenvideo)')


def test_osd_cast_row_to_person_and_close_all_returns_to_video(matrix):
    _play(matrix)
    _open_cast_row()
    # the biography follows the focus once it rested
    wait_for('String.IsEqual(Container(6599).ListItem.Property(tmdb_id),Container(6501).ListItem.Property(tmdb_id))', timeout=20)
    screenshot('tmdb-osd-cast')
    person = info('Container(6501).ListItem.Label')['Container(6501).ListItem.Label']
    action('select')
    _page(1)
    assert info('ListItem.Label')['ListItem.Label'] == person
    assert not _true('Window.IsActive(videoosd)')
    assert _true('Player.Playing')  # playback keeps running behind the chain
    assert 'back to video' in info('Control.GetLabel(9004)')['Control.GetLabel(9004)'].lower()
    builtin('SetFocus(9004)')
    action('select')
    wait_for(IDLE, timeout=20)
    wait_for('Window.IsActive(fullscreenvideo)', timeout=10)
    assert _true('Player.Playing')


def test_osd_cast_row_click_while_the_biography_loads(matrix):
    """OK in the second the focused person's biography loads used to do nothing: it waits for
    the biography and then opens the person."""
    _play(matrix)
    _open_cast_row()
    wait_for('String.IsEqual(Container(6599).ListItem.Property(tmdb_id),Container(6501).ListItem.Property(tmdb_id))', timeout=20)
    action('right', delay=0)
    person = info('Container(6501).ListItem.Label')['Container(6501).ListItem.Label']
    wait_for('Container(6599).IsUpdating', timeout=10)
    action('select', delay=0)
    _page(1)
    assert info('ListItem.Label')['ListItem.Label'] == person
    assert not _true('Window.IsActive(1141)')


def _info_and_person(matrix, crew_index=None):
    """The Matrix's info page, then the page of a person in its cast (or crew_index in its crew)."""
    builtin('NotifyAll(nightcity,info:movie:{})'.format(matrix))
    wait_for('Window.IsActive(movieinformation)', timeout=20)
    # the list may still hold the items of the page or tab before (TmdbFresh5500), and reloads
    # only a moment after the tab switched: wait for items of the right request, a click while
    # the list loads does nothing
    loaded = ('String.IsEqual(Container(5500).ListItem(0).Property(param.info),{}) + '
              '!Container(5500).IsUpdating + Integer.IsGreater(Container(5500).NumItems,0)')
    wait_for(loaded.format('cast'), timeout=30)
    if crew_index is not None:
        builtin('SetFocus(5522)')
        action('select', delay=0.5)
        wait_for('String.IsEqual(Window(Home).Property(nc.info.tab),crew) + ' + loaded.format('crew'), timeout=30)
    builtin('SetFocus(5500,{},absolute)'.format(crew_index or 0))
    action('select')
    _page(2)
    wait_for('!Container(5510).IsUpdating', timeout=30)


def test_credits_tab_applies_on_focus(matrix):
    """DESIGN.md: focus applies. Right from cast to crew shows the crew without OK, Left the
    cast again; a choice made while the list loads follows once it is in."""
    builtin('NotifyAll(nightcity,info:movie:{})'.format(matrix))
    wait_for('Window.IsActive(movieinformation)', timeout=20)
    loaded = ('String.IsEqual(Container(5500).ListItem(0).Property(param.info),{}) + '
              '!Container(5500).IsUpdating + Integer.IsGreater(Container(5500).NumItems,0)')
    wait_for(loaded.format('cast'), timeout=30)
    builtin('SetFocus(5521)')
    wait_for('Control.HasFocus(5521)')
    action('right', delay=0)
    wait_for('String.IsEqual(Window(Home).Property(nc.info.tab),crew) + ' + loaded.format('crew'), timeout=30)
    screenshot('tmdb-crew-on-focus')
    action('left', delay=0)
    wait_for('String.IsEqual(Window(Home).Property(nc.info.tab),cast) + ' + loaded.format('cast'), timeout=30)
    assert _true('Control.HasFocus(5521)')


def test_person_tabs_apply_on_focus_after_back_from_a_title(matrix):
    """Back from a title page whose recommendations still loaded left them hidden and updating
    on the person page; every tab then waited for them (TmdbBusy) and needed OK."""
    _info_and_person(matrix)
    _list_in(5510)
    builtin('SetFocus(5510,0,absolute)')
    action('select')
    _page(3)
    action('back', delay=0)
    wait_for('Window.IsActive(movieinformation) + String.IsEqual(ListItem.Property(tmdb_type),person)', timeout=30)
    _list_in(5510)
    builtin('SetFocus(5523)')
    wait_for('Control.HasFocus(5523)')
    action('right', delay=0)
    wait_for('String.IsEqual(Window(Home).Property(nc.info.tab),tv) + '
             'String.IsEqual(Container(5510).ListItem(0).Property(param.info),stars_in_tvshows)', timeout=30)


def test_person_without_films_still_reaches_the_tabs(matrix):
    """A crew member with no films (The Matrix's colour timer): Down from the buttons used to do
    nothing, the tabs with the crew jobs were out of reach."""
    _info_and_person(matrix, crew_index=43)
    assert info('Container(5510).NumItems')['Container(5510).NumItems'] == '0'
    action('down', delay=1)
    assert _true('ControlGroup(5520).HasFocus()')
    screenshot('tmdb-person-without-films')
    builtin('SetFocus(5525)')
    action('select', delay=0.5)
    assert _true('Control.HasFocus(5525)')  # the list is empty yet: the focus stays on the tab
    # once the jobs are in, the focus goes down to them by itself (nc_info_enter)
    wait_for('Integer.IsGreater(Container(5510).NumItems,0) + !Container(5510).IsUpdating', timeout=30)
    wait_for('Control.HasFocus(5510)', timeout=2)


def test_back_right_after_a_page_opens_goes_one_page_back(matrix):
    """Back in the moment a page appears used to leave TMDb Helper waiting 30 s on an empty
    backdrop and then end the chain. The page holds Back for a second and then goes back."""
    _info_and_person(matrix)
    wait_for('Integer.IsGreater(Container(5510).NumItems,0)', timeout=30)
    builtin('SetFocus(5510,0,absolute)')
    action('select', delay=0)
    wait_for('Window.IsActive(movieinformation) + String.IsEqual(ListItem.Property(tmdb_type),movie)', timeout=30)
    action('back', delay=0)
    assert _true('Window.IsActive(movieinformation)')  # held
    wait_for('String.IsEqual(Window(Home).Property(TMDbHelper.Position),2)', timeout=10)
    wait_for('Window.IsActive(movieinformation) + String.IsEqual(ListItem.Property(tmdb_type),person)', timeout=10)
    assert _true(RUNNING)


def test_escape_right_after_a_page_opens_goes_one_page_back(matrix):
    """Esc on a keyboard, and Back on many remotes, is PreviousMenu, not Back: <onback> never
    sees it, so it closed the page before TMDb Helper's manager looked and the chain hung 30 s."""
    _info_and_person(matrix)
    wait_for('Integer.IsGreater(Container(5510).NumItems,0)', timeout=30)
    builtin('SetFocus(5510,0,absolute)')
    action('select', delay=0)
    wait_for('Window.IsActive(movieinformation) + String.IsEqual(ListItem.Property(tmdb_type),movie)', timeout=30)
    rpc('Input.ButtonEvent', {'button': 'escape', 'keymap': 'KB'})  # through the keymaps
    time.sleep(0.1)
    assert _true('Window.IsActive(movieinformation)')  # held
    wait_for('String.IsEqual(Window(Home).Property(TMDbHelper.Position),2)', timeout=10)
    wait_for('Window.IsActive(movieinformation) + String.IsEqual(ListItem.Property(tmdb_type),person)', timeout=10)
    assert _true(RUNNING)


def test_home_key_in_a_chain_ends_it_on_home(matrix):
    """The key asks the manager to exit, then goes Home a second after it ended (nc_home_key):
    closing the info page under the manager looked like Back to it, and it brought the page
    before back over Home. Home's script then starts alone, two interpreters at once crashed
    Kodi."""
    _info_and_person(matrix)
    builtin('ActivateWindow(1160)')
    wait_for(IDLE, timeout=20)
    wait_for('String.IsEmpty(Window(Home).Property(nc.home.key))', timeout=5)
    wait_for('Window.IsActive(home) + !System.HasActiveModalDialog + String.IsEqual(Window(Home).Property(nc.page),home)', timeout=10)
    time.sleep(2)  # the manager must not bring a page back
    assert _true('Window.IsActive(home) + !Window.IsActive(movieinformation)')
    assert rpc('JSONRPC.Ping') == 'pong'  # Kodi survived both interpreters


def test_quick_menu_link_in_a_chain_ends_it_first(matrix):
    """A link of the quick menu goes through the Home key window (nc.go): the chain ends first,
    then the link's window opens and no info page comes back over it."""
    _info_and_person(matrix)
    builtin('SetProperty(nc.go,files,home)')
    builtin('ActivateWindow(1160)')
    wait_for(IDLE, timeout=20)
    wait_for('Window.IsActive(filemanager) + !System.HasActiveModalDialog', timeout=10)
    time.sleep(2)  # the manager must not bring a page back
    assert _true('Window.IsActive(filemanager) + !Window.IsActive(movieinformation)')
    assert not info('Window(Home).Property(nc.go)')['Window(Home).Property(nc.go)']
    action('back', delay=1)


def _plugin_starts():
    """Times (s) of the TMDb Helper plugin starts in this Kodi run, with their query."""
    import re
    starts = []
    for line in kodi_log('running add-on script TMDb Helper').splitlines():
        m = re.match(r"\S+ (\d+):(\d+):([\d.]+) .*TMDb Helper\('[^']*', '[^']*', '\?(info=\w+)", line)
        if m:
            starts.append((int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)), m.group(4)))
    return starts


def test_title_page_starts_its_lists_one_after_another(matrix):
    """A title page opened after another one: its cast list still held the cast of the page
    before, so the similar movies started together with the cast, two interpreters at once."""
    _info_and_person(matrix)
    wait_for('Integer.IsGreater(Container(5510).NumItems,0)', timeout=30)
    # kdev log shows the last matches only: compare times, not counts
    before = max([t for t, _ in _plugin_starts()] or [0])
    builtin('SetFocus(5510,0,absolute)')
    action('select')
    _page(3)
    wait_for('Integer.IsGreater(Container(5300).NumItems,0) + !Container(5300).IsUpdating', timeout=45)
    starts = [(t, name) for t, name in _plugin_starts() if t > before]
    infos = [name for _, name in starts]
    assert 'info=cast' in infos and 'info=recommendations' in infos, starts
    times = [t for t, _ in starts]
    # before, both started in the same millisecond
    assert all(b - a > 0.05 for a, b in zip(times, times[1:])), starts


def test_click_right_after_leaving_a_chain_opens_the_next(matrix):
    """The claim against a second manager start outlived a short chain by seconds: a person
    clicked right after a chain was closed did not open."""
    _info_and_person(matrix)  # loads the cast and the person into TMDb Helper's cache
    builtin('SetProperty(TMDbHelper.Command,exit,home)')
    _settle()  # Home's held script
    wait_for('String.IsEmpty(Window(Home).Property(nc.chain.claim))', timeout=10)
    builtin('NotifyAll(nightcity,info:movie:{})'.format(matrix))
    wait_for('Window.IsActive(movieinformation) + Integer.IsGreater(Container(5500).NumItems,0) + !Container(5500).IsUpdating', timeout=20)
    builtin('SetFocus(5500,0,absolute)')
    action('select', delay=0)
    wait_for(RUNNING, timeout=10)  # a short chain: page, then close all
    _page(2)
    builtin('SetProperty(TMDbHelper.Command,exit,home)')
    _settle()
    started = time.time()
    builtin('NotifyAll(nightcity,info:movie:{})'.format(matrix))
    wait_for('Window.IsActive(movieinformation) + Integer.IsGreater(Container(5500).NumItems,0) + !Container(5500).IsUpdating', timeout=20)
    assert time.time() - started < 5, 'too slow to show it'
    builtin('SetFocus(5500,1,absolute)')
    action('select')
    _page(2)


def test_back_button_names_the_page_and_waits_at_the_left(matrix):
    """Started from the movies page, back all the way says so. On a title page it stands left of
    the play button and takes the focus only with Left."""
    builtin('SetFocus(9102)')
    wait_for('String.IsEqual(Window(Home).Property(nc.page),movies)')
    _info_and_person(matrix)
    assert 'back to movies' in info('Control.GetLabel(9004)')['Control.GetLabel(9004)'].lower()
    wait_for('Integer.IsGreater(Container(5510).NumItems,0)', timeout=30)
    builtin('SetFocus(5510,0,absolute)')
    action('select')
    _page(3)
    wait_for('Control.IsVisible(9004)')
    focused = info('System.CurrentControlId')['System.CurrentControlId']
    assert focused and focused != '9004' and _true('ControlGroup(9000).HasFocus()'), focused
    for _ in range(4):
        if _true('Control.HasFocus(9004)'):
            break
        action('left', delay=0.3)
    assert _true('Control.HasFocus(9004)')
    action('select')
    wait_for(IDLE, timeout=20)
    wait_for('Window.IsActive(home) + String.IsEqual(Window(Home).Property(nc.page),movies)', timeout=10)


def test_walking_back_out_of_an_osd_chain_never_seeks(matrix):
    """Up walks back page by page; the last one ends the chain. It used to end on the bare video,
    where one Up too many jumped a chapter (or 10 minutes) ahead. The chain ends on the chapter
    row it was entered from below, so extra keys only move between the player's levels."""
    from test_level_hints import key
    _play(matrix)
    time.sleep(2)
    _open_cast_row()
    wait_for('String.IsEqual(Container(6599).ListItem.Property(tmdb_id),Container(6501).ListItem.Property(tmdb_id))', timeout=20)
    key('select')
    _page(1)
    before = rpc('Player.GetProperties', {'playerid': 1, 'properties': ['time']})['time']
    started = time.time()
    for _ in range(3):
        key('up')
        time.sleep(0.6)
    wait_for(IDLE, timeout=20)
    # the chain ends on the chapter row; an Up left over closes it onto the bar, where Up does nothing
    wait_for('Window.IsActive(videoosd)', timeout=5)
    time.sleep(1)
    after = rpc('Player.GetProperties', {'playerid': 1, 'properties': ['time']})['time']
    seconds = lambda t: t['hours'] * 3600 + t['minutes'] * 60 + t['seconds']
    assert seconds(after) - seconds(before) <= time.time() - started + 2, (before, after)


def _menu_entries():
    labels = []
    for cid in range(1001, 1041):
        key = 'Control.IsVisible({})'.format(cid)
        if not _true(key):
            break
        labels.append(info('Control.GetLabel({})'.format(cid))['Control.GetLabel({})'.format(cid)])
    return labels


def test_more_on_a_title_without_library_copy_opens_its_menu(matrix):
    """… on a TMDb title the library lacks: the title's context menu as TMDb Helper lists it,
    loaded on OK only, and the focus back on … once it closes."""
    _info_and_person(matrix)
    wait_for('Integer.IsGreater(Container(5510).NumItems,3)', timeout=30)
    before = max([t for t, _ in _plugin_starts()] or [0])
    builtin('SetFocus(5510,3,absolute)')
    action('select')
    _page(3)
    wait_for('!String.IsEmpty(ListItem.Property(tmdb_id)) + String.IsEmpty(ListItem.DBID)')
    wait_for('!Container(5500).IsUpdating + !Container(5901).IsUpdating + Control.IsVisible(9005)', timeout=30)
    time.sleep(2)
    assert not _true('Control.IsVisible(9006)')
    details = lambda: [name for t, name in _plugin_starts() if t > before].count('info=details')
    assert details() == 0  # … loads nothing before OK
    builtin('SetFocus(9005)')
    wait_for('Control.HasFocus(9005)')
    action('select')
    wait_for('Window.IsVisible(contextmenu)', timeout=20)
    labels = _menu_entries()
    assert details() == 1
    assert 'Browse lists' in labels, labels
    screenshot('more-tmdb-menu')
    action('back')
    wait_for('!Window.IsVisible(contextmenu)')
    wait_for('Control.HasFocus(9005)', timeout=3)
    # a second OK opens it at once, from the loaded list
    action('select')
    wait_for('Window.IsVisible(contextmenu)', timeout=3)
    action('back')
    wait_for('Control.HasFocus(9005)', timeout=3)


def test_back_in_the_chain_returns_to_the_person_left(matrix):
    """Back reopens the page before as a new page; it goes back to the item it was left from."""
    builtin('NotifyAll(nightcity,info:movie:{})'.format(matrix))
    wait_for('Window.IsActive(movieinformation)', timeout=20)
    wait_for('Integer.IsGreater(Container(5500).NumItems,3) + !Container(5500).IsUpdating', timeout=30)
    builtin('SetFocus(5500,2,absolute)')
    wait_for('Integer.IsEqual(Container(5500).CurrentItem,3)')
    person = info('Container(5500).ListItem.Label')['Container(5500).ListItem.Label']
    action('select')
    _page(2)
    action('back', delay=0)
    # until the list is in the focus waits out of sight (9098), never on the buttons
    seen, end = set(), time.time() + 30
    while time.time() < end:
        now = info('ListItem.DBID', 'System.CurrentControlId', 'Container(5500).CurrentItem')
        if now['ListItem.DBID'] == str(matrix):
            seen.add(now['System.CurrentControlId'])
            if now['System.CurrentControlId'] == '5500' and now['Container(5500).CurrentItem'] == '3':
                break
    assert seen <= {'9098', '5500'}, seen
    assert '5500' in seen
    assert info('Container(5500).ListItem.Label')['Container(5500).ListItem.Label'] == person


def test_back_in_the_chain_returns_to_the_crew_tab(matrix):
    builtin('NotifyAll(nightcity,info:movie:{})'.format(matrix))
    wait_for('Window.IsActive(movieinformation)', timeout=20)
    wait_for('Integer.IsGreater(Container(5500).NumItems,0) + !Container(5500).IsUpdating', timeout=30)
    builtin('SetFocus(5522)')  # crew: applies on focus
    wait_for('String.IsEqual(Container(5500).ListItem(0).Property(param.info),crew) + !Container(5500).IsUpdating + '
             'Integer.IsGreater(Container(5500).NumItems,1)', timeout=30)
    builtin('SetFocus(5500,1,absolute)')
    wait_for('Integer.IsEqual(Container(5500).CurrentItem,2)')
    person = info('Container(5500).ListItem.Label')['Container(5500).ListItem.Label']
    action('select')
    _page(2)
    action('back')
    _page(1)
    wait_for('Control.HasFocus(5500) + Integer.IsEqual(Container(5500).CurrentItem,2) + '
             'String.IsEqual(Container(5500).ListItem(0).Property(param.info),crew)', timeout=30)
    assert info('Container(5500).ListItem.Label')['Container(5500).ListItem.Label'] == person


def test_up_from_an_osd_chain_returns_to_the_person_left(matrix):
    """Up at the top of the person page ends the chain back on the cast row, on that person; it
    used to end on the chapter row."""
    _play(matrix)
    time.sleep(2)
    _open_cast_row()
    wait_for('Integer.IsGreater(Container(6501).NumItems,3) + !Container(6501).IsUpdating', timeout=20)
    builtin('SetFocus(6501,2,absolute)')
    wait_for('Integer.IsEqual(Container(6501).CurrentItem,3)')
    wait_for('String.IsEqual(Container(6599).ListItem.Property(tmdb_id),Container(6501).ListItem.Property(tmdb_id))', timeout=20)
    person = info('Container(6501).ListItem.Label')['Container(6501).ListItem.Label']
    action('select')
    _page(1)
    action('up', delay=1)
    wait_for(IDLE, timeout=20)
    wait_for('Window.IsActive(1141) + Control.HasFocus(6501) + Integer.IsEqual(Container(6501).CurrentItem,3)', timeout=20)
    assert info('Container(6501).ListItem.Label')['Container(6501).ListItem.Label'] == person
    screenshot('tmdb-osd-back-on-the-person')
