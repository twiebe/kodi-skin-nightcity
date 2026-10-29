"""Context menu on screen and on the spotlight title.

The context menu used to open a third of the screen wide at the right edge and so low that only
its first four entries showed. Here every entry, focused one after the other, has to show in full
on the screenshot: the focused entry is the only wide bar in the focus colour besides the accent
bar on top of the menu.
"""
import time

import pytest
from PIL import Image

from conftest import action, builtin, cond, info, rpc, screenshot, wait_for

pytestmark = pytest.mark.e2e

FOCUS = (0x5F, 0xD8, 0xE8)  # focus and accent of the default colour theme


def focus(control_id):
    builtin('SetFocus({})'.format(control_id))
    wait_for('Control.HasFocus({})'.format(control_id))


@pytest.fixture
def home_page(home):
    yield
    builtin('Dialog.Close(all,true)')
    focus(9101)


def open_context_menu():
    rpc('Input.ContextMenu')
    wait_for('Window.IsVisible(contextmenu)')
    wait_for('Control.HasFocus(1001)')


def entries():
    labels = []
    for cid in range(1001, 1041):
        key = 'Control.IsVisible({})'.format(cid)
        if not cond(key)[key]:
            break
        labels.append(info('Control.GetLabel({})'.format(cid))['Control.GetLabel({})'.format(cid)])
    return labels


def bars(path):
    """(top, bottom, left, right) of the horizontal bars in the focus colour, at least 300 px
    wide in 1920 x 1080 terms, top to bottom."""
    img = Image.open(path).convert('RGB')
    w, h = img.size
    px = img.load()
    scale = w / 1920

    def near(c):
        return all(abs(a - b) <= 6 for a, b in zip(c, FOCUS))

    rows = []
    for y in range(h):
        run = best = 0
        first = last = None
        for x in range(w):
            if near(px[x, y]):
                run += 1
                if run > best:
                    best, last = run, x
                    first = x - run + 1
            else:
                run = 0
        rows.append((first, last) if best >= 300 * scale else None)
    found, start = [], None
    for y, r in enumerate(rows + [None]):
        if r and start is None:
            start = y
        elif not r and start is not None:
            xs = [rows[i] for i in range(start, y)]
            found.append(tuple(v / scale for v in (start, y - 1, min(a for a, _ in xs), max(b for _, b in xs))))
            start = None
    return found


def assert_entries_on_screen(name):
    labels = entries()
    assert len(labels) >= 4, labels
    for n in range(len(labels)):
        focus(1001 + n)
        shot = screenshot('{}-{}'.format(name, n + 1))
        found = [b for b in bars(shot) if b[1] - b[0] > 30]  # an entry, not the 4 px accent bar
        assert found, 'entry {} ({}) not on screen'.format(n + 1, labels[n])
        top, bottom, left, right = found[-1]
        assert top > 0 and bottom < 1078 and left > 0 and right < 1919, (labels[n], found[-1])
        assert bottom - top >= 46, (labels[n], found[-1])
    return labels


def test_context_menu_on_card_shows_every_entry(home_page):
    focus(9102)
    # first test of a worker right after the run restarted Kodi: the row may still be empty,
    # a SetFocus on it goes nowhere
    end = time.time() + 30
    while True:
        builtin('SetFocus(9410)')
        try:
            wait_for('ControlGroup(9410).HasFocus() + !String.IsEmpty(Container.ListItem.Label)', timeout=3)
            break
        except AssertionError:
            if time.time() > end:
                raise
    open_context_menu()
    labels = assert_entries_on_screen('ctx-card')
    assert 'Information' in labels or 'Movie information' in labels, labels


@pytest.mark.parametrize('tab,spotlight,button', [(9101, 9000, 9010), (9101, 9000, 9011), (9103, 9001, 9551)])
def test_context_menu_on_spotlight_title(home_page, tab, spotlight, button):
    """jellyfin-kodi's entries (add to playlist ...) come with the menu of a library item."""
    focus(tab)
    wait_for('Integer.IsGreater(Container({}).NumItems,0)'.format(spotlight))
    focus(button)
    title = info('Container({}).ListItem.Label'.format(spotlight))['Container({}).ListItem.Label'.format(spotlight)]
    wait_for('String.IsEqual(Container({}).ListItem.Label,{})'.format(button, title))
    open_context_menu()
    labels = entries()
    assert any('Jellyfin' in label or 'jellyfin' in label for label in labels), labels
    screenshot('ctx-spotlight-{}'.format(button))
    action('back')
    wait_for('!Window.IsVisible(contextmenu)')
    assert cond('Control.HasFocus({})'.format(button))['Control.HasFocus({})'.format(button)]


def test_spotlight_buttons_follow_the_title(home_page):
    """The one-item list behind the buttons changes with the spotlight."""
    focus(9101)
    wait_for('Integer.IsGreater(Container(9000).NumItems,2)')
    focus(9010)
    before = info('Container(9010).ListItem.DBID')['Container(9010).ListItem.DBID']
    action('left')
    wait_for('!String.IsEqual(Container(9000).ListItem.DBID,{})'.format(before))
    now = info('Container(9000).ListItem.DBID')['Container(9000).ListItem.DBID']
    wait_for('String.IsEqual(Container(9010).ListItem.DBID,{})'.format(now))
    assert cond('Control.HasFocus(9010)')['Control.HasFocus(9010)']



KDEV_SHOW = ('videodb://tvshows/titles/?xsp={"rules":{"and":[{"field":"title","operator":"is","value":["Kdev Show"]}]},'
             '"type":"tvshows"}')


@pytest.fixture
def info_page(home_page):
    yield
    builtin('Dialog.Close(all,true)')
    builtin('ActivateWindow(Home)')
    wait_for('Window.IsActive(home)')


def _open_info(kind):
    builtin('Dialog.Close(all,true)')
    if kind == 'movie':
        builtin('NotifyAll(nightcity,info:movie:1)')
    elif kind == 'tvshow':
        # the show's info from its card in the library window
        builtin('ActivateWindow(Videos,"{}",return)'.format(KDEV_SHOW.replace('"', '\\"')))
        wait_for('Window.IsActive(Videos) + Integer.IsGreater(Container.NumItems,0)')
        if not cond('String.IsEqual(ListItem.Label,Kdev Show)')['String.IsEqual(ListItem.Label,Kdev Show)']:
            action('down')  # past the parent folder item
        wait_for('String.IsEqual(ListItem.Label,Kdev Show)')
        builtin('Action(Info)')
    else:
        builtin('ClearProperty(nc.info.ready,home)')
        builtin('NotifyAll(nightcity,next_episode:1)')
    wait_for('Window.IsActive(movieinformation)')
    if kind == 'episode':
        wait_for('!String.IsEmpty(Window(Home).Property(nc.info.ready))')
    wait_for('String.IsEqual(ListItem.DBType,{})'.format(kind))


@pytest.mark.parametrize('kind', ['movie', 'tvshow', 'episode'])
def test_more_button_on_info_page_opens_the_titles_menu(info_page, kind):
    """… on a library info page is Kodi's context menu of the title, with the entries add-ons
    add to it, like on a card."""
    _open_info(kind)
    focus(9003)
    action('contextmenu')
    wait_for('Window.IsVisible(contextmenu)')
    labels = entries()
    assert any('jellyfin' in label.lower() for label in labels), labels
    screenshot('ctx-info-{}'.format(kind))
    action('back')
    wait_for('!Window.IsVisible(contextmenu)')
    assert cond('Control.HasFocus(9003)')['Control.HasFocus(9003)']


def test_more_button_on_episode_page_follows_the_episode(info_page):
    """The episode page walks its season: … holds the episode on screen, not the one it opened."""
    _open_info('episode')
    builtin('SetFocus(5100)')
    wait_for('Control.HasFocus(5100)')
    action('right')
    wait_for('!String.IsEqual(Container(5100).ListItem.DBID,ListItem.DBID)')
    episode = info('Container(5100).ListItem.DBID')['Container(5100).ListItem.DBID']
    wait_for('String.IsEqual(Container(9003).ListItem.DBID,{})'.format(episode))


def test_more_button_select_opens_the_titles_menu(info_page):
    """OK on … opens the menu too: the button reads … and should do something on OK."""
    _open_info('movie')
    focus(9003)
    action('select')
    wait_for('Window.IsVisible(contextmenu)')
    action('back')
