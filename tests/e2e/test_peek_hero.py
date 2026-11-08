"""A page without spotlight keeps its hero and previews the title the cursor would land on
(Includes_Sections.xml PeekHeroes): in the menu the first title of the first row with titles,
Down lands on it, Right moves on, Up back to the menu keeps the title the cursor left, Down lands
on it again. The same on the movies page right after the move along the menu."""
import time

import pytest

from conftest import builtin, cond, info, rpc, wait_for

pytestmark = pytest.mark.e2e

PEEK = {'home': (9360, 92), 'movies': (9370, 94)}


def true(condition):
    return cond(condition)[condition]


def first_title_row(base):
    for n in range(1, 9):
        if true('Control.IsVisible({0}0{1}) + Integer.IsGreater(Container({0}0{1}).NumItems,1)'.format(base, n)):
            return n
    pytest.skip('no row with two titles on this page')


@pytest.fixture
def no_spotlight(home):
    builtin('Skin.SetString(SpotlightSource,off)')
    builtin('Skin.SetString(nc.movies.spotlight,off)')
    builtin('ReloadSkin()')
    time.sleep(3)
    wait_for('Window.IsActive(home)', timeout=20)
    try:
        yield
    finally:
        builtin('Skin.Reset(SpotlightSource)')
        builtin('Skin.Reset(nc.movies.spotlight)')
        builtin('ReloadSkin()')
        time.sleep(3)
        wait_for('Window.IsActive(home)', timeout=20)


def test_the_hero_previews_where_down_lands(no_spotlight):
    peek, base = PEEK['home']
    builtin('SetFocus(9101)')
    wait_for('Control.HasFocus(9101)')
    n = first_title_row(base)
    row, group = '{}0{}'.format(base, n), peek + n
    wait_for('Control.IsVisible({}) + Integer.IsEqual(Container({}).Position,0)'.format(group, row))
    assert not true('Control.IsVisible(9050)')  # no buttons
    rpc('Input.Down')
    wait_for('Control.HasFocus({}) + Integer.IsEqual(Container({}).Position,0)'.format(row, row))
    # the same hero from the menu onto the card: no swap to the hero that follows a card
    assert true('Control.IsVisible({}) + !Control.IsVisible(9302)'.format(group))
    rpc('Input.Right')
    wait_for('Integer.IsEqual(Container({}).Position,1)'.format(row))
    title = info('Container({}).ListItem.Label'.format(row))['Container({}).ListItem.Label'.format(row)]
    rpc('Input.Up')
    wait_for('Control.HasFocus(9101) + Control.IsVisible({})'.format(group))
    # the hero shows the title the cursor left, not the first one
    assert info('Container({}).ListItem.Label'.format(row))['Container({}).ListItem.Label'.format(row)] == title
    rpc('Input.Down')
    wait_for('Control.HasFocus({}) + Integer.IsEqual(Container({}).Position,1)'.format(row, row))


def test_the_next_page_previews_at_once(no_spotlight):
    peek, base = PEEK['movies']
    builtin('SetFocus(9101)')
    wait_for('Control.HasFocus(9101)')
    rpc('Input.Right')
    wait_for('Control.HasFocus(9102) + String.IsEqual(Window(Home).Property(nc.page),movies)')
    n = first_title_row(base)
    row = '{}0{}'.format(base, n)
    wait_for('Control.IsVisible({})'.format(peek + n))
    rpc('Input.Down')
    wait_for('Control.HasFocus({})'.format(row))
