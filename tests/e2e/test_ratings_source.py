"""The ratings of the spotlight titles (docs/media-info-af3.md, "Ratings source").

The service points TMDb Helper at the hero while a hero button has focus (or always with
nc.ratings.spotlight) and keeps what it fetched per title in nc.hero.<container>.*: the hero's
ratings line stays when focus leaves and when the spotlight comes back to the title. Only The
Matrix resolves in TMDb Helper in kodi-dev (TMDb 8.2, no keys for the online ratings).
"""
import time

import pytest

from conftest import action, builtin, cond, info, rpc, screenshot, wait_for
from test_media_info import MOVIE_RATINGS, _open_info, _shown, _visible_of

pytestmark = pytest.mark.e2e

WIDGET = 'Window(Home).Property(TMDbHelper.WidgetContainer)'
KEPT = 'Window(Home).Property(nc.hero.9000.TMDb_Rating)'


def _visible(cid):
    key = 'Control.IsVisible({})'.format(cid)
    return cond(key)[key]


def _label(key):
    return info(key)[key]


def _move_to(title):
    """Move the movie spotlight (random order) to TITLE."""
    wait_for('Integer.IsGreater(Container(9000).NumItems,0)', timeout=30)
    n = int(_label('Container(9000).NumItems'))
    for start in range(0, n, 100):
        keys = ['Container(9000).ListItemAbsolute({}).Label'.format(i) for i in range(start, min(n, start + 100))]
        labels = info(*keys)
        for i, key in enumerate(keys):
            if labels[key] == title:
                current = int(_label('Container(9000).CurrentItem')) - 1
                builtin('Control.Move(9000,{})'.format(start + i - current))
                wait_for('String.IsEqual(Container(9000).ListItem.Label,{})'.format(title))
                return
    pytest.skip('no {} in this Kodi'.format(title))


@pytest.fixture
def no_spotlight_setting():
    """Spotlight ratings on focus only; the TMDb source on (off by default, the only one kodi-dev
    has without keys)."""
    builtin('Skin.Reset(nc.ratings.spotlight)')
    builtin('Skin.SetBool(nc.ratings.show.tmdb)')
    yield
    builtin('Skin.Reset(nc.ratings.spotlight)')
    builtin('Skin.Reset(nc.ratings.show.tmdb)')


def test_hero_keeps_its_ratings_once_fetched(home, no_spotlight_setting):
    # the home fixture leaves focus on the play button: TMDb Helper watches the hero
    _move_to('The Matrix')
    wait_for('String.IsEqual({},9000)'.format(WIDGET))
    wait_for('String.IsEqual({},8.2) + Control.IsVisible(9030)'.format(KEPT), timeout=20)
    screenshot('ratings-hero-focused')
    # a row takes focus: TMDb Helper lets go of the hero, the line stays
    builtin('SetFocus(9202)')
    wait_for('Control.HasFocus(9202) + String.IsEmpty({})'.format(WIDGET))
    assert _visible(9030)
    screenshot('ratings-hero-row')
    # the spotlight moves on and comes back
    builtin('Control.Move(9000,1)')
    wait_for('!String.IsEqual(Container(9000).ListItem.Label,The Matrix)')
    wait_for('!Control.IsVisible(9030)')
    builtin('Control.Move(9000,-1)')
    wait_for('String.IsEqual(Container(9000).ListItem.Label,The Matrix)')
    wait_for('Control.IsVisible(9030)', timeout=2)
    assert _label(KEPT) == '8.2'
    assert not _label(WIDGET)
    screenshot('ratings-hero-back')


def test_hero_ratings_load_on_focus_only_by_default(home, no_spotlight_setting):
    builtin('SetFocus(9101)')
    wait_for('String.IsEmpty({})'.format(WIDGET))
    builtin('SetFocus(9202)')
    time.sleep(0.6)
    assert not _label(WIDGET)
    builtin('SetFocus(9010)')
    wait_for('String.IsEqual({},9000)'.format(WIDGET))


def test_hero_ratings_load_without_focus_with_the_setting(home, no_spotlight_setting):
    builtin('Skin.SetBool(nc.ratings.spotlight)')
    builtin('SetFocus(9202)')
    wait_for('Control.HasFocus(9202)')
    time.sleep(0.6)
    assert _label(WIDGET) == '9000'
    builtin('SetFocus(9101)')
    time.sleep(0.6)
    assert _label(WIDGET) == '9000'


def test_library_rating_only_with_the_setting(home):
    """Jellyfin's community rating (Kodi's default rating) shows only with "Ratings only from
    TMDb Helper" off. On the info page, which reads the movie afresh (Home keeps its spotlight
    items as loaded); the heroes share the line (tests/static/test_ratings_source.py)."""
    movieid = rpc('VideoLibrary.GetMovies', {'filter': {'field': 'title', 'operator': 'is', 'value': 'Bulk 0001'}})
    if not movieid.get('movies'):
        pytest.skip('no Bulk 0001 in this Kodi')
    movieid = movieid['movies'][0]['movieid']
    rpc('VideoLibrary.SetMovieDetails', {'movieid': movieid, 'rating': 7.4})
    try:
        _open_info(movieid)
        wait_for('String.IsEqual(ListItem.Rating,7.4) + String.IsEmpty(Window(Home).Property(TMDbHelper.IsUpdating))')
        time.sleep(1)
        line = _visible_of(MOVIE_RATINGS)
        assert not _shown(line)
        builtin('Skin.SetBool(nc.ratings.library)')
        wait_for(line, timeout=2)
        screenshot('ratings-info-library')
    finally:
        builtin('Skin.Reset(nc.ratings.library)')
        builtin('Dialog.Close(all,true)')
        rpc('VideoLibrary.SetMovieDetails', {'movieid': movieid, 'rating': 0.0})


def test_source_toggle_hides_its_rating(home, no_spotlight_setting):
    """The hero's line keeps TMDb's rating, the TMDb toggle decides whether it shows."""
    _move_to('The Matrix')
    wait_for('String.IsEqual({},8.2) + Control.IsVisible(9030)'.format(KEPT), timeout=20)
    builtin('Skin.Reset(nc.ratings.show.tmdb)')
    wait_for('!Control.IsVisible(9030)', timeout=2)
    builtin('Skin.SetBool(nc.ratings.show.tmdb)')
    wait_for('Control.IsVisible(9030)', timeout=2)


def test_rating_settings_have_their_category(home):
    """Skin settings > Ratings: the two settings, then one toggle per source with its
    description; OK switches them."""
    builtin('ActivateWindow(SkinSettings)')
    try:
        wait_for('Window.IsActive(skinsettings)')
        builtin('SetFocus(9007)')
        wait_for('Control.HasFocus(9007) + Control.IsVisible(800)')
        action('right')
        wait_for('Control.HasFocus(621) + !Skin.HasSetting(nc.ratings.library)')
        assert 'Jellyfin' in _label('Control.GetLabel(6)')
        action('down')
        wait_for('Control.HasFocus(622) + !Skin.HasSetting(nc.ratings.spotlight)')
        assert 'online requests' in _label('Control.GetLabel(6)')
        action('down')
        wait_for('Control.HasFocus(631)')
        assert 'Top 250' in _label('Control.GetLabel(6)')
        action('down', 'down', 'down', 'down', 'down')
        wait_for('Control.HasFocus(636)')
        assert 'Trakt account' in _label('Control.GetLabel(6)')
        screenshot('ratings-settings')
        action('select')
        wait_for('Skin.HasSetting(nc.ratings.show.trakt)')
        action('left')
        wait_for('Control.HasFocus(9007)')
    finally:
        builtin('Skin.Reset(nc.ratings.show.trakt)')
        builtin('Dialog.Close(all,true)')
        builtin('ReplaceWindow(Home)')
        wait_for('Window.IsActive(home)')


def test_show_hero_keeps_what_tmdb_helper_had(home, no_spotlight_setting):
    """The show hero (9001): kodi-dev's shows have no TMDb data, so what is kept is the title
    with no ratings, and it stays once focus moves to a row."""
    builtin('SetFocus(9103)')
    wait_for('String.IsEqual(Window(Home).Property(nc.page),shows) + Integer.IsGreater(Container(9001).NumItems,0)',
             timeout=30)
    builtin('SetFocus(9551)')
    wait_for('String.IsEqual({},9001)'.format(WIDGET))
    wait_for('Integer.IsEqual(Container(9001).ListItem.DBID,Window(Home).Property(nc.hero.9001.dbid))', timeout=10)
    builtin('SetFocus(9510)')
    wait_for('String.IsEmpty({})'.format(WIDGET))
    assert _label('Window(Home).Property(nc.hero.9001.dbtype)') == 'tvshow'
    builtin('SetFocus(9101)')
