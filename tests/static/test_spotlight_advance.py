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


def test_hero_art_changes_with_the_title():
    """Poster and logo of a hero change in the frame the title changes: the spotlight list keeps
    the art of the next titles loaded (SpotlightList), so there is nothing to wait for. A
    crossfade (fadetime) would let the old logo shine through after a page switch, longer than
    the page fade."""
    images = [c for c in load('Home.xml').iter('control') if c.get('type') == 'image'
              and re.search(r'Container\(900[01]\)\.ListItem\.Art\((poster|clearlogo)\)', c.findtext('texture') or '')]
    assert len(images) >= 3  # movie hero poster and logo, show hero
    for image in images:
        assert int(image.findtext('fadetime') or 0) == 0, image.findtext('texture')


def test_movie_backdrop_fades_in_on_home_and_movies():
    """The fanart of the movie spotlight stands behind home and movies alike, so it stays visible
    on a switch between them and would crossfade from the old title to the new one in full view.
    Like the hero it fades in from nothing whenever one of the two pages comes up (one
    Conditional animation per page), the crossfade runs under that fade. No Visible animation on
    top, coming from a third page both would run and multiply."""
    home = load('Home.xml')
    group = next(g for g in home.iter('control') if g.get('type') == 'group' and any(
        'Container(9000).ListItem.Art(fanart)' in (i.findtext('texture') or '') for i in g.findall('control')))
    anims = group.findall('animation')
    fades = {}
    for a in anims:
        if (a.get('type') or a.text or '').strip().lower() == 'conditional':
            for page in ('home', 'movies'):
                if 'nc.page),{})'.format(page) in (a.get('condition') or ''):
                    fades[page] = a
    assert set(fades) == {'home', 'movies'}
    for page, a in fades.items():
        assert a.get('reversible') == 'false', page
        assert any((e.get('type') == 'fade' and e.get('start') == '0') for e in a.findall('effect')), page
        assert not [e for e in a.findall('effect') if e.get('type') == 'slide'], page  # a full screen picture
    assert not [a for a in anims if (a.get('type') or a.text or '').strip().lower() == 'visible']
    assert [a for a in anims if (a.get('type') or a.text or '').strip().lower() == 'hidden']
