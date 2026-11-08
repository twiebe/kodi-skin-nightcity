"""The spotlight on a page switch and on a title change.

A page switch on Home leaves each spotlight where it is: home and movies have a movie spotlight of
their own (lists 9000 and 9003, each with its interval), shows has 9001. The buttons of the movie
spotlight stand on home and movies alike and fade in with either page (SharedPageFade); each
page's title, poster and fanart fade in with their page. A title change (autoscroll, left/right on the hero buttons)
is soft: poster or cover, logo and backdrop of the hero crossfade from the old title to the new
one (fadetime)."""
import re

import pytest

from navigation import load

TABS = ('9101', '9102', '9103', '9107')  # home, movies, shows, music
SPOTLIGHTS = r'Container\(900[0123]\)\.ListItem\.Art\('
CROSSFADE = 400


def controls():
    return list(load('Home.xml').iter('control'))


@pytest.mark.parametrize('tab_id', TABS)
def test_page_tab_does_not_move_the_spotlight(tab_id):
    tab = next(c for c in controls() if c.get('id') == tab_id)
    actions = [(o.text or '').strip() for o in tab.findall('onfocus')]
    assert not [a for a in actions if a.startswith('Control.Move') or 'nc_spot_hold' in a], (tab_id, actions)


def hero_images(kinds):
    pattern = re.compile(SPOTLIGHTS + '(' + '|'.join(kinds) + r')\)')
    return [c for c in controls() if c.get('type') == 'image' and pattern.search(c.findtext('texture') or '')]


@pytest.mark.parametrize('kinds,least', [
    (('poster',), 3),           # the movie heroes of home and movies, the show hero; one image per card state (CutCard)
    (('clearlogo',), 3),        # the same three heroes
    (('thumb',), 2),            # music hero cover
    (('fanart', 'artist.fanart'), 4),  # backdrops of the two movie, the show and the music spotlight
])
def test_hero_art_crossfades_on_a_title_change(kinds, least):
    images = hero_images(kinds)
    assert len(images) >= least, kinds
    for image in images:
        assert int(image.findtext('fadetime') or 0) == CROSSFADE, image.findtext('texture')


def test_page_switch_keeps_the_shared_buttons_fade():
    """The movie spotlight's buttons stand on home and movies alike: they fade in whenever one of
    the two pages comes up (one Conditional animation per page)."""
    hero = next(c for c in controls() if c.get('id') == '9300')
    conditions = [a.get('condition') or '' for a in hero.findall('animation')
                  if (a.get('type') or '').lower() == 'conditional']
    assert any('nc.page),movies)' in c for c in conditions)
    assert any('nc.page),home)' in c for c in conditions)
    assert not [a for a in hero.findall('animation') if (a.get('type') or a.text or '').strip().lower() == 'visible']


@pytest.mark.parametrize('list_id,page', [('9000', 'home'), ('9003', 'movies')])
def test_each_movie_spotlight_has_its_own_backdrop(list_id, page):
    """Each page's fanart stands only on its page and fades in and out with it."""
    backdrop = next(g for g in controls() if g.get('type') == 'group' and any(
        'Container({}).ListItem.Art(fanart)'.format(list_id) in (i.findtext('texture') or '') for i in g.findall('control')))
    assert 'nc.page),{})'.format(page) in backdrop.findtext('visible')
    kinds = [(a.get('type') or a.text or '').strip().lower() for a in backdrop.findall('animation')]
    assert 'visible' in kinds and 'hidden' in kinds
