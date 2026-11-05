"""The position bar of the library grid, end to end: the order grid, menu, bar; one press a group
in every sort; the grid follows; OK and Left stay there, Back returns to the card it came from.

The test library has three movies; the fixture gives them what the groups need and takes it back.
"""
import sqlite3
import time

import pytest
from PIL import Image

from conftest import _data, action, builtin, cond, info, movie_rating, rpc, screenshot, wait_for

pytestmark = pytest.mark.e2e

GRID, MENU, BAR = 5000, 5100, 5200
BULK_FROM = 1000
LABEL = 'Window(Home).Property(nc.lib.label)'
CURRENT = 'Container({}).CurrentItem'.format(GRID)
READY = '!String.IsEmpty(Window(Home).Property(nc.lib.bar))'
FIELDS = ['title', 'sorttitle', 'year', 'rating', 'dateadded']
# sort title, year, rating, date added: in that order by sort title
TITLES = [('Alpha', 1994, 8.3, '2024-02-10 10:00:00'), ('Mike', 2005, 6.1, '2025-07-01 10:00:00'),
          ('Zulu', 2020, 0.0, '2026-11-04 10:00:00')]


def _label(name):
    return info(name)[name]


def _focus_is(cid, timeout=10):
    wait_for('Integer.IsEqual(System.CurrentControlId,{})'.format(cid), timeout=timeout)


def _sort(method='', desc=False):
    builtin('Skin.SetString(nc.sort,{})'.format(method) if method else 'Skin.Reset(nc.sort)')
    if cond('Skin.HasSetting(nc.sortdesc)')['Skin.HasSetting(nc.sortdesc)'] != desc:
        builtin('Skin.ToggleSetting(nc.sortdesc)')


def _open():
    builtin('SetProperty(nc.library,movies,home)')
    builtin('ActivateWindow(1110)')
    wait_for('Window.IsActive(1110)')
    wait_for('Integer.IsEqual(Container({}).NumItems,3) + !Container({}).IsUpdating'.format(GRID, GRID), timeout=20)
    # the grid keeps its place over closing the window
    builtin('SetFocus({},0,absolute)'.format(GRID))
    _focus_is(GRID)
    _grid_on(1)


def _details(movies):
    for movie in movies:
        rpc('VideoLibrary.SetMovieDetails', movie)


def _bulk(change):
    """Run CHANGE on the video database and let the grid load anew: a sort it did not show last."""
    database = sorted((_data() / 'kodi' / 'userdata' / 'Database').glob('MyVideos*.db'))[-1]
    with sqlite3.connect(str(database), timeout=30) as connection:
        change(connection)
    connection.close()


def _remove_bulk(connection):
    for table, key in (('videoversion', 'idFile'), ('movie', 'idMovie'), ('files', 'idFile')):
        connection.execute('DELETE FROM {} WHERE {} >= ?'.format(table, key), (BULK_FROM,))


@pytest.fixture
def library(home):
    _bulk(_remove_bulk)  # a run stopped halfway leaves them behind
    before = rpc('VideoLibrary.GetMovies', {'properties': FIELDS})['movies']
    assert len(before) == 3
    _details([{'movieid': m['movieid'], 'sorttitle': t[0], 'year': t[1], 'rating': t[2], 'dateadded': t[3]}
              for m, t in zip(before, TITLES)])
    _sort()
    yield
    builtin('Dialog.Close(all,true)')
    builtin('ActivateWindow(home)')
    _sort()
    _details([{'movieid': m['movieid'], 'sorttitle': m['sorttitle'], 'year': m['year'], 'dateadded': m['dateadded']}
              for m in before])
    for m in before:
        movie_rating(m['movieid'], m['rating'])


def _to_bar():
    """From the menu, the grid staying on its card."""
    builtin('SetFocus(5101)')
    _focus_is(5101)
    wait_for(READY, timeout=10)
    action('right', delay=0.2)
    _focus_is(BAR)


def _state():
    return info('System.CurrentWindow', 'System.CurrentControlId', LABEL, CURRENT, 'Skin.String(nc.sort)')


def _label_is(value):
    try:
        wait_for('String.IsEqual({},{})'.format(LABEL, value), timeout=5)
    except AssertionError:
        raise AssertionError('label not {}: {}'.format(value, _state()))


def _grid_on(item):
    wait_for('Integer.IsEqual({},{})'.format(CURRENT, item), timeout=5)


# --- a library that scrolls: three rows of six cards on a page ------------------------------------

BULK = {'B': 20, 'C': 20, 'D': 20}  # sort titles B00..D19, between Alpha and Mike
POSITION = 'Container({}).Position'.format(GRID)  # the cursor's place on the page


def _reload(count):
    _sort('year')
    wait_for('String.IsEqual(Skin.String(nc.sort),year)', timeout=5)
    time.sleep(1)
    _sort()
    wait_for('Integer.IsEqual(Container({}).NumItems,{}) + !Container({}).IsUpdating'.format(GRID, count, GRID), timeout=20)


@pytest.fixture
def big_library(library):
    def copy(connection, table, key, values):
        """A row like the first movie's, with VALUES instead."""
        columns = [row[1] for row in connection.execute('PRAGMA table_info({})'.format(table))]
        select = ', '.join('?' if c in values else c for c in columns)
        connection.execute('INSERT INTO {} ({}) SELECT {} FROM {} WHERE {}'.format(
            table, ', '.join(columns), select, table, key), [values[c] for c in columns if c in values])

    def add(connection):
        first = connection.execute('SELECT idFile FROM movie WHERE idMovie = 1').fetchone()[0]
        number = BULK_FROM
        for letter, count in BULK.items():
            for i in range(count):
                sort = '{}{:02}'.format(letter, i)
                copy(connection, 'files', 'idFile = {}'.format(first), {'idFile': number, 'strFilename': sort + '.mkv'})
                copy(connection, 'movie', 'idMovie = 1',
                     {'idMovie': number, 'idFile': number, 'c00': 'Bulk ' + sort, 'c10': sort})
                copy(connection, 'videoversion', 'idFile = {}'.format(first), {'idFile': number, 'idMedia': number})
                number += 1
    _bulk(add)
    _open_any()
    _reload(3 + sum(BULK.values()))
    builtin('SetFocus({},0,absolute)'.format(GRID))
    _focus_is(GRID)
    yield
    _bulk(_remove_bulk)
    builtin('Dialog.Close(all,true)')
    _reload(3)


def _open_any():
    builtin('SetProperty(nc.library,movies,home)')
    builtin('ActivateWindow(1110)')
    wait_for('Window.IsActive(1110)')
    wait_for('!Container({}).IsUpdating'.format(GRID), timeout=20)


def _position():
    return int(_label(POSITION))


def _on_top_row():
    position = _position()
    assert position < 6, 'row {} of the page: {}'.format(position // 6 + 1, _state())


def test_a_later_group_lands_on_the_top_row(big_library):
    _to_bar()
    _label_is('A')
    action('down', delay=0.3)
    _label_is('B')
    _grid_on(2)
    _on_top_row()
    action('down', delay=0.3)
    _label_is('C')
    _grid_on(22)
    _on_top_row()
    screenshot('library-bar-top-row')
    action('down', delay=0.3)
    _label_is('D')
    _grid_on(42)
    _on_top_row()


def test_an_earlier_group_lands_on_the_top_row(big_library):
    builtin('SetFocus({},61,absolute)'.format(GRID))
    _grid_on(62)
    _to_bar()
    _label_is('M')
    action('up', delay=0.3)
    _label_is('D')
    _grid_on(42)
    _on_top_row()
    action('up', delay=0.3)
    _label_is('C')
    _grid_on(22)
    _on_top_row()


def test_ok_right_after_a_press_lands_on_the_top_row(big_library):
    _to_bar()
    action('down', 'down', delay=0.05)
    _label_is('C')
    action('select', delay=0.3)
    _focus_is(GRID)
    _grid_on(22)
    _on_top_row()


def test_the_end_of_the_list_cannot_scroll_further(big_library):
    """Z has no page after it: it stays where the last page shows it."""
    _to_bar()
    for label in ('B', 'C', 'D', 'M', 'Z'):
        action('down', delay=0.3)
        _label_is(label)
    _grid_on(63)
    assert _position() >= 6


def test_right_goes_along_the_cards_then_menu_then_bar(library):
    _open()
    action('right', delay=0.2)
    _grid_on(2)
    action('right', delay=0.2)
    _grid_on(3)
    action('right', delay=0.2)
    _focus_is(5101)
    wait_for(READY, timeout=10)
    action('right', delay=0.2)
    _focus_is(BAR)
    _label_is('Z')
    screenshot('library-bar-last-card')


def test_the_first_card_starts_on_its_group(library):
    _open()
    _to_bar()
    _label_is('A')
    screenshot('library-bar-first')


def test_a_quick_right_right_reaches_the_bar(library):
    """The menu takes no time to think once the window has settled."""
    _open()
    wait_for(READY, timeout=10)
    builtin('SetFocus({},2,absolute)'.format(GRID))
    _grid_on(3)
    action('right', delay=0)
    action('right', delay=0)
    _focus_is(BAR)


def test_down_moves_a_group_and_the_grid_follows_without_the_focus(library):
    _open()
    _to_bar()
    action('down', delay=0.2)
    _label_is('M')
    _grid_on(2)
    _focus_is(BAR)
    assert _label('Container({}).ListItem.SortLetter'.format(GRID)) == 'M'
    screenshot('library-bar-middle')
    action('down', delay=0.2)
    _label_is('Z')
    _grid_on(3)
    screenshot('library-bar-last')
    # the ends stop it
    action('down', delay=0.4)
    _label_is('Z')
    action('up', delay=0.2)
    _label_is('M')
    _grid_on(2)


def test_a_burst_of_presses_ends_on_the_last(library):
    _open()
    _to_bar()
    action('down', 'down', 'up', delay=0)
    _label_is('M')
    _grid_on(2)


def test_ok_goes_to_the_groups_first_title(library):
    _open()
    _to_bar()
    action('down', delay=0.3)
    _label_is('M')
    action('select')
    _focus_is(GRID)
    _grid_on(2)


def test_ok_right_after_the_press_lands_there(library):
    _open()
    _to_bar()
    action('down', delay=0)
    _label_is('M')
    action('select', delay=0)
    _focus_is(GRID)
    _grid_on(2)


def test_back_returns_to_the_card_it_came_from(library):
    _open()
    action('right', delay=0.3)  # the second card
    _grid_on(2)
    _to_bar()
    _label_is('M')
    action('down', delay=0.2)
    _label_is('Z')
    _grid_on(3)
    action('back', delay=0.3)
    _focus_is(GRID)
    _grid_on(2)
    assert cond('Window.IsActive(1110)')['Window.IsActive(1110)']


def test_escape_on_the_bar_is_back_too(library):
    """Esc on a keyboard, and Back on many remotes, is PreviousMenu."""
    _open()
    _to_bar()
    action('down', delay=0.2)
    _label_is('M')
    rpc('Input.ButtonEvent', {'button': 'escape', 'keymap': 'KB'})
    _focus_is(GRID)
    _grid_on(1)
    assert cond('Window.IsActive(1110)')['Window.IsActive(1110)']


def test_back_on_the_grid_still_leaves_the_window(library):
    _open()
    action('back', delay=0.5)
    wait_for('!Window.IsActive(1110)', timeout=5)


def test_back_right_after_a_press_is_not_undone_by_the_grid_following(library):
    _open()
    _to_bar()
    action('down', delay=0)
    _label_is('M')
    action('back', delay=0)
    _focus_is(GRID)
    _grid_on(1)
    time.sleep(0.5)
    _grid_on(1)


def test_left_stays_there_by_way_of_the_menu(library):
    _open()
    _to_bar()
    action('down', delay=0.2)
    _label_is('M')
    action('left', delay=0.2)
    _focus_is(5101)
    _grid_on(2)
    action('left', delay=0.2)
    _focus_is(GRID)
    _grid_on(2)


def _bright_beside_the_rail(path):
    """Bright pixels in the strip between the menu and the rail, where only the cursor ever draws."""
    image = Image.open(path).convert('RGB')
    scale = image.width / 1920
    strip = image.crop((int(1878 * scale), 0, int(1894 * scale), image.height))
    return sum(1 for pixel in strip.getdata() if max(pixel) > 150)


@pytest.mark.parametrize('key', ['select', 'left', 'back'])
def test_the_cursor_leaves_nothing_behind(library, key):
    """Without the focus the bar shows nothing: a colour of 0 made Kodi draw it as a white frame."""
    _open()
    _to_bar()
    action('down', delay=0.3)
    _label_is('M')
    assert _bright_beside_the_rail(screenshot('library-bar-on')) > 0  # the strip does see the cursor
    action(key, delay=0.6)
    assert info('System.CurrentControlId')['System.CurrentControlId'] != str(BAR)
    assert _bright_beside_the_rail(screenshot('library-bar-left-' + key)) == 0


def _edges_at_the_column_end(path):
    """How much the rows differ at the right end of the wide menu: its frames, or background."""
    image = Image.open(path).convert('L')
    scale = image.width / 1920
    strip = image.crop((int(1810 * scale), int(100 * scale), int(1850 * scale), int(250 * scale)))
    rows = [sum(strip.crop((0, y, strip.width, y + 1)).getdata()) / strip.width for y in range(strip.height)]
    return max(rows) - min(rows)


def test_the_menu_is_narrow_only_while_the_bar_has_the_focus(library):
    """The middle stop: the cursor is far below the buttons, so only the menu can be in this strip."""
    _open()
    time.sleep(0.3)
    grid = _edges_at_the_column_end(screenshot('library-bar-menu-wide'))
    _to_bar()
    action('down', delay=0.2)
    _label_is('M')
    time.sleep(0.5)
    bar = _edges_at_the_column_end(screenshot('library-bar-menu-narrow'))
    assert bar < grid / 2, (grid, bar)
    action('left', delay=0.3)
    _focus_is(5101)
    action('left', delay=0.3)
    _focus_is(GRID)
    time.sleep(0.3)
    back = _edges_at_the_column_end(screenshot('library-bar-menu-back'))
    assert back > grid / 2, (grid, back)


def test_a_window_reopened_after_leaving_from_the_bar_has_the_wide_menu(library):
    _open()
    _to_bar()
    time.sleep(0.3)
    builtin('ActivateWindow(home)')
    wait_for('!Window.IsActive(1110)')
    _open()
    time.sleep(0.5)
    assert _edges_at_the_column_end(screenshot('library-bar-menu-reopened')) > 3


def _cursor_row(path):
    """The middle of the cursor's bright rows, in screen px of 1080 lines."""
    image = Image.open(path).convert('RGB')
    scale = image.width / 1920
    strip = image.crop((int(1878 * scale), 0, int(1894 * scale), image.height))
    rows = [y for y in range(strip.height) if max(strip.getpixel((strip.width // 2, y))) > 150]
    assert rows
    return (rows[0] + rows[-1]) / 2 / scale


@pytest.mark.parametrize('keys,stop', [(['down'], 1), (['down', 'down', 'up'], 1), (['down', 'down'], 2)])
def test_the_cursor_ends_on_its_stop_of_the_rail(library, keys, stop):
    """Evenly over the rail: the first stop at its top, the last at its end."""
    _open()
    _to_bar()
    action(*keys, delay=0.05)
    time.sleep(0.6)
    assert abs(_cursor_row(screenshot('library-bar-stop')) - (98 + 450 * stop)) < 12


def test_the_rail_stands_without_the_focus(library):
    _open()
    assert cond('Control.IsVisible(5900)')['Control.IsVisible(5900)'] is not None
    screenshot('library-bar-rail')


@pytest.mark.parametrize('method,labels', [
    ('year', ['1994', '2005', '2020']),
    ('dateadded', ['Feb 24', 'Jul 25', 'Nov 26']),
])
def test_other_sorts_name_their_groups(library, method, labels):
    _sort(method)
    _open()
    _to_bar()
    for i, label in enumerate(labels):
        _label_is(label)
        _grid_on(i + 1)
        screenshot('library-bar-{}-{}'.format(method, i))
        action('down', delay=0.2)


def test_rating_sort_ends_on_none(library):
    _sort('rating', desc=True)
    _open()
    _to_bar()
    for label in ('8', '6', 'none'):
        _label_is(label)
        action('down', delay=0.2)
    screenshot('library-bar-rating')


def test_descending_starts_at_the_end_of_the_alphabet(library):
    _sort('', desc=True)
    _open()
    _to_bar()
    _label_is('Z')
    action('down', delay=0.2)
    _label_is('M')
    _grid_on(2)


def test_changing_the_sort_makes_a_new_table(library):
    _open()
    _to_bar()
    _label_is('A')
    action('left', delay=0.3)
    _focus_is(5101)
    action('select', delay=0.3)  # title to year
    wait_for('String.IsEqual(Skin.String(nc.sort),year)', timeout=5)
    time.sleep(1)
    wait_for(READY, timeout=10)
    action('right', delay=0.2)
    _focus_is(BAR)
    _label_is('1994')


def test_too_few_groups_leave_the_bar_out(library):
    """All three in one year: a bar with one stop has nothing to offer, Right stays on the menu."""
    movies = rpc('VideoLibrary.GetMovies', {'properties': ['year']})['movies']
    _details([{'movieid': m['movieid'], 'year': 2000} for m in movies])
    _sort('year', desc=True)  # a sort no test before used: Kodi keeps a list it has loaded
    _open()
    builtin('SetFocus(5101)')
    _focus_is(5101)
    time.sleep(1.5)
    action('right', delay=1)
    _focus_is(5101)
