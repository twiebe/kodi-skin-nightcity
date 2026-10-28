"""Context menu size and place, the context menu of the spotlight title and the spotlight kicker.

Kodi places DialogContextMenu itself (GUIDialogContextMenu.cpp): it centres the window on the
focused control and keeps it on screen, measuring the window by the background image 999 from the
window origin. Kodi stretches 999 to the entries of grouplist 996 (its height minus the grouplist
height plus the entries' height), so 999 has to start at the window origin and hold the grouplist.
"""
import re

from navigation import load

SCREEN_W, SCREEN_H = 1920, 1080


def _num(el, tag, default=0):
    text = (el.findtext(tag) or '').strip()
    return int(text) if text else default


def _context_menu():
    window = load('DialogContextMenu.xml')
    path, found = [], {}

    def walk(el, chain):
        for c in el.findall('control'):
            if c.get('id') in ('999', '996'):
                found[c.get('id')] = (c, chain)
            walk(c, chain + [c])
    walk(window.find('controls'), path)
    return window, found


def test_context_menu_background_starts_at_window_origin():
    """Every control above 999 sits at 0,0: else Kodi clamps the wrong rectangle and the menu
    hangs off the right and the bottom of the screen."""
    window, found = _context_menu()
    background, chain = found['999']
    for c in chain + [background]:
        assert _num(c, 'left') == 0 and _num(c, 'top') == 0, c.attrib
        assert c.find('centerleft') is None and c.find('centertop') is None, c.attrib
    coords = window.find('coordinates')
    if coords is not None:
        assert _num(coords, 'left') == 0 and _num(coords, 'top') == 0


def test_context_menu_grows_with_its_entries_and_fits_the_screen():
    _, found = _context_menu()
    background, _ = found['999']
    grouplist, chain = found['996']
    height = grouplist.find('height')
    assert height.text.strip() == 'auto' and height.get('max'), 'grouplist height must follow the entries'
    tallest = int(height.get('max'))
    top = sum(_num(c, 'top') for c in chain) + _num(grouplist, 'top')
    left = sum(_num(c, 'left') for c in chain) + _num(grouplist, 'left')
    # the gap below the entries stays when Kodi resizes 999
    assert _num(background, 'height') >= top + tallest
    assert _num(background, 'height') <= SCREEN_H and _num(background, 'width') <= SCREEN_W
    assert left + _num(grouplist, 'width') <= _num(background, 'width')
    # long menus (jellyfin-kodi, TMDb Helper) scroll inside: at least 12 entries of 52 px
    assert tallest >= 12 * 52


SPOTLIGHT = {'9050': ('9000', ('9010', '9011', '9012')), '9550': ('9001', ('9551', '9552', '9553'))}


def test_spotlight_buttons_are_lists_of_the_spotlight_title():
    """The context menu key opens the menu of the focused list item; a button has none. The
    spotlight buttons are one-item lists holding the spotlight title from the library."""
    controls = {c.get('id'): c for c in load('Home.xml').iter('control') if c.get('id')}
    for group, (spotlight, buttons) in SPOTLIGHT.items():
        assert controls[group].get('type') == 'group'
        inside = {c.get('id') for c in controls[group].iter('control')}
        for cid in buttons:
            assert cid in inside
            button = controls[cid]
            assert button.get('type') == 'list', cid
            content = button.findtext('content') or ''
            assert content.startswith('$VAR['), cid
    variables = load_variables()
    assert 'Container(9000).ListItem.DBID' in variables['SpotlightItemPath']
    assert 'Container(9001).ListItem' in variables['SpotlightShowItemPath']


def load_variables():
    from conftest import ROOT, parse
    root = parse(ROOT / '1080i' / 'Variables.xml')
    return {v.get('name'): ' '.join((x.text or '') + ' ' + (x.get('condition') or '') for x in v)
            for v in root.iter('variable')}


def test_spotlight_kicker_has_no_position_counter():
    """The spotlight runs without end: no "5/580" next to the arrows."""
    from conftest import ROOT
    for name in ('Home.xml', 'Includes_Home.xml'):
        text = (ROOT / '1080i' / name).read_text()
        for spotlight in ('9000', '9001'):
            assert 'Container({}).CurrentItem'.format(spotlight) not in text, name
            assert 'Container({}).NumItems]'.format(spotlight) not in text, name
