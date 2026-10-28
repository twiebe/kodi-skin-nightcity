"""TMDb lists never show the page before.

The info page stays in memory between pages (CGUIDialogVideoInfo is KEEP_IN_MEMORY), so its
lists keep their items when it closes and show them again when it opens for the next title,
until their new content is loaded; an empty path does not clear them, and IsUpdating misses the
time before a list starts loading (similar movies wait for the cast) and its last frame. Every
TMDb item carries the request it came from (param.tmdb_id, param.query, param.info, ...): a list
shows only while its first item's request matches the page (TmdbFresh<id>, Includes_Tmdb.xml)
and fades out otherwise. It stays visible to Kodi, so it keeps loading."""
import re

import pytest

from conftest import ROOT, parse
from navigation import load

SKIN = ROOT / '1080i'
LISTS = {'5500': 'DialogVideoInfo.xml', '5300': 'DialogVideoInfo.xml', '5510': 'DialogVideoInfo.xml',
         '6501': 'Custom_1141_OSDCast.xml'}


def _expression(name):
    for path in SKIN.glob('Includes*.xml'):
        for el in parse(path).iter('expression'):
            if el.get('name') == name:
                return el.text.strip()
    raise AssertionError(name)


def _holds(expression, values):
    """Evaluate a Kodi condition; infolabels come from `values` (missing ones are empty), the
    second argument of String.IsEqual is an infolabel when `values` knows it, else a literal."""
    def atom(m):
        text = m.group(0)
        eq = re.match(r'String\.IsEqual\((.+),(.*)\)$', text)
        if eq:
            left, right = eq.group(1), eq.group(2)
            return str(values.get(left, '') == values.get(right, right if not re.match(r'\w+\(|ListItem\.|VideoPlayer\.', right) else ''))
        empty = re.match(r'String\.IsEmpty\((.+)\)$', text)
        if empty:
            return str(not values.get(empty.group(1), ''))
        raise AssertionError('unknown atom ' + text)
    atoms = re.compile(r'String\.Is(?:Equal|Empty)\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)')
    text = atoms.sub(atom, expression)
    text = text.replace('[', '(').replace(']', ')').replace('+', ' and ').replace('|', ' or ').replace('!', ' not ')
    return eval(text, {})


def _item(cid, **params):
    return {'Container({}).ListItem(0).Property(param.{})'.format(cid, k): v for k, v in params.items()}


@pytest.mark.parametrize('cid', sorted(LISTS))
def test_list_fades_while_it_shows_another_page(cid):
    lists = [c for c in load(LISTS[cid]).iter('control') if c.get('id') == cid]
    assert len(lists) == 1, cid
    fades = [(a.get('effect'), a.get('start'), a.get('end'), a.get('time'), a.get('condition'), a.text) for a in lists[0].findall('animation')]
    assert ('fade', '100', '0', '0', '!$EXP[TmdbFresh{}]'.format(cid), 'Conditional') in fades


TMDB_MOVIE = {'ListItem.DBType': 'movie', 'ListItem.Property(tmdb_id)': '1401586'}
LIBRARY_MOVIE = {'ListItem.DBType': 'movie', 'ListItem.IMDBNumber': 'tt0133093', 'ListItem.Title': 'The Matrix'}
EPISODE = {'ListItem.DBType': 'episode', 'ListItem.TVShowTitle': 'Breaking Bad',
           'Container(5100).ListItem.Season': '1', 'Container(5100).ListItem.Episode': '3'}
PERSON = {'ListItem.DBType': 'video', 'ListItem.Property(tmdb_type)': 'person', 'ListItem.Property(tmdb_id)': '6384'}


@pytest.mark.parametrize('page,items,fresh', [
    (TMDB_MOVIE, _item('5500', info='cast', tmdb_id='1401586'), True),
    (TMDB_MOVIE, _item('5500', info='cast', tmdb_id='603'), False),  # the film before
    (TMDB_MOVIE, {}, False),  # nothing loaded yet
    (LIBRARY_MOVIE, _item('5500', info='cast', tmdb_id='603', imdb_id='tt0133093', query='The Matrix'), True),
    (LIBRARY_MOVIE, _item('5500', info='cast', tmdb_id='1401586'), False),
    (EPISODE, _item('5500', info='cast', tmdb_type='tv', query='Breaking Bad', season='1', episode='3'), True),
    (EPISODE, _item('5500', info='cast', tmdb_type='tv', query='Breaking Bad', season='1', episode='2'), False),
    (EPISODE, _item('5500', info='cast', tmdb_type='movie', tmdb_id='1401586'), False),
    (dict(TMDB_MOVIE, **{'Window(Home).Property(nc.info.tab)': 'crew', 'Window(Home).Property(nc.info.live)': '1'}),
     _item('5500', info='cast', tmdb_id='1401586'), False),  # the cast while the crew loads
    (dict(TMDB_MOVIE, **{'Window(Home).Property(nc.info.tab)': 'crew', 'Window(Home).Property(nc.info.live)': '1'}),
     _item('5500', info='crew', tmdb_id='1401586'), True),
])
def test_cast_row_fresh(page, items, fresh):
    assert _holds(_expression('TmdbFresh5500'), dict(page, **items)) is fresh


@pytest.mark.parametrize('page,items,fresh', [
    (TMDB_MOVIE, _item('5300', info='recommendations', tmdb_id='1401586'), True),
    (TMDB_MOVIE, _item('5300', info='recommendations', tmdb_id='604'), False),
    (LIBRARY_MOVIE, _item('5300', info='recommendations', imdb_id='tt0133093', query='The Matrix'), True),
    (LIBRARY_MOVIE, _item('5300', info='recommendations', tmdb_id='1401586'), False),
])
def test_similar_row_fresh(page, items, fresh):
    assert _holds(_expression('TmdbFresh5300'), dict(page, **items)) is fresh


@pytest.mark.parametrize('page,items,fresh', [
    (PERSON, _item('5510', info='stars_in_movies', tmdb_id='6384'), True),
    (PERSON, _item('5510', info='stars_in_movies', tmdb_id='1234'), False),
    (dict(PERSON, **{'Window(Home).Property(nc.info.tab)': 'tv', 'Window(Home).Property(nc.info.live)': '1'}),
     _item('5510', info='stars_in_movies', tmdb_id='6384'), False),
    (dict(PERSON, **{'Window(Home).Property(nc.info.tab)': 'tv', 'Window(Home).Property(nc.info.live)': '1'}),
     _item('5510', info='stars_in_tvshows', tmdb_id='6384'), True),
    (dict(PERSON, **{'Window(Home).Property(nc.info.tab)': 'crew', 'Window(Home).Property(nc.info.live)': '1'}),
     _item('5510', info='crew_in_both', tmdb_id='6384'), True),
])
def test_person_credits_fresh(page, items, fresh):
    assert _holds(_expression('TmdbFresh5510'), dict(page, **items)) is fresh


MOVIE_PLAYING = {'VideoPlayer.Title': 'The Matrix', 'VideoPlayer.IMDBNumber': 'tt0133093',
                 'Window(Home).Property(TMDbHelper.Player.TMDb_ID)': '603', 'VideoPlayer.Content(movies)': True}
EPISODE_PLAYING = {'VideoPlayer.TVShowTitle': 'Breaking Bad', 'VideoPlayer.Season': '1', 'VideoPlayer.Episode': '3'}


@pytest.mark.parametrize('page,items,fresh', [
    (MOVIE_PLAYING, _item('6501', info='cast', tmdb_id='603'), True),
    (MOVIE_PLAYING, _item('6501', info='cast', tmdb_id='604'), False),  # the video before
    ({'VideoPlayer.Title': 'The Matrix', 'VideoPlayer.IMDBNumber': 'tt0133093'}, _item('6501', info='cast', imdb_id='tt0133093', query='The Matrix'), True),
    (EPISODE_PLAYING, _item('6501', info='cast', query='Breaking Bad', season='1', episode='3'), True),
    (EPISODE_PLAYING, _item('6501', info='cast', query='Breaking Bad', season='1', episode='2'), False),
    (dict(MOVIE_PLAYING, **{'Window(Home).Property(nc.osd.credits)': 'crew'}), _item('6501', info='cast', tmdb_id='603'), False),
    (dict(MOVIE_PLAYING, **{'Window(Home).Property(nc.osd.credits)': 'crew'}), _item('6501', info='crew', tmdb_id='603'), True),
])
def test_osd_cast_row_fresh(page, items, fresh):
    assert _holds(_expression('TmdbFresh6501'), dict(page, **items)) is fresh


SEARCH_FRESH = 'String.IsEqual(Container({}).ListItem(0).Property(param.query),Window(Home).Property(nc.search))'


def _row_box(rid):
    for path in SKIN.glob('Includes*.xml'):
        for el in parse(path).iter('include'):
            if el.get('content') == 'RowBox':
                params = {p.get('name'): p.get('value') for p in el.findall('param')}
                if params.get('id') == rid:
                    return params
    raise AssertionError(rid)


def test_tmdb_search_rows_never_show_the_search_before():
    """A new search keeps the TMDb rows on the results of the search before for a few seconds,
    without IsUpdating: a row counts as loaded only once its first item answers this search."""
    for rid, loader in (('9704', '9724'), ('9705', '9725')):
        params = _row_box(rid)
        assert params['loader'] == loader
        assert params['fresh'] == SEARCH_FRESH.format(loader), rid
        # the row itself shows its last items until it loaded the new search: faded out
        assert params['freshrow'] == SEARCH_FRESH.format(rid), rid


def test_row_box_waits_for_fresh_items():
    box = next(el for path in SKIN.glob('Includes*.xml') for el in parse(path).iter('include')
               if el.get('name') == 'RowBox')
    defaults = {p.get('name'): p.get('default') for p in box.findall('param')}
    assert defaults['fresh'] == defaults['freshrow'] == 'true'
    group = box.find('definition/control')
    assert group.findtext('visible') == ('[Integer.IsGreater(Container($PARAM[loader]).NumItems,0) + [$PARAM[fresh]]]'
                                         ' | [Container($PARAM[loader]).IsUpdating + !Integer.IsGreater(Container($PARAM[loader]).NumItems,0)]')
    row = next(c for c in group.iter('control') if c.get('id') == '$PARAM[id]')
    assert row.findtext('visible') == '!$PARAM[wait] | [Integer.IsGreater(Container($PARAM[loader]).NumItems,0) + [$PARAM[fresh]]]'
    fades = [a for a in row.findall('animation') if a.get('condition') == '![$PARAM[freshrow]]']
    assert [(a.get('effect'), a.get('end'), a.get('time'), a.text) for a in fades] == [('fade', '0', '0', 'Conditional')]
