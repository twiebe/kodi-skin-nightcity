"""The focus never lands in a TMDb row that still shows the page before or is still loading,
and it needs no extra key once the row is in (nc_info_enter, Timers.xml).

Same requirements as test_tmdb_chain.py: TMDb Helper, internet access, The Matrix in the
library."""
import time

import pytest

from conftest import action, builtin, info, wait_for
from test_tmdb_chain import _page, _true, matrix  # noqa: F401 (fixture)

pytestmark = pytest.mark.e2e

INFO = {'5500': 'cast', '5300': 'recommendations', '5510': 'stars_in_movies'}


def _ready(cid):
    """The list holds its own items (TmdbFresh<cid>, which JSON-RPC cannot evaluate), loaded."""
    first, kind = ('Container({}).ListItem(0).Property(param.{})'.format(cid, k) for k in ('tmdb_id', 'info'))
    labels = info('ListItem.Property(tmdb_id)', first, kind)
    page, first, kind = labels['ListItem.Property(tmdb_id)'], labels[first], labels[kind]
    return (bool(page) and page == first and kind == INFO[cid]
            and _true('!Container({0}).IsUpdating + Integer.IsGreater(Container({0}).NumItems,0)'.format(cid)))


def _wait_ready(cid, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        if _ready(cid):
            return
        time.sleep(0.1)
    raise AssertionError('{} not ready: {}'.format(cid, info(
        'ListItem.Property(tmdb_id)', 'Container({}).ListItem(0).Property(param.tmdb_id)'.format(cid),
        'Container({}).ListItem(0).Property(param.info)'.format(cid), 'Container({}).NumItems'.format(cid))))


def _third_page(matrix):
    """The Matrix, its first actor, the actor's first film: a page that opens over the lists of
    the Matrix's page."""
    builtin('NotifyAll(nightcity,info:movie:{})'.format(matrix))
    wait_for('Window.IsActive(movieinformation)', timeout=20)
    # the library page opens first: nothing before it to show
    wait_for('!Container(5500).IsUpdating + Integer.IsGreater(Container(5500).NumItems,0)', timeout=30)
    builtin('SetFocus(5500,0,absolute)')
    action('select')
    _page(2)
    _wait_ready('5510')
    # a film that is not The Matrix: its lists start with the Matrix's items
    builtin('SetFocus(5510,0,absolute)')
    for _ in range(5):
        if 'Matrix' not in info('Container(5510).ListItem.Label')['Container(5510).ListItem.Label']:
            break
        action('right')
    title = info('Container(5510).ListItem.Label')['Container(5510).ListItem.Label']
    action('select', delay=0)
    wait_for('String.IsEqual(Window(Home).Property(TMDbHelper.Position),3)', timeout=30)
    wait_for('Window.IsActive(movieinformation) + String.IsEqual(ListItem.Property(tmdb_type),movie)', timeout=20)
    return title


def _on_the_credits(matrix):
    """Down into the credits of a new page as soon as they take the focus: similar titles
    load after them."""
    _third_page(matrix)
    wait_for('ControlGroup(9000).HasFocus()', timeout=5)
    action('down', delay=0)
    # the tabs while the credits load
    wait_for('ControlGroup(5520).HasFocus() | Control.HasFocus(5500)', timeout=5)
    if _true('ControlGroup(5520).HasFocus()'):
        action('down', delay=0)
    wait_for('Control.HasFocus(5500)', timeout=30)


def test_fast_down_waits_for_the_credits_of_the_new_page(matrix):
    _third_page(matrix)
    wait_for('ControlGroup(9000).HasFocus()', timeout=5)
    action('down', delay=0)
    action('down', delay=0)
    # never in a list that is not ready
    for _ in range(40):
        for cid in ('5500', '5300'):
            if _true('Control.HasFocus({})'.format(cid)):
                assert _ready(cid), cid
        if _true('Control.HasFocus(5500) | Control.HasFocus(5300)'):
            break
        action('noop', delay=0.1)
    _wait_ready('5500')
    wait_for('Control.HasFocus(5500) | Control.HasFocus(5300)', timeout=3)


def test_moving_on_forgets_the_waiting_move(matrix):
    """OK on the crew tab, then Left to the cast tab before the crew is in: the focus stays
    where it went."""
    _third_page(matrix)
    _wait_ready('5500')
    builtin('SetFocus(5522)')
    wait_for('Control.HasFocus(5522)')
    action('select', delay=0)
    action('left', delay=0)
    wait_for('String.IsEmpty(Window(Home).Property(nc.info.enter))', timeout=3)
    wait_for('String.IsEqual(Container(5500).ListItem(0).Property(param.info),crew) + !Container(5500).IsUpdating', timeout=30)
    assert _true('Control.HasFocus(5521)')
