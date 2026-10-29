"""A page switch on Home advances the spotlight of the page that comes up by one title, so two
pages never show the same title right after a switch (home and movies share the movie spotlight,
list 9000). The rotation starts over with it (nc_spot_hold), so the new title gets its full
interval. Only the menu tabs switch pages: Home coming back from another window keeps its title."""
import re

import pytest

from navigation import evaluate, load

# menu tab, page, spotlight list, skin string that switches the page's spotlight off
TABS = (('9101', 'home', '9000', 'SpotlightSource'),
        ('9102', 'movies', '9000', 'nc.movies.spotlight'),
        ('9103', 'shows', '9001', 'nc.shows.spotlight'))
PAGES = ('home', 'movies', 'shows', 'search', 'system')


def tab(tab_id):
    return next(c for c in load('Home.xml').iter('control') if c.get('id') == tab_id)


def onfocus(control):
    return [(o.get('condition') or '', (o.text or '').strip()) for o in control.findall('onfocus')]


def actions_when(control, page, skin):
    """The onfocus actions Kodi runs for this tab while `page` is up (Kodi checks the conditions
    before it runs the first action, so all of them see the page that is being left)."""
    skin = dict(skin, **{'Window(Home).Property(nc.page)': page})
    return [a for c, a in onfocus(control) if not c or evaluate(c, skin)]


@pytest.mark.parametrize('tab_id,page,spotlight,setting', TABS)
def test_switching_to_a_page_advances_its_spotlight(tab_id, page, spotlight, setting):
    control = tab(tab_id)
    for other in PAGES:
        if other == page:
            continue
        actions = actions_when(control, other, {})
        assert 'Control.Move({},1)'.format(spotlight) in actions, (page, other)
        # the rotation starts over: the autoscroll condition is false while the hold runs
        assert 'Skin.TimerStart(nc_spot_hold)' in actions, (page, other)
        # before the page changes (the conditions name the page that is left)
        assert actions.index('Control.Move({},1)'.format(spotlight)) < actions.index(
            'SetProperty(nc.page,{},home)'.format(page))


@pytest.mark.parametrize('tab_id,page,spotlight,setting', TABS)
def test_focus_on_the_current_tab_keeps_the_spotlight(tab_id, page, spotlight, setting):
    """Up from the page into its own tab, Home coming back from the info page or the player
    with the tab focused: no page switch, no advance."""
    current = ('', page) if page == 'home' else (page,)
    for value in current:
        actions = actions_when(tab(tab_id), value, {})
        assert not [a for a in actions if a.startswith('Control.Move') or 'nc_spot_hold' in a], (page, value)


@pytest.mark.parametrize('tab_id,page,spotlight,setting', TABS)
def test_no_advance_without_spotlight(tab_id, page, spotlight, setting):
    """The page's spotlight is off: its list may not exist at all."""
    actions = actions_when(tab(tab_id), 'search', {setting: 'off'})
    assert not [a for a in actions if a.startswith('Control.Move')], page


def test_other_tabs_move_no_spotlight():
    for control in load('Home.xml').iter('control'):
        if control.get('id') in ('9104',):
            assert not [a for _, a in onfocus(control) if re.match(r'Control\.Move|Skin\.TimerStart', a)]


def test_page_switch_keeps_the_shared_hero_fade():
    """The fade of the movie hero between home and movies (SharedPageFade) stays: a source with
    one title, or two pages that land on the same title, show no new content to fade."""
    home = load('Home.xml')
    hero = next(c for c in home.iter('control') if c.get('id') == '9300')
    conditions = [a.get('condition') or '' for a in hero.findall('animation')
                  if (a.get('type') or '').lower() == 'conditional']
    assert any('nc.page),movies)' in c for c in conditions)
    assert any('nc.page),home)' in c for c in conditions)
