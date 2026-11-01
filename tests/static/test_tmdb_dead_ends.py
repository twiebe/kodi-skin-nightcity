"""TMDb navigation without dead ends: the info page in every state its TMDb lists can be in, and
the cast row over the playing video.

For each state (page kind, lists loaded, loading or empty, chosen tab, inside a chain or not)
focus.Page proves: something takes the focus, every control shown is reachable, every reachable
control has a way back to the top row (whose Up leaves the page), and OK on every list item does
something.
"""
import itertools

import pytest

from focus import Page, State

INFO = 'DialogVideoInfo.xml'
OSD_CAST = 'Custom_1141_OSDCast.xml'

KINDS = {
    'library movie': dict(dbtype='movie', dbid=True),
    'library show': dict(dbtype='tvshow', dbid=True),
    'library episode': dict(dbtype='episode', dbid=True),
    'tmdb movie': dict(dbtype='movie', tmdb_type='movie'),
    'tmdb show': dict(dbtype='tvshow', tmdb_type='tv'),
    'person': dict(dbtype='video', tmdb_type='person'),
}
LOADS = ('items', 'updating', 'empty')
# infobools of the play and resume buttons and of Kodi's own cast list on an episode page
EXTRA = {
    'ListItem.IsResumable': False,
    'Container(5100).ListItem.IsResumable': False,
    'Container(5901).ListItem.IsResumable': False,
    'String.IsEqual(Container(5100).ListItem.DBID,ListItem.DBID)': True,
    'String.IsEqual(Window(Home).Property(nc.info.ep.id),Container(5100).ListItem.DBID)': True,
    # a plot that fits its box (test_plot_text.py has long and missing ones)
    'Container(9050).HasNext': False,
    'Container(9051).HasNext': False,
    'Container(9052).HasNext': False,
    'String.IsEmpty(ListItem.Plot)': False,
    'String.IsEmpty(Container(5100).ListItem.Plot)': False,
}


def _info_states():
    for kind, item in KINDS.items():
        person = item.get('tmdb_type') == 'person'
        tabs = ('', 'movies', 'tv', 'crew') if person else ('', 'cast', 'crew')
        episode = item['dbtype'] == 'episode'
        # a person page only opens in a chain
        chains = ('True',) if person else ('', 'True')
        # the credits list of the other kind of page is hidden but keeps the items of the page
        # before (a page opens in the same dialog): Container(5500).NumItems on a person page
        for credits, other, kodi_cast, similar, tab, chain in itertools.product(
                LOADS, ('stale', 'empty'), ('items', 'empty'), ('items', 'empty'), tabs, chains):
            # similar movies load after the cast: before, their items belong to the page before
            containers = {'5510' if person else '5500': credits, '5500' if person else '5510': other,
                          '50': kodi_cast, '5300': similar if credits == 'items' or similar == 'empty' else 'stale',
                          '5901': 'empty', '5100': 'items' if episode else 'empty',
                          '5200': 'items' if episode else 'empty'}
            props = {'nc.info.tab': tab, 'TMDbHelper.Instance': chain,
                     'nc.info.ep.query': 'season=1&episode=1' if episode else ''}
            yield '{} {} other {} {} {} {} {}'.format(kind, credits, other, kodi_cast, similar, tab or '-', chain or '-'), \
                State(containers=containers, props=props, extra=EXTRA, **item)


INFO_STATES = dict(_info_states())


@pytest.fixture(scope='module')
def info_page():
    return Page(INFO)


@pytest.mark.parametrize('label', sorted(INFO_STATES))
def test_info_page_has_no_dead_end(info_page, label):
    assert info_page.report(INFO_STATES[label], offscreen={'5901', '9098', '9099'}) == []


def test_up_on_the_top_row_leaves_the_page(info_page):
    """Up on any button of the top row goes to the plot, Up there is Back: one page back in a
    chain, else to the row the page was opened from (test_plot_text.py)."""
    texts = ('9060', '9061', '9062')
    for label, state in INFO_STATES.items():
        for cid in ('9001', '9002', '9003', '9004'):
            if info_page.can_focus(cid, state):
                text, ran = info_page.move(cid, 'onup', state)
                assert text in texts and not ran, (label, cid)
                assert 'Action(Back)' in info_page.move(text, 'onup', state)[1], (label, cid)


def _osd_states():
    for cast, bio, tab in itertools.product(('items', 'updating'), ('items', 'empty', 'updating'), ('', 'cast', 'crew')):
        yield 'cast {} bio {} tab {}'.format(cast, bio, tab or '-'), \
            State(containers={'6501': cast, '6599': bio}, props={'nc.osd.credits': tab})


@pytest.mark.parametrize('label,state', list(_osd_states()))
def test_osd_cast_row_has_no_dead_end(label, state):
    assert Page(OSD_CAST).report(state, offscreen={'6599'}) == []


def _playing_states():
    """The page of the movie that plays (InfoMoviePlaying): its resume and from start hide. In a
    chain over the player (a person, one of their films) and outside one (the library while it
    plays), a library movie, a TMDb title with its library copy (5901) and one without, the cast
    loaded, loading or empty; a resumable movie too (from start would show)."""
    kinds = {'library movie': dict(dbtype='movie', dbid=True, copy='empty'),
             'tmdb movie with copy': dict(dbtype='movie', tmdb_type='movie', copy='items'),
             'tmdb movie': dict(dbtype='movie', tmdb_type='movie', copy='empty')}
    for (kind, item), cast, chain, resumable in itertools.product(
            kinds.items(), LOADS, ('', 'True'), (False, True)):
        item = dict(item)
        copy = item.pop('copy')
        containers = {'5500': cast, '5510': 'empty', '50': 'empty', '5300': 'empty', '5901': copy,
                      '5100': 'empty', '5200': 'empty'}
        extra = dict(EXTRA, **{'InfoMoviePlaying': True, 'ListItem.IsResumable': resumable,
                               'Container(5901).ListItem.IsResumable': resumable})
        yield '{} cast {} {} {}'.format(kind, cast, 'chain' if chain else 'no chain',
                                        'resumable' if resumable else 'not started'), \
            State(containers=containers, props={'TMDbHelper.Instance': chain}, extra=extra, **item)


PLAYING_STATES = dict(_playing_states())


@pytest.mark.parametrize('label', sorted(PLAYING_STATES))
def test_page_of_the_playing_movie_has_no_dead_end(info_page, label):
    state = PLAYING_STATES[label]
    assert info_page.report(state, offscreen={'5901', '9098', '9099'}) == []
    # no way to play it again from the start; in a chain the way back to the video takes the focus
    assert not info_page.can_focus('9001', state) and not info_page.can_focus('9002', state)
    if state.props['TMDbHelper.Instance']:
        assert info_page.start(state) == '9004', label
