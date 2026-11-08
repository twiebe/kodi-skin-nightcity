"""The spotlight follows the focused row title and stands still meanwhile (Includes_Home.xml
FollowHero). kodi-dev's library: Kdev movies and Kdev Show; rows 9202 new movies, 9203 new episodes
on home (Kodi lists the new episodes as their shows), 9401 on movies, 9502 on shows."""
import time

import pytest

from conftest import action, builtin, cond, info, rpc, screenshot, wait_for

pytestmark = pytest.mark.e2e

INTERVAL = 10  # s, the shortest the settings have
FOLLOWS = 'Control.IsVisible(9302)'


def true(condition):
    return cond(condition)[condition]


def label(key):
    return info(key)[key]


def to_page(tab_id, page):
    builtin('SetFocus({})'.format(tab_id))
    wait_for('String.IsEqual(Window(Home).Property(nc.page),{})'.format(page))


def focus_row(row):
    wait_for('Integer.IsGreater(Container({}).NumItems,0)'.format(row), timeout=30)
    builtin('SetFocus({})'.format(row))
    wait_for('Control.HasFocus({})'.format(row))


def reopen_home():
    builtin('ReplaceWindow(Settings)')  # Home reads the slots and the interval when opened
    wait_for('Window.IsActive(settings)')
    builtin('ReplaceWindow(Home)')
    wait_for('Window.IsActive(home)')


@pytest.fixture
def short_interval(home):
    builtin('Skin.SetString(SpotlightInterval,{})'.format(INTERVAL))
    reopen_home()
    wait_for('Integer.IsGreater(Container(9000).NumItems,2)', timeout=30)
    yield
    builtin('Skin.Reset(SpotlightInterval)')
    reopen_home()


@pytest.fixture
def back_to_home(home):
    yield
    to_page(9101, 'home')


def assert_shows_card():
    """The hero's title is the card's, the spotlight's own stands hidden."""
    title = label('ListItem.Title')
    wait_for('String.Contains(Control.GetLabel(9320),{})'.format(title))
    assert true(FOLLOWS)
    return title


def test_spotlight_itself_does_not_follow(home):
    builtin('SetFocus(9010)')
    wait_for('Control.HasFocus(9010)')
    assert not true(FOLLOWS)


def test_follows_a_movie(back_to_home):
    focus_row(9202)
    assert label('ListItem.DBType') == 'movie'
    assert_shows_card()
    screenshot('follow-movie')
    first = label('ListItem.Title')
    action('right')
    wait_for('!String.IsEqual(ListItem.Title,{})'.format(first))
    assert_shows_card()


def test_follows_a_show_on_the_movie_spotlight(back_to_home):
    """Home's spotlight holds movies; its hero shows the show under the cursor."""
    focus_row(9203)
    assert label('ListItem.DBType') == 'tvshow'
    assert_shows_card()
    assert label('ListItem.Genre') in label('Control.GetLabel(9322)')
    screenshot('follow-show')


@pytest.fixture
def episode_in_progress(home):
    episode = rpc('VideoLibrary.GetEpisodes', {'limits': {'end': 1}})['episodes'][0]['episodeid']
    rpc('VideoLibrary.SetEpisodeDetails', {'episodeid': episode, 'resume': {'position': 30, 'total': 60}})
    builtin('ReloadSkin()')  # Home's rows keep their lists through a window change
    wait_for('Window.IsActive(home)', timeout=20)
    yield
    rpc('VideoLibrary.SetEpisodeDetails', {'episodeid': episode, 'resume': {'position': 0, 'total': 0}})
    builtin('ReloadSkin()')
    wait_for('Window.IsActive(home)', timeout=20)


def test_follows_an_episode_with_show_and_number_in_the_kicker(episode_in_progress, back_to_home):
    """Continue watching on home, the user's own example."""
    focus_row(9201)
    assert label('ListItem.DBType') == 'episode'
    assert_shows_card()
    season, episode, show = (label('ListItem.' + k) for k in ('Season', 'Episode', 'TVShowTitle'))
    number = 'S{:02d}E{:02d}'.format(int(season), int(episode))
    kicker = label('Control.GetLabel(9322)').upper()
    assert show.upper() in kicker and number in kicker
    screenshot('follow-episode')


def test_follows_a_show_on_the_shows_page(back_to_home):
    to_page(9103, 'shows')
    focus_row(9502)
    assert label('ListItem.DBType') == 'tvshow'
    assert_shows_card()
    screenshot('follow-show-on-shows')


def test_follows_on_the_movies_page(back_to_home):
    to_page(9102, 'movies')
    focus_row(9401)
    assert_shows_card()


def test_timer_stands_while_following_and_starts_over(short_interval):
    key = 'Container(9000).CurrentItem'
    focus_row(9202)
    assert_shows_card()
    position, title = label(key), label('Container(9000).ListItem.Title')
    time.sleep(INTERVAL + 4)
    assert label(key) == position
    builtin('SetFocus(9010)')
    wait_for('Control.HasFocus(9010)')
    back = time.time()
    assert not true(FOLLOWS)
    assert label('Container(9000).ListItem.Title') == title
    assert title.upper() in label('Control.GetLabel(9020)').upper()
    screenshot('follow-back-on-spotlight')
    time.sleep(INTERVAL - 3)
    assert label(key) == position  # the interval started anew
    wait_for('!Integer.IsEqual({},{})'.format(key, position), timeout=8)
    assert time.time() - back >= INTERVAL - 1


@pytest.fixture
def genre_tabs(short_interval):
    """The seeded movies have no genres: give them some and have the service count them. The tabs
    of the genre row are its cards that are no title."""
    movies = rpc('VideoLibrary.GetMovies', {'limits': {'end': 3}})['movies']
    for movie, genre in zip(movies, ('Action', 'Comedy', 'Drama')):
        rpc('VideoLibrary.SetMovieDetails', {'movieid': movie['movieid'], 'genre': [genre]})
    builtin('NotifyAll(nightcity,genres)')
    wait_for('!String.IsEmpty(Window(Home).Property(nc.genre.1.id))', timeout=20)
    reopen_home()
    yield
    for movie in movies:
        rpc('VideoLibrary.SetMovieDetails', {'movieid': movie['movieid'], 'genre': []})
    builtin('ClearProperty(nc.genre.id,home)')
    builtin('ClearProperty(nc.genre.label,home)')
    builtin('NotifyAll(nightcity,genres)')
    to_page(9101, 'home')
    reopen_home()


def test_non_title_card_leaves_the_spotlight_running(genre_tabs):
    to_page(9102, 'movies')
    wait_for('Control.IsVisible(9431)', timeout=20)
    builtin('SetFocus(9431)')
    wait_for('Control.HasFocus(9431)')
    assert not true(FOLLOWS)
    screenshot('follow-genre-tab')
    key = 'Container(9000).CurrentItem'
    position = label(key)
    wait_for('!Integer.IsEqual({},{})'.format(key, position), timeout=INTERVAL + 3)
    # a card of that genre below the tabs is a title again
    action('down')
    wait_for(FOLLOWS)


def test_row_to_top_menu_is_the_spotlight_at_once(home):
    focus_row(9202)
    assert true(FOLLOWS)
    builtin('SetFocus(9101)')
    wait_for('Control.HasFocus(9101)')
    assert not true(FOLLOWS)


def test_up_from_a_row_reaches_the_buttons_and_play_acts_on_the_spotlight(back_to_home):
    focus_row(9202)
    assert true(FOLLOWS)
    builtin('Skin.TimerStart(nc_spot_hold)')
    spotlight = label('Container(9000).ListItem.Title')
    action('up')
    wait_for('Control.HasFocus(9010)')
    assert not true(FOLLOWS)
    assert label('Container(9000).ListItem.Title') == spotlight
    action('select')
    try:
        wait_for('Player.HasVideo', timeout=20)
        wait_for('String.IsEqual(VideoPlayer.Title,{})'.format(spotlight), timeout=10)
    finally:
        if rpc('Player.GetActivePlayers'):
            rpc('Player.Stop', {'playerid': 1})


def test_up_from_a_row_on_the_shows_page_reaches_the_buttons(back_to_home):
    to_page(9103, 'shows')
    focus_row(9502)
    assert true(FOLLOWS)
    action('up')
    wait_for('Control.HasFocus(9551)')
    assert not true(FOLLOWS)


def test_info_page_from_a_row_and_back_still_follows(back_to_home):
    focus_row(9202)
    title = assert_shows_card()
    action('info')
    wait_for('Window.IsActive(movieinformation)')
    action('back')
    wait_for('!Window.IsActive(movieinformation) + Control.HasFocus(9202)')
    wait_for(FOLLOWS)
    assert label('ListItem.Title') == title
    assert_shows_card()


def test_no_spotlight_the_preview_shows_the_card(home):
    """Without spotlight the hero stays and previews a title (test_peek_hero.py); on a card the
    preview of its row shows it, the follow hero stays out."""
    builtin('Skin.SetString(SpotlightSource,off)')
    try:
        reopen_home()
        focus_row(9202)
        assert label('ListItem.DBType') == 'movie'
        wait_for('Control.IsVisible(9362) + !' + FOLLOWS)
        screenshot('follow-spotlight-off')
    finally:
        builtin('Skin.Reset(SpotlightSource)')
        reopen_home()


def test_page_switch_runs_with_the_spotlight_back(back_to_home):
    """Off a row to the tabs and over to the next page: the spotlight title stands as it was."""
    focus_row(9202)
    builtin('Skin.TimerStart(nc_spot_hold)')
    title = label('Container(9000).ListItem.Title')
    to_page(9102, 'movies')
    assert not true(FOLLOWS)
    assert true('Control.IsVisible(9300)')
    assert label('Container(9000).ListItem.Title') == title


@pytest.fixture
def tmdb_ratings(back_to_home):
    """The TMDb source on (off by default, the only one kodi-dev has without keys)."""
    builtin('Skin.SetBool(nc.ratings.show.tmdb)')
    yield
    builtin('Skin.Reset(nc.ratings.show.tmdb)')


def to_card(title):
    focus_row(9202)
    builtin('SetFocus(9202,0,absolute)')
    for _ in range(int(label('Container(9202).NumItems'))):
        if label('ListItem.Title') == title:
            return
        action('right')
    pytest.skip('no {} in this Kodi'.format(title))


HELPER_TITLE = 'Window(Home).Property(TMDbHelper.ListItem.base_label)'
POINTED = 'Window(Home).Property(TMDbHelper.WidgetContainer)'


def test_ratings_of_a_card_from_a_lookup_of_its_own(tmdb_ratings):
    """The Matrix has TMDb data, Kdev Alpha none. Standing on Kdev Alpha first takes TMDb Helper
    off any title it still had from the spotlight: The Matrix's ratings are its own lookup's, and
    stay out of the others and the spotlight's."""
    to_card('Kdev Alpha')
    wait_for('String.IsEqual({},Kdev Alpha)'.format(HELPER_TITLE), timeout=6)
    wait_for('String.IsEqual(Window(Home).Property(nc.kept.follow.dbid),{})'.format(label('ListItem.DBID')), timeout=5)
    assert not true('Control.IsVisible(9324)')
    to_card('The Matrix')
    wait_for('String.IsEqual(Window(Home).Property(nc.kept.follow.TMDb_Rating),8.2) + Control.IsVisible(9324)', timeout=20)
    screenshot('follow-ratings')
    to_card('Kdev Alpha')
    wait_for('!Control.IsVisible(9324)')
    time.sleep(1.5)
    assert not true('Control.IsVisible(9324)')  # nothing of The Matrix lands on this card
    if label('Container(9000).ListItem.Title') != 'The Matrix':
        assert not label('Window(Home).Property(nc.kept.9000.TMDb_Rating)')


def test_tmdb_helper_only_looks_after_the_cursor_stood_still(tmdb_ratings):
    focus_row(9202)
    start = time.time()
    wait_for('String.IsEqual({},9202)'.format(POINTED), timeout=5)
    assert 1.2 <= time.time() - start <= 2.2
    time.sleep(3)  # lets go once it is done with the card
    wait_for('String.IsEmpty({})'.format(POINTED), timeout=20)
    title = label(HELPER_TITLE)
    for direction in ('right', 'left') * 4:
        action(direction, delay=0.25)
        assert not label(POINTED)
    assert label(HELPER_TITLE) == title


@pytest.fixture
def trending_row(tmdb_ratings):
    """TMDb Helper's own list: cards without a library id."""
    builtin('Skin.SetString(nc.home.slot1,trending)')
    builtin('ReloadSkin()')
    wait_for('Window.IsActive(home)', timeout=20)
    try:
        wait_for('Integer.IsGreater(Container(9201).NumItems,2)', timeout=30)
    except AssertionError:
        pytest.skip('no trending list from TMDb')
    yield
    builtin('Skin.Reset(nc.home.slot1)')
    builtin('ReloadSkin()')
    wait_for('Window.IsActive(home)', timeout=20)


def test_ratings_of_a_card_without_a_library_id(trending_row):
    builtin('SetFocus(9201,2,absolute)')
    wait_for('Control.HasFocus(9201)')
    assert not label('ListItem.DBID')
    assert_shows_card()
    title = label('ListItem.Label')
    wait_for('String.IsEqual(Window(Home).Property(nc.kept.follow.label),ListItem.Label) + '
             '!String.IsEmpty(Window(Home).Property(nc.kept.follow.TMDb_Rating))', timeout=20)
    wait_for('Control.IsVisible(9324)')
    action('right')
    wait_for('!String.IsEqual(ListItem.Label,{})'.format(title.replace(',', '')))
    assert not true('Control.IsVisible(9324)')  # not those of the card before
