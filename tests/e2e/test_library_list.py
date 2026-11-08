"""All movies and all shows as posters or as a list, and the filter by format and studio, end to
end. The test library has three movies with one 640x360 AAC mono stream each; the fixture gives
two of them the streams of a 4K Dolby Vision TrueHD 7.1 and a 1080p HDR10 DD+ 5.1 film, a studio
each, and takes it all back."""
import importlib.util
import pathlib
import re
import sqlite3
import time

import pytest

from conftest import _data, action, builtin, cond, info, rpc, screenshot, wait_for

pytestmark = pytest.mark.e2e

GRID, SORT, VIEW, FILTER = 5000, 5101, 5103, 5104
CURRENT = 'Container({}).CurrentItem'.format(GRID)
ALPHA, BETA, MATRIX = 'Kdev Alpha', 'Kdev Beta', 'The Matrix'
STREAMS = {ALPHA: (3840, 2160, 'dolbyvision', 'truehd', 8), BETA: (1920, 1080, 'hdr10', 'eac3', 6)}
STUDIOS = {ALPHA: ['Kdev Pictures'], BETA: ['Kdev Pictures', 'Other Films'], MATRIX: ['Warner Bros.']}

_spec = importlib.util.spec_from_file_location(
    'nightcity', pathlib.Path(__file__).resolve().parents[2] / 'scripts' / 'nightcity.py')
nightcity = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nightcity)


def _database():
    return str(sorted((_data() / 'kodi' / 'userdata' / 'Database').glob('MyVideos*.db'))[-1])


def _streams(connection, rows):
    for file_id, (width, height, hdr, codec, channels) in rows.items():
        connection.execute('UPDATE streamdetails SET iVideoWidth = ?, iVideoHeight = ?, strHdrType = ? '
                           'WHERE idFile = ? AND iStreamType = 0', (width, height, hdr, file_id))
        connection.execute('UPDATE streamdetails SET strAudioCodec = ?, iAudioChannels = ? '
                           'WHERE idFile = ? AND iStreamType = 1', (codec, channels, file_id))


def _clear_filters():
    for library in ('movies', 'tvshows'):
        for suffix in ('', '.path', '.label'):
            builtin('ClearProperty(nc.libfilter.{}{},home)'.format(library, suffix))


@pytest.fixture
def library(home):
    movies = {m['label']: m for m in rpc('VideoLibrary.GetMovies', {'properties': ['file', 'studio', 'streamdetails']})['movies']}
    assert set(movies) >= {ALPHA, BETA, MATRIX}
    with sqlite3.connect(_database(), timeout=30) as connection:
        files = {title: connection.execute('SELECT idFile FROM movie WHERE idMovie = ?', (movies[title]['movieid'],)).fetchone()[0]
                 for title in STREAMS}
        before = {}
        for title, file_id in files.items():
            video = movies[title]['streamdetails']['video'][0]
            audio = movies[title]['streamdetails']['audio'][0]
            before[file_id] = (video['width'], video['height'], video['hdrtype'], audio['codec'], audio['channels'])
        _streams(connection, {files[t]: s for t, s in STREAMS.items()})
    connection.close()
    for title, studios in STUDIOS.items():
        rpc('VideoLibrary.SetMovieDetails', {'movieid': movies[title]['movieid'], 'studio': studios})
    shows = rpc('VideoLibrary.GetTVShows', {'properties': ['studio']})['tvshows']
    rpc('VideoLibrary.SetTVShowDetails', {'tvshowid': shows[0]['tvshowid'], 'studio': ['Kdev Network']})
    builtin('Skin.Reset(nc.sort)')
    builtin('Skin.Reset(nc.libview.movies)')
    builtin('Skin.Reset(nc.libview.tvshows)')
    _clear_filters()
    yield {'shows': shows}
    builtin('Dialog.Close(all,true)')
    builtin('ActivateWindow(home)')
    builtin('Skin.Reset(nc.libview.movies)')
    builtin('Skin.Reset(nc.libview.tvshows)')
    _clear_filters()
    with sqlite3.connect(_database(), timeout=30) as connection:
        _streams(connection, before)
    connection.close()
    for title in STUDIOS:
        rpc('VideoLibrary.SetMovieDetails', {'movieid': movies[title]['movieid'], 'studio': movies[title]['studio']})
    for show in shows:
        rpc('VideoLibrary.SetTVShowDetails', {'tvshowid': show['tvshowid'], 'studio': show['studio']})


def _open(kind='movies', count=3):
    builtin('SetProperty(nc.library,{},home)'.format(kind))
    builtin('ActivateWindow(1110)')
    wait_for('Window.IsActive(1110)')
    _count_is(count)
    builtin('SetFocus({},0,absolute)'.format(GRID))
    wait_for('Control.HasFocus({})'.format(GRID))


def _count_is(count):
    wait_for('Integer.IsEqual(Container({0}).NumItems,{1}) + !Container({0}).IsUpdating'.format(GRID, count), timeout=20)


def _titles():
    labels = ['Container({}).ListItemAbsolute({}).Label'.format(GRID, i) for i in range(3)]
    return [t for t in (info(*labels)[label] for label in labels) if t]


def _header():
    return re.sub(r'\[/?[A-Z]+[^\]]*\]', '', info('Control.GetLabel(9026)')['Control.GetLabel(9026)'])


def _toggle_view():
    builtin('SetFocus({})'.format(VIEW))
    wait_for('Control.HasFocus({})'.format(VIEW))
    action('select', delay=0.5)


def test_posters_by_default_down_stays_in_the_row(library):
    _open()
    action('down')
    wait_for('Integer.IsEqual({},1)'.format(CURRENT))
    assert cond('Control.HasFocus({})'.format(GRID))['Control.HasFocus({})'.format(GRID)]


def test_the_view_button_makes_a_list_and_it_is_remembered(library):
    _open()
    _toggle_view()
    wait_for('String.IsEqual(Skin.String(nc.libview.movies),list)')
    assert not cond('String.IsEqual(Skin.String(nc.libview.tvshows),list)')['String.IsEqual(Skin.String(nc.libview.tvshows),list)']
    builtin('SetFocus({},0,absolute)'.format(GRID))
    wait_for('Control.HasFocus({})'.format(GRID))
    action('down')  # one title a row now
    wait_for('Integer.IsEqual({},2)'.format(CURRENT))
    screenshot('library-list-movies')
    builtin('ActivateWindow(home)')
    wait_for('Window.IsActive(home)')
    _open()
    action('down')
    wait_for('Integer.IsEqual({},2)'.format(CURRENT))
    # the shows keep their posters
    builtin('ActivateWindow(home)')
    wait_for('Window.IsActive(home)')
    _open('tvshows', len(library['shows']))
    action('down')
    wait_for('Integer.IsEqual({},1)'.format(CURRENT))
    # and back to posters
    _open()
    _toggle_view()
    wait_for('String.IsEmpty(Skin.String(nc.libview.movies))')


def test_the_list_keeps_the_bar_click_and_counter(library):
    builtin('Skin.SetString(nc.libview.movies,list)')
    _open()
    action('down')
    wait_for('Integer.IsEqual({},2)'.format(CURRENT))
    assert info('Control.GetLabel(9028)')['Control.GetLabel(9028)'] == '2/3'
    action('right')
    wait_for('Control.HasFocus({})'.format(SORT))
    action('left')
    wait_for('Control.HasFocus({}) + Integer.IsEqual({},2)'.format(GRID, CURRENT))


def true(condition):
    return cond(condition)[condition]


def _select_dialog():
    wait_for('Window.IsActive(selectdialog)', timeout=10)


def test_the_filter_dialog_narrows_the_grid_and_the_header_says_so(library):
    _open()
    builtin('SetFocus({})'.format(FILTER))
    wait_for('Control.HasFocus({})'.format(FILTER))
    action('select')
    _select_dialog()
    action('select', delay=1)  # resolution
    wait_for('Window.IsActive(selectdialog) + Integer.IsEqual(Container(3).NumItems,4)')
    action('select')  # 4K
    builtin('SetFocus(5)')  # OK of the multi-select
    wait_for('Control.HasFocus(5)')
    action('select', delay=1)
    _select_dialog()  # the groups again, the choice made
    wait_for('!String.IsEmpty(Window(Home).Property(nc.libfilter.movies.path))')
    action('back', delay=1)
    wait_for('!Window.IsActive(selectdialog)')
    _count_is(1)  # Container(5000) answers for the window on top: only now
    assert _titles() == [ALPHA]
    assert '4K' in _header(), _header()
    assert '4K' in info('Control.GetLabel({})'.format(FILTER))['Control.GetLabel({})'.format(FILTER)]
    screenshot('library-filter')
    # clear filter: the last entry
    builtin('SetFocus({})'.format(FILTER))
    action('select')
    _select_dialog()
    wait_for('Integer.IsEqual(Container(6).NumItems,6)')
    builtin('SetFocus(6,5,absolute)')
    action('select', delay=1)
    wait_for('String.IsEmpty(Window(Home).Property(nc.libfilter.movies.path))')
    action('back', delay=1)
    wait_for('!Window.IsActive(selectdialog)')
    _count_is(3)
    assert '4K' not in _header()


@pytest.mark.parametrize('choice, titles', [
    ({'res': ['2160', '1080']}, [ALPHA, BETA]),
    ({'res': ['480']}, [MATRIX]),
    ({'hdr': ['hdr']}, [ALPHA, BETA]),
    ({'hdr': ['dolbyvision']}, [ALPHA]),
    ({'hdr': ['sdr']}, [MATRIX]),
    ({'hdr': ['sdr', 'hdr10']}, [BETA, MATRIX]),
    ({'audio': ['truehd', 'eac3']}, [ALPHA, BETA]),
    ({'channels': ['6']}, [BETA]),
    ({'res': ['2160', '1080'], 'channels': ['6']}, [BETA]),
    ({'studio': ['Kdev Pictures']}, [ALPHA, BETA]),
    ({'studio': ['Warner Bros.'], 'hdr': ['sdr']}, [MATRIX]),
])
def test_every_rule_kodi_runs(library, choice, titles):
    """The paths the dialog makes, in the grid itself."""
    builtin('SetProperty(nc.libfilter.movies.path,{},home)'.format(nightcity.lib_filter_path('movies', choice)))
    _open(count=len(titles))
    assert _titles() == titles


def test_shows_filter_by_studio_only(library):
    _open('tvshows', len(library['shows']))
    builtin('SetFocus({})'.format(FILTER))
    wait_for('Control.HasFocus({})'.format(FILTER))
    action('select')
    _select_dialog()
    wait_for('Integer.IsEqual(Container(6).NumItems,1)')  # studio, nothing chosen yet: no clear
    action('select', delay=1)
    wait_for('Window.IsActive(selectdialog) + Integer.IsEqual(Container(3).NumItems,1)')
    action('select')
    builtin('SetFocus(5)')
    wait_for('Control.HasFocus(5)')
    action('select', delay=1)
    _select_dialog()
    wait_for('!String.IsEmpty(Window(Home).Property(nc.libfilter.tvshows.path))')
    action('back', delay=1)
    wait_for('!Window.IsActive(selectdialog)')
    _count_is(1)
    assert 'Kdev Network' in _header() or 'KDEV NETWORK' in _header(), _header()


def _focused_row_drawn():
    """The glow of the focused row, right of where three posters end: at 1000, 130 of 1920 x 1080."""
    from PIL import Image
    image = Image.open(screenshot('library-list-reopened')).convert('RGB')
    scale = image.width / 1920
    return max(image.getpixel((int(1000 * scale), int(130 * scale)))) > 150


def test_a_view_chosen_while_closed_draws_every_row_anew(library):
    """A panel keeps its items over closing the window, each with the layout it drew it with, and
    on the way back picks its layout without asking them (GUIBaseContainer::AllocResources): the
    rows drew as posters. Kodi lets them go only when a layout's condition changes on screen."""
    _open()
    builtin('ActivateWindow(home)')
    wait_for('Window.IsActive(home)')
    builtin('Skin.SetString(nc.libview.movies,list)')
    _open()
    time.sleep(1)
    assert _focused_row_drawn()


def test_left_takes_the_filter_dialogs_up_a_level_with_the_choice(library):
    """One OK, no Cancel; Left in a group's multi-select keeps what is ticked and goes back to the
    groups, Left there closes the dialog; Right stays in the list."""
    _open()
    builtin('SetFocus({})'.format(FILTER))
    wait_for('Control.HasFocus({})'.format(FILTER))
    action('select')
    _select_dialog()
    wait_for('Control.IsVisible(9) + !Control.IsVisible(7)')  # the groups: their OK only
    action('select', delay=1)  # resolution
    wait_for('Window.IsActive(selectdialog) + Integer.IsEqual(Container(3).NumItems,4)')
    wait_for('Control.IsVisible(5) + !Control.IsVisible(7) + !Control.IsVisible(9)')  # Kodi's OK only
    action('select')  # 4K
    action('right')
    assert true('Control.HasFocus(3)')  # Right stays in the list
    action('left', delay=1)
    _select_dialog()
    wait_for('Integer.IsEqual(Container(6).NumItems,6)')  # the groups again, the choice taken
    wait_for('!String.IsEmpty(Window(Home).Property(nc.libfilter.movies.path))')
    action('left', delay=1)
    wait_for('!Window.IsActive(selectdialog) + String.IsEmpty(Window(Home).Property(nc.select.ok))')
    _count_is(1)
    assert _titles() == [ALPHA]


def test_the_bar_remembers_its_button(library):
    """In the list (one column) Right goes to the bar at once: to the button it left."""
    builtin('Skin.SetString(nc.libview.movies,list)')
    _open()
    builtin('SetFocus({})'.format(FILTER))
    wait_for('Control.HasFocus({})'.format(FILTER))
    action('left')
    wait_for('Control.HasFocus({})'.format(GRID))
    action('right')
    wait_for('Control.HasFocus({})'.format(FILTER))
