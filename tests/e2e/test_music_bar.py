"""The position bar in the music library, end to end, on the seeded library: 3 artists, 7 albums,
30 songs. Lists start with the parent folder, which belongs to no group and which CurrentItem does
not count: on it CurrentItem is 0."""
import time

import pytest

from conftest import _data, action, builtin, cond, info, rpc, screenshot, wait_for

pytestmark = pytest.mark.e2e

LABEL = 'Window(Home).Property(nc.lib.label)'
READY = '!String.IsEmpty(Window(Home).Property(nc.lib.bar))'
BAR, MENU = 5200, 9060
ARTIST, ALBUM, TITLE, TRACK, YEAR = 10, 12, 7, 8, 16


def _holds(condition):
    return cond(condition)[condition]


def _focus_is(cid, timeout=10):
    wait_for('Integer.IsEqual(System.CurrentControlId,{})'.format(cid), timeout=timeout)


def _label_is(value):
    wait_for('String.IsEqual({},{})'.format(LABEL, value), timeout=5)


def _current(view=50):
    return int(info('Container({}).CurrentItem'.format(view))['Container({}).CurrentItem'.format(view)])


def _current_is(item, view=50):
    wait_for('Integer.IsEqual(Container({}).CurrentItem,{})'.format(view, item), timeout=5)


def _sort(method):
    for _ in range(20):
        if _holds('Container.SortMethod({})'.format(method)):
            return
        before = info('Container.SortMethod')['Container.SortMethod']
        builtin('Container.NextSortMethod')
        wait_for('!String.IsEqual(Container.SortMethod,{})'.format(before), timeout=5)
    raise AssertionError('no sort {} here'.format(method))


def _open(path, sort, view=50):
    builtin('ActivateWindow(Music,{},return)'.format(path))
    wait_for('Window.IsActive(music) + String.StartsWith(Container.FolderPath,{})'.format(path), timeout=20)
    builtin('Container.SetViewMode({})'.format(view))
    wait_for('Control.IsVisible({})'.format(view))
    _sort(sort)
    wait_for('!Container({}).IsUpdating'.format(view), timeout=20)
    builtin('SetFocus({},0,absolute)'.format(view))
    _focus_is(view)


@pytest.fixture
def music(home):
    if not _holds('Library.HasContent(music)'):
        pytest.skip('no music library in this Kodi')
    # The startup writes the keymap a second into the Startup screen; a test that goes Home at once
    # is faster, so the file may be an older run's.
    wait_for('!String.IsEmpty(Window(Home).Property(nc.service))')
    builtin('NotifyAll(nightcity,home_keymap)')
    keymap = _data() / 'kodi' / 'userdata' / 'keymaps' / '0_skin.nightcity.back.xml'
    end = time.time() + 5
    while '<music>' not in keymap.read_text() and time.time() < end:
        time.sleep(0.1)
    time.sleep(0.3)  # Kodi reloads it
    yield
    builtin('Container.SetViewMode(50)')
    builtin('ActivateWindow(home)')


def _to_bar(view=50):
    action('right', delay=0.2)
    _focus_is(2)
    wait_for(READY, timeout=10)
    action('right', delay=0.2)
    _focus_is(BAR)


def _artists():
    """The first letter of each artist, as Kodi sorts them; the seeded artists differ in it."""
    _open('musicdb://artists/', ARTIST)
    count = int(info('Container(50).NumItems')['Container(50).NumItems'])
    names = ['Container(50).ListItemAbsolute({}).SortLetter'.format(i) for i in range(1, count + 1)]
    labels = info(*names)
    return [labels[name] for name in names]


def test_right_goes_list_menu_bar_and_the_parent_folder_is_no_group(music):
    letters = _artists()
    _to_bar()
    _label_is(letters[0])
    screenshot('music-bar-artists')
    _current_is(0)  # the bar does not move the list until asked


def test_down_moves_a_group_and_the_list_follows(music):
    letters = _artists()
    _to_bar()
    action('down', delay=0.2)
    _label_is(letters[1])
    _current_is(2)
    _focus_is(BAR)
    for i in range(2, len(letters)):
        action('down', delay=0.2)
        _label_is(letters[i])
        _current_is(i + 1)
    action('down', delay=0.3)  # the end stops it
    _label_is(letters[-1])


def test_ok_goes_to_the_first_title_of_the_group(music):
    letters = _artists()
    _to_bar()
    action('down', delay=0.2)
    _label_is(letters[1])
    action('select')
    _focus_is(50)
    _current_is(2)


def test_left_stays_there_by_way_of_the_menu(music):
    letters = _artists()
    _to_bar()
    action('down', delay=0.2)
    _label_is(letters[1])
    action('left', delay=0.2)
    _focus_is(2)
    _current_is(2)
    action('left', delay=0.2)
    _focus_is(50)
    _current_is(2)


def test_back_returns_to_where_it_came_from_in_the_same_folder(music):
    letters = _artists()
    action('down', delay=0.2)
    _current_is(1)
    _to_bar()
    _label_is(letters[0])
    action('down', delay=0.2)
    _label_is(letters[1])
    _current_is(2)
    action('back', delay=0.3)
    _focus_is(50)
    _current_is(1)
    assert _holds('String.IsEqual(Container.FolderPath,musicdb://artists/)')


def test_escape_on_the_bar_is_back_and_on_the_list_leaves_the_window(music):
    letters = _artists()
    _to_bar()
    action('down', delay=0.2)
    _label_is(letters[1])
    rpc('Input.ButtonEvent', {'button': 'escape', 'keymap': 'KB'})
    _focus_is(50)
    _current_is(0)
    assert _holds('Window.IsActive(music)')
    rpc('Input.ButtonEvent', {'button': 'escape', 'keymap': 'KB'})
    wait_for('!Window.IsActive(music)', timeout=5)


def test_a_later_group_lands_on_the_top_of_a_long_list(music):
    _open('musicdb://songs/', TITLE)
    _to_bar()
    first = info(LABEL)[LABEL]
    action('down', 'down', 'down', delay=0.3)
    time.sleep(0.5)
    assert info(LABEL)[LABEL] != first
    index = _current()  # with the parent folder
    assert index > 0
    # 31 rows, 16 on a page: the top row unless the end of the list is in the way
    assert int(info('Container(50).Position')['Container(50).Position']) == max(0, index - 15)
    screenshot('music-bar-songs')


def test_year_sort_names_years(music):
    _open('musicdb://albums/', YEAR)
    _to_bar()
    label = info(LABEL)[LABEL]
    assert label.isdigit() and len(label) == 4, label
    screenshot('music-bar-years')


def test_a_sort_without_groups_leaves_the_bar_out(music):
    """An album's tracks: Right stays on the menu."""
    _open('musicdb://albums/1/', TRACK)
    action('right', delay=0.2)
    _focus_is(2)
    time.sleep(1)
    action('right', delay=0.5)
    _focus_is(2)


def test_the_wall_of_cards_has_the_bar_too(music):
    _open('musicdb://albums/', ALBUM, view=51)
    builtin('SetFocus(51,5,absolute)')  # the end of the row: Right goes along the cards before that
    _current_is(5, view=51)
    _to_bar()
    first = info(LABEL)[LABEL]
    action('up', delay=0.2)
    wait_for('!String.IsEqual({},{})'.format(LABEL, first), timeout=5)
    wait_for('!Integer.IsEqual(Container(51).CurrentItem,5)', timeout=5)
    screenshot('music-bar-wall')
    action('back', delay=0.3)
    _focus_is(51)
    _current_is(5, view=51)
