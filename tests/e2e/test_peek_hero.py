"""A still spotlight (interval "still") keeps its hero and buttons and shows the title the cursor
would land on (Includes_Sections.xml PeekHeroes): from the menu Down to the buttons, Down onto
that title, Right moves on, Up back to the buttons keeps the title the cursor left. Left and Right
on the buttons only move between them, info opens the shown title's page and Back returns to the
button. The next page shows its own title right after the move along the menu."""
import time

import pytest

from conftest import action, builtin, cond, info, rpc, screenshot, wait_for

pytestmark = pytest.mark.e2e

PEEK = {'home': (9360, 92), 'movies': (9370, 94)}


def true(condition):
    return cond(condition)[condition]


def label(key):
    return info(key)[key]


def first_title_row(base):
    for n in range(1, 9):
        if true('Control.IsVisible({0}0{1}) + Integer.IsGreater(Container({0}0{1}).NumItems,1)'.format(base, n)):
            return n
    pytest.skip('no row with two titles on this page')


def loaded(base):
    """Some row of the page has titles (the started ones may have none)."""
    return ' | '.join('Integer.IsGreater(Container({}0{}).NumItems,1)'.format(base, n) for n in range(1, 9))


def reopen_home():
    builtin('ReplaceWindow(Settings)')  # Home reads the interval when opened
    wait_for('Window.IsActive(settings)')
    builtin('ReplaceWindow(Home)')
    wait_for('Window.IsActive(home)')


@pytest.fixture
def still(home):
    builtin('Skin.SetString(SpotlightInterval,off)')
    builtin('Skin.SetString(nc.movies.interval,off)')
    reopen_home()
    try:
        yield
    finally:
        builtin('Skin.Reset(SpotlightInterval)')
        builtin('Skin.Reset(nc.movies.interval)')
        builtin('SetFocus(9101)')
        reopen_home()


def test_the_hero_shows_where_down_lands(still):
    peek, base = PEEK['home']
    builtin('SetFocus(9101)')
    wait_for('Control.HasFocus(9101) + [' + loaded(base) + ']', timeout=15)
    n = first_title_row(base)
    row, group = '{}0{}'.format(base, n), peek + n
    wait_for('Control.IsVisible({}) + Integer.IsEqual(Container({}).Position,0)'.format(group, row))
    assert not true('Control.IsVisible(9000)')  # no spotlight list of its own
    screenshot('still-home-menu')
    rpc('Input.Down')
    wait_for('Control.HasFocus(9010) + Control.IsVisible({})'.format(group))
    screenshot('still-home-buttons')
    rpc('Input.Down')
    wait_for('Control.HasFocus({}) + Integer.IsEqual(Container({}).Position,0)'.format(row, row))
    # the same hero from the buttons onto the card: no swap to the hero that follows a card
    assert true('Control.IsVisible({}) + !Control.IsVisible(9302)'.format(group))
    rpc('Input.Right')
    wait_for('Integer.IsEqual(Container({}).Position,1)'.format(row))
    title = label('Container({}).ListItem.Label'.format(row))
    for _ in range(n):  # up through the rows above, past empty slots
        if true('Control.HasFocus(9010)'):
            break
        rpc('Input.Up')
        time.sleep(0.3)
    wait_for('Control.HasFocus(9010) + Control.IsVisible({})'.format(group))
    # the hero shows the title the cursor left, not the first one
    assert label('Container({}).ListItem.Label'.format(row)) == title
    rpc('Input.Down')
    wait_for('Control.HasFocus({}) + Integer.IsEqual(Container({}).Position,1)'.format(row, row))


def test_the_next_page_shows_its_title_at_once(still):
    peek, base = PEEK['movies']
    builtin('SetFocus(9101)')
    wait_for('Control.HasFocus(9101)')
    rpc('Input.Right')
    wait_for('Control.HasFocus(9102) + String.IsEqual(Window(Home).Property(nc.page),movies)')
    wait_for(loaded(base), timeout=15)
    n = first_title_row(base)
    row = '{}0{}'.format(base, n)
    wait_for('Control.IsVisible({})'.format(peek + n))
    rpc('Input.Down')
    wait_for('Control.HasFocus(9010) + Control.IsVisible(9012)')
    rpc('Input.Down')
    wait_for('Control.HasFocus({})'.format(row))


def test_left_and_right_only_move_between_the_buttons(still):
    peek, base = PEEK['home']
    builtin('SetFocus(9010)')
    wait_for('Control.HasFocus(9010) + [' + loaded(base) + ']', timeout=15)
    n = first_title_row(base)
    row, group = '{}0{}'.format(base, n), peek + n
    wait_for('Control.IsVisible({})'.format(group))
    title = label('Container({}).ListItem.Label'.format(row))
    action('left', delay=0.5)
    assert true('Control.HasFocus(9010)')
    action('right', delay=0.5)
    wait_for('Control.HasFocus(9011)')
    action('right', delay=0.5)
    assert true('Control.HasFocus(9011) + Control.IsVisible({})'.format(group))
    assert label('Container({}).ListItem.Label'.format(row)) == title


def test_info_opens_the_shown_title_and_back_returns_to_the_button(still):
    peek, base = PEEK['home']
    builtin('SetFocus(9011)')
    wait_for('Control.HasFocus(9011) + [' + loaded(base) + ']', timeout=15)
    n = first_title_row(base)
    row = '{}0{}'.format(base, n)
    wait_for('Control.IsVisible({})'.format(peek + n))
    title = label('Container({}).ListItem.Title'.format(row))
    action('select')
    # the page is up and has its focus before Back: a Back while it still opens can go astray
    wait_for('Window.IsActive(movieinformation) + Control.HasFocus(9001)', timeout=15)
    assert label('ListItem.Title') == title
    time.sleep(0.5)
    action('back')
    wait_for('Window.IsActive(home) + !Window.IsVisible(movieinformation) + Control.HasFocus(9011)', timeout=15)


def test_the_hero_follows_the_row_the_cursor_was_in(still):
    """Down into a second row: the hero shows that row's title, also after Up to the buttons; a
    row named itself only for a bare ListItem, which at onfocus is still the control before."""
    peek, base = PEEK['movies']
    # two rows with titles: new movies first, random movies second
    builtin('Skin.SetString(nc.movies.slot1,newmovies)')
    builtin('Skin.SetString(nc.movies.slot2,random)')
    reopen_home()
    try:
        builtin('SetFocus(9102)')
        wait_for('String.IsEqual(Window(Home).Property(nc.page),movies)')
        first, second = '{}01'.format(base), '{}02'.format(base)
        wait_for('Integer.IsGreater(Container({}).NumItems,0) + Integer.IsGreater(Container({}).NumItems,0)'.format(first, second), timeout=15)
        wait_for('Control.IsVisible({})'.format(peek + 1))
        builtin('SetFocus({})'.format(second))
        wait_for('Control.HasFocus({})'.format(second))
        wait_for('String.IsEqual(Window(Home).Property(nc.peek.movies),{})'.format(second))
        wait_for('Control.IsVisible({}) + !Control.IsVisible({})'.format(peek + 2, peek + 1))
        builtin('SetFocus(9010)')
        wait_for('Control.HasFocus(9010) + Control.IsVisible({})'.format(peek + 2))
    finally:
        builtin('Skin.Reset(nc.movies.slot1)')
        builtin('Skin.Reset(nc.movies.slot2)')
