"""The combo row, continue watching + next up in one row (CATALOGUE 'combo'): what was started on
the left, then a split (LookRowSplit on the first next-up card), then next up without the shows a
started episode stands for already (nightcity.combo). kodi-dev's library: The Matrix started,
Breaking Bad with its first episode watched (next up), Kdev Show with its first episode started
(continue, and so not in next up). Slot 5 of home: list 9205, group 9215, split loader 9275."""
import pathlib
import shutil
import time

import pytest

from conftest import SKIN_ID, action, builtin, cond, info, rpc, screenshot, wait_for

pytestmark = pytest.mark.e2e

ROW, SPLIT = 9205, 9275
FOLLOWS = 'Control.IsVisible(9302)'
SHOTS = pathlib.Path('/dist/combo-row')


def true(condition):
    return cond(condition)[condition]


def label(key):
    return info(key)[key]


def keep_shot(name):
    """A screenshot for the report, per skin."""
    path = screenshot(name)
    try:
        SHOTS.mkdir(parents=True, exist_ok=True)
        shutil.copy(path, SHOTS / '{}-{}.png'.format(SKIN_ID.split('.')[1], name))
    except OSError:
        pass


def _episodes(show):
    return [e for e in rpc('VideoLibrary.GetEpisodes', {'properties': ['showtitle', 'season', 'episode']})['episodes']
            if e['showtitle'] == show]


def _stick(get, put, value):
    """Set a resume point or play count until it sticks: jellyfin-kodi writes the server's value
    back a moment later."""
    stable = 0
    for _ in range(30):
        if get() == value:
            stable += 1
            if stable == 3:
                return
        else:
            stable = 0
            put()
        time.sleep(0.5)
    raise AssertionError('library value did not stick')


def episode_state(episodeid, position=0, playcount=0):
    def get():
        d = rpc('VideoLibrary.GetEpisodeDetails', {'episodeid': episodeid, 'properties': ['resume', 'playcount']})['episodedetails']
        return int(d['resume']['position']) > 0, d['playcount'] > 0
    _stick(get, lambda: rpc('VideoLibrary.SetEpisodeDetails', {
        'episodeid': episodeid, 'playcount': playcount, 'resume': {'position': position, 'total': 600 if position else 0}}),
        (position > 0, playcount > 0))


def movie_state(movieid, position=0):
    def get():
        d = rpc('VideoLibrary.GetMovieDetails', {'movieid': movieid, 'properties': ['resume']})['moviedetails']
        return int(d['resume']['position']) > 0
    _stick(get, lambda: rpc('VideoLibrary.SetMovieDetails', {
        'movieid': movieid, 'resume': {'position': position, 'total': 600 if position else 0}}), position > 0)


def reopen_home():
    builtin('ReplaceWindow(Settings)')  # Home reads the slots when opened
    wait_for('Window.IsActive(settings)')
    builtin('ReplaceWindow(Home)')
    wait_for('Window.IsActive(home)')


def items():
    n = int(label('Container({}).NumItems'.format(ROW)) or 0)
    return [(label('Container({}).ListItemAbsolute({}).DBType'.format(ROW, i)),
             label('Container({}).ListItemAbsolute({}).Label'.format(ROW, i))) for i in range(n)]


@pytest.fixture
def library(home):
    matrix = next(m['movieid'] for m in rpc('VideoLibrary.GetMovies')['movies'] if m['label'] == 'The Matrix')
    bb, kdev = _episodes('Breaking Bad'), _episodes('Kdev Show')
    if not bb or not kdev:
        pytest.skip('kodi-dev library without its two shows')
    movie_state(matrix, 300)
    episode_state(bb[0]['episodeid'], playcount=1)
    episode_state(kdev[0]['episodeid'], position=120)
    state = {'matrix': matrix, 'bb': bb, 'kdev': kdev}
    try:
        yield state
    finally:
        movie_state(matrix)
        for e in bb + kdev:
            episode_state(e['episodeid'])


@pytest.fixture
def combo(library):
    builtin('Skin.SetString(nc.home.slot5,combo)')
    reopen_home()
    try:
        yield library
    finally:
        builtin('Skin.Reset(nc.home.slot5)')
        reopen_home()


def wait_for_items(expected, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        if items() == expected:
            return
        time.sleep(0.5)
    assert items() == expected


def focus(position):
    builtin('SetFocus({},{},absolute)'.format(ROW, position))
    wait_for('Control.HasFocus({}) + Integer.IsEqual(Container({}).CurrentItem,{})'.format(ROW, ROW, position + 1))


SPLIT_HERE = 'Integer.IsEqual(ListItem.CurrentItem,Container({0}).NumItems) + Integer.IsGreater(Container({0}).NumItems,1)'.format(SPLIT)


def test_started_then_next_up_without_doubles(combo):
    """Kdev Show stands in the first part with its started episode, so not in next up."""
    wait_for_items([('movie', 'The Matrix'), ('episode', combo['kdev'][0]['label']), ('tvshow', 'Breaking Bad')])
    assert 'Kdev%20Show' in label('Window(Home).Property(nc.combo.nextup)')
    assert label('Container({}).NumItems'.format(SPLIT)) == '3'  # two started, one static item
    focus(0)
    assert not true(SPLIT_HERE)
    wait_for(FOLLOWS)
    keep_shot('continue-card')
    focus(2)
    assert true(SPLIT_HERE)  # the first card of next up draws the split
    assert label('Control.GetLabel(9320)')
    keep_shot('nextup-card')
    focus(1)
    assert not true(SPLIT_HERE)
    keep_shot('split')


def test_counter_counts_both_parts(combo):
    """n/m over the whole row: the static item of the split loader is not in the row."""
    wait_for('Integer.IsEqual(Container({}).NumItems,3)'.format(ROW), timeout=20)
    focus(2)
    assert label('Container({}).CurrentItem'.format(ROW)) == '3'
    assert true('Control.IsVisible(9215)')  # shown, so it takes its number


def test_spotlight_follows_both_parts(combo):
    wait_for('Integer.IsEqual(Container({}).NumItems,3)'.format(ROW), timeout=20)
    for position, dbtype in ((1, 'episode'), (2, 'tvshow')):
        focus(position)
        assert label('ListItem.DBType') == dbtype
        title = label('ListItem.Title')
        wait_for('String.Contains(Control.GetLabel(9320),{})'.format(title))
        assert true(FOLLOWS)


def test_ratings_point_at_the_combo_row(combo):
    builtin('Skin.SetBool(nc.ratings.show.tmdb)')
    try:
        wait_for('Integer.IsEqual(Container({}).NumItems,3)'.format(ROW), timeout=20)
        focus(0)
        assert label('ListItem.Title') == 'The Matrix'
        # TMDb Helper looks at the row once the cursor stood still (unless the session kept them)
        wait_for('String.IsEqual(Window(Home).Property(nc.kept.follow.TMDb_Rating),8.2) + Control.IsVisible(9324)', timeout=20)
    finally:
        builtin('Skin.Reset(nc.ratings.show.tmdb)')


def test_next_up_follows_the_library(combo):
    """Kdev Show's episode watched to the end: the first part loses it, next up gains the show
    (the service makes its path anew after the library change)."""
    wait_for_items([('movie', 'The Matrix'), ('episode', combo['kdev'][0]['label']), ('tvshow', 'Breaking Bad')])
    episode_state(combo['kdev'][0]['episodeid'], playcount=1)
    end = time.time() + 20
    while time.time() < end and [t for t, _ in items()] != ['movie', 'tvshow', 'tvshow']:
        time.sleep(0.5)
    found = items()
    assert found[0] == ('movie', 'The Matrix')
    assert sorted(found[1:]) == [('tvshow', 'Breaking Bad'), ('tvshow', 'Kdev Show')]
    assert 'Kdev%20Show' not in label('Window(Home).Property(nc.combo.nextup)')
    assert label('Container({}).NumItems'.format(SPLIT)) == '2'
    focus(1)
    assert true(SPLIT_HERE)


@pytest.fixture
def combo_first_no_spotlight(library):
    builtin('Skin.SetString(nc.home.slot1,combo)')
    builtin('Skin.SetString(SpotlightSource,off)')
    builtin('ReloadSkin()')
    time.sleep(3)
    wait_for('Window.IsActive(home)', timeout=20)
    try:
        yield
    finally:
        builtin('Skin.Reset(nc.home.slot1)')
        builtin('Skin.Reset(SpotlightSource)')
        builtin('ReloadSkin()')
        time.sleep(3)
        wait_for('Window.IsActive(home)', timeout=20)


def test_page_without_spotlight_previews_the_combo_row(combo_first_no_spotlight):
    builtin('SetFocus(9101)')
    wait_for('Control.HasFocus(9101)')
    wait_for('Integer.IsGreater(Container(9201).NumItems,2)', timeout=20)
    wait_for('Control.IsVisible(9361) + Integer.IsEqual(Container(9201).Position,0)')
    rpc('Input.Down')
    wait_for('Control.HasFocus(9201)')
    action('right', 'right')
    wait_for('Integer.IsEqual(Container(9201).CurrentItem,3)')
    assert label('ListItem.DBType') == 'tvshow'
    rpc('Input.Up')
    wait_for('Control.HasFocus(9101) + Control.IsVisible(9361)')
    assert label('Container(9201).ListItem.DBType') == 'tvshow'  # the title the cursor left
