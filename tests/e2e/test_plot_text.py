"""The plot of an info page and its button, end to end.

The text takes no focus. A button in the row opens it whole in Kodi's text viewer, Back closes the
viewer onto the button, and Up from the row goes one level up or one page back in a TMDb chain at
once, whether the text is long, short or missing.

Needs TMDb Helper, internet access for TMDb and The Matrix in the library (its plot is one short
line, its cast has Keanu Reeves with a long biography and films without a plot); without them
the tests are skipped.

Control.* booleans over JSON-RPC look at the window below a dialog, so these tests read
System.CurrentControlId, which finds the topmost dialog.
"""
import time

import pytest

from test_tmdb_chain import _click_opens  # noqa: E402

from conftest import action, builtin, cond, info, rpc, screenshot, wait_for

pytestmark = pytest.mark.e2e

RUNNING = '!String.IsEmpty(Window(Home).Property(TMDbHelper.Instance))'
IDLE = 'String.IsEmpty(Window(Home).Property(TMDbHelper.Instance))'
BUTTON = 9063


def _label(name):
    return info(name)[name]


def _focus_is(cid, timeout=10):
    try:
        wait_for('Integer.IsEqual(System.CurrentControlId,{})'.format(cid), timeout=timeout)
    except AssertionError:
        # where the focus is instead: a full run lost this detail
        raise AssertionError('focus not on {}: {}'.format(cid, info(
            'System.CurrentWindow', 'System.CurrentControlId', 'ListItem.Label',
            'Window(Home).Property(TMDbHelper.Position)')))


@pytest.fixture
def matrix(home):
    addons = rpc('Addons.GetAddons', {'type': 'xbmc.python.pluginsource', 'enabled': True})['addons']
    if 'plugin.video.themoviedb.helper' not in [a['addonid'] for a in addons]:
        pytest.skip('TMDb Helper not installed')
    movies = rpc('VideoLibrary.GetMovies', {'filter': {'field': 'title', 'operator': 'is', 'value': 'The Matrix'}})
    if not movies.get('movies'):
        pytest.skip('The Matrix not in the library')
    yield movies['movies'][0]['movieid']
    if cond('Window.IsActive(textviewer)')['Window.IsActive(textviewer)']:
        action('back', delay=1)
    if cond(RUNNING)[RUNNING]:
        builtin('SetProperty(TMDbHelper.Command,exit,home)')
        wait_for(IDLE, timeout=20)
    builtin('Dialog.Close(all,true)')


def _matrix_page(movieid):
    builtin('NotifyAll(nightcity,info:movie:{})'.format(movieid))
    wait_for('Window.IsActive(movieinformation)', timeout=20)
    wait_for('Integer.IsGreater(Container(5500).NumItems,0) + !Container(5500).IsUpdating', timeout=45)
    _focus_is(9001)


def _person_page(movieid):
    """The Matrix, then the page of the first of its cast; skipped when TMDb has no biography
    surely longer than the box (four lines of about 90 characters)."""
    _matrix_page(movieid)
    builtin('SetFocus(5500,0,absolute)')
    action('select')
    wait_for('String.IsEqual(Window(Home).Property(TMDbHelper.Position),2)', timeout=30)
    wait_for('Window.IsActive(movieinformation) + String.IsEqual(ListItem.Property(tmdb_type),person)', timeout=20)
    # TMDb Helper polls for the page every half second; Back before it saw the page stalls it
    time.sleep(1.5)
    _focus_is(9004)
    if len(_label('ListItem.Plot')) < 600:
        pytest.skip('biography too short to overflow')
    return _label('ListItem.Label')


def _to_button():
    """Right along the row, the way the remote gets there."""
    for _ in range(6):
        action('right', delay=0.4)
        if _label('System.CurrentControlId') == str(BUTTON):
            return
    _focus_is(BUTTON, timeout=1)


def test_a_long_biography_opens_in_the_viewer(matrix):
    person = _person_page(matrix)
    _to_button()
    screenshot('plot-person-button')
    action('select')
    wait_for('Window.IsActive(textviewer)', timeout=10)
    screenshot('plot-viewer')
    # Up and Down page through a text longer than the viewer (its scrollbar 60), the viewer stays
    action('down', delay=0.4)
    assert cond('Window.IsActive(textviewer)')['Window.IsActive(textviewer)']
    action('back')
    wait_for('!Window.IsActive(textviewer)', timeout=10)
    # back on the button, on the same person page
    _focus_is(BUTTON)
    assert _label('ListItem.Label') == person
    assert _label('Window(Home).Property(TMDbHelper.Position)') == '2'


def test_up_from_the_buttons_steps_back_in_the_chain(matrix):
    _person_page(matrix)
    action('up', delay=1)
    wait_for('String.IsEqual(Window(Home).Property(TMDbHelper.Position),1)', timeout=30)
    wait_for('Window.IsActive(movieinformation) + String.IsEqual(ListItem.DBID,{})'.format(matrix), timeout=20)


def test_up_from_the_text_button_leaves_too(matrix):
    _person_page(matrix)
    _to_button()
    action('up', delay=1)
    wait_for('String.IsEqual(Window(Home).Property(TMDbHelper.Position),1)', timeout=30)


def test_a_short_plot_has_the_button_and_up_leaves(matrix):
    _matrix_page(matrix)
    assert len(_label('ListItem.Plot')) < 80  # one line
    screenshot('plot-movie-short')
    _to_button()
    screenshot('plot-movie-short-button')
    # OK still shows it whole
    action('select')
    wait_for('Window.IsActive(textviewer)', timeout=10)
    action('back')
    wait_for('!Window.IsActive(textviewer)', timeout=10)
    _focus_is(BUTTON)
    action('up', delay=1)
    wait_for('!Window.IsActive(movieinformation)', timeout=10)
    assert cond('Window.IsActive(home)')['Window.IsActive(home)']


def test_the_next_page_opens_on_play_after_leaving_by_the_button(matrix):
    """The row keeps its last focused button over closing the page unless told otherwise."""
    _matrix_page(matrix)
    _to_button()
    action('up', delay=1)
    wait_for('!Window.IsActive(movieinformation)', timeout=10)
    _matrix_page(matrix)  # asserts the focus on play


def test_no_plot_has_no_button(matrix):
    """A TMDb title without a plot: nothing to open, and Up leaves at once."""
    _person_page(matrix)
    builtin('SetFocus(5510)')
    wait_for('!Container(5510).IsUpdating + Integer.IsGreater(Container(5510).NumItems,0)', timeout=30)
    count = int(_label('Container(5510).NumItems'))
    labels = info(*['Container(5510).ListItemAbsolute({}).Plot'.format(i) for i in range(count)])
    empty = [i for i in range(count) if not labels['Container(5510).ListItemAbsolute({}).Plot'.format(i)]]
    if not empty:
        pytest.skip('every film of the person has a plot')
    builtin('SetFocus(5510,{},absolute)'.format(empty[0]))
    _click_opens(5510, 3)
    wait_for('String.IsEqual(Window(Home).Property(TMDbHelper.Position),3)', timeout=30)
    wait_for('Window.IsActive(movieinformation) + !String.IsEqual(ListItem.Property(tmdb_type),person)', timeout=20)
    time.sleep(1.5)
    assert _label('ListItem.Plot') == ''
    assert not cond('Control.IsVisible({})'.format(BUTTON))['Control.IsVisible({})'.format(BUTTON)]
    screenshot('plot-movie-empty')
    action('up', delay=1)
    wait_for('String.IsEqual(Window(Home).Property(TMDbHelper.Position),2)', timeout=30)


VIEWER = 'Window.IsActive(textviewer)'
VIEWER_PAGE = 'Container(5).CurrentPage'


@pytest.fixture
def long_plot(matrix):
    """The Matrix with a plot of several pages of the viewer: no TMDb biography is that long."""
    plot = rpc('VideoLibrary.GetMovieDetails', {'movieid': matrix, 'properties': ['plot']})['moviedetails']['plot']
    text = ' '.join('Paragraph {}: {}'.format(i, 'the long text of the viewer goes on. ' * 6) for i in range(40))
    rpc('VideoLibrary.SetMovieDetails', {'movieid': matrix, 'plot': text})
    yield matrix
    rpc('VideoLibrary.SetMovieDetails', {'movieid': matrix, 'plot': plot})


def _open_viewer():
    _to_button()
    action('select')
    wait_for(VIEWER, timeout=10)
    time.sleep(0.5)


def _closed_onto_the_button():
    wait_for('!' + VIEWER, timeout=10)
    _focus_is(BUTTON)


def test_the_viewer_pages_and_up_on_the_first_page_closes_it(long_plot):
    """Down pages down and never closes, Up pages back up and on the first page closes."""
    _matrix_page(long_plot)
    _open_viewer()
    pages = int(_label('Container(5).NumPages'))
    assert pages >= 3
    assert _label(VIEWER_PAGE) == '1'
    action('down', delay=0.6)
    wait_for('String.IsEqual({},2)'.format(VIEWER_PAGE), timeout=5)
    # Down at the end does nothing
    for _ in range(pages):
        action('down', delay=0.4)
    assert cond(VIEWER)[VIEWER]
    assert _label(VIEWER_PAGE) == str(pages)
    screenshot('plot-viewer-last-page')
    # Up pages back (the last page ends with the text, so it may lie less than a page further)
    for _ in range(pages):
        if not cond('Container(5).HasPrevious')['Container(5).HasPrevious']:
            break
        before = _label(VIEWER_PAGE)
        action('up', delay=0.6)
        wait_for('Integer.IsLess({},{})'.format(VIEWER_PAGE, before), timeout=5)
        assert cond(VIEWER)[VIEWER]
    assert _label(VIEWER_PAGE) == '1'
    action('up')
    _closed_onto_the_button()
    assert cond('Window.IsActive(movieinformation)')['Window.IsActive(movieinformation)']


@pytest.mark.parametrize('key', ['select', 'left', 'right'])
def test_ok_left_and_right_close_the_viewer(long_plot, key):
    _matrix_page(long_plot)
    _open_viewer()
    action('down', delay=0.6)
    wait_for('String.IsEqual({},2)'.format(VIEWER_PAGE), timeout=5)  # also from a later page
    action(key)
    _closed_onto_the_button()


def test_up_closes_a_biography_of_one_page_at_once(matrix):
    person = _person_page(matrix)
    _open_viewer()
    assert _label('Container(5).NumPages') == '1'
    action('up')
    _closed_onto_the_button()
    assert _label('ListItem.Label') == person
    assert _label('Window(Home).Property(TMDbHelper.Position)') == '2'


def test_up_closes_a_short_text_at_once(matrix):
    _matrix_page(matrix)
    _open_viewer()
    assert _label('Container(5).NumPages') == '1'
    action('up')
    _closed_onto_the_button()
    assert cond('Window.IsActive(movieinformation)')['Window.IsActive(movieinformation)']
