"""All movies and all shows as posters or as a list, the details of a row, the sort by runtime and
the filter by genre, format and studio, end to end. The test library has three movies with one
640x360 AAC mono stream each; the fixture gives two of them the streams of a 4K Dolby Vision TrueHD
7.1 and a 1080p HDR10 DD+ 5.1 film, each a studio, a genre and a runtime of its own, and takes it all
back."""
import importlib.util
import pathlib
import re
import sqlite3
import time

import pytest

from conftest import _data, action, builtin, cond, info, rpc, screenshot, wait_for

pytestmark = pytest.mark.e2e

GRID, SORT, VIEW, FILTER, DETAILS = 5000, 5101, 5103, 5104, 5105
CURRENT = 'Container({}).CurrentItem'.format(GRID)
ALPHA, BETA, MATRIX = 'Kdev Alpha', 'Kdev Beta', 'The Matrix'
STREAMS = {ALPHA: (3840, 2160, 'dolbyvision', 'truehd', 8), BETA: (1920, 1080, 'hdr10', 'eac3', 6)}
STUDIOS = {ALPHA: ['Kdev Pictures'], BETA: ['Kdev Pictures', 'Other Films'], MATRIX: ['Warner Bros.']}
GENRES = {ALPHA: ['Action'], BETA: ['Drama', 'Action'], MATRIX: ['Science Fiction']}
RUNTIMES = {ALPHA: 7200, BETA: 5400, MATRIX: 8160}  # s: 2:00, 1:30, 2:16

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


def _length(connection, file_id, seconds):
    connection.execute('UPDATE streamdetails SET iVideoDuration = ? WHERE idFile = ? AND iStreamType = 0', (seconds, file_id))


def _clear_filters():
    for library in ('movies', 'tvshows'):
        for suffix in ('', '.path', '.label'):
            builtin('ClearProperty(nc.libfilter.{}{},home)'.format(library, suffix))
        builtin('Skin.Reset(nc.libdetails.{})'.format(library))


@pytest.fixture
def library(home):
    movies = {m['label']: m for m in rpc('VideoLibrary.GetMovies', {'properties': ['file', 'studio', 'streamdetails', 'genre', 'runtime']})['movies']}
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
        # the length of the stream too: Kodi shows it before the runtime (VideoInfoTag GetDuration)
        lengths = {}
        for title, seconds in RUNTIMES.items():
            file_id = connection.execute('SELECT idFile FROM movie WHERE idMovie = ?', (movies[title]['movieid'],)).fetchone()[0]
            lengths[file_id] = connection.execute('SELECT iVideoDuration FROM streamdetails WHERE idFile = ? AND iStreamType = 0',
                                                  (file_id,)).fetchone()[0]
            _length(connection, file_id, seconds)
    connection.close()
    for title, studios in STUDIOS.items():
        rpc('VideoLibrary.SetMovieDetails', {'movieid': movies[title]['movieid'], 'studio': studios,
                                             'genre': GENRES[title], 'runtime': RUNTIMES[title]})
    shows = rpc('VideoLibrary.GetTVShows', {'properties': ['studio', 'genre']})['tvshows']
    rpc('VideoLibrary.SetTVShowDetails', {'tvshowid': shows[0]['tvshowid'], 'studio': ['Kdev Network'], 'genre': ['Crime']})
    builtin('Skin.Reset(nc.sort)')
    builtin('Skin.Reset(nc.sortdesc)')
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
        for file_id, seconds in lengths.items():
            _length(connection, file_id, seconds)
    connection.close()
    builtin('Skin.Reset(nc.sort)')
    builtin('Skin.Reset(nc.sortdesc)')
    for title in STUDIOS:
        rpc('VideoLibrary.SetMovieDetails', {'movieid': movies[title]['movieid'], 'studio': movies[title]['studio'],
                                             'genre': movies[title]['genre'], 'runtime': movies[title]['runtime']})
    for show in shows:
        rpc('VideoLibrary.SetTVShowDetails', {'tvshowid': show['tvshowid'], 'studio': show['studio'], 'genre': show['genre']})


def _open(kind='movies', count=3):
    builtin('SetProperty(nc.library,{},home)'.format(kind))
    builtin('ActivateWindow(1110)')
    wait_for('Window.IsActive(1110)')
    _count_is(count)
    # the layouts hold only once the window is up (lib_layout): a key before moves in the empty one
    wait_for('!String.IsEmpty(Window(Home).Property(nc.lib.layout))')
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


def _group(index):
    """The cursor on a group of the filter's list."""
    wait_for('Control.HasFocus(6)')
    builtin('SetFocus(6,{},absolute)'.format(index))
    wait_for('Control.HasFocus(6) + Integer.IsEqual(Container(6).CurrentItem,{})'.format(index + 1))


def test_the_filter_dialog_narrows_the_grid_and_the_header_says_so(library):
    _open()
    builtin('SetFocus({})'.format(FILTER))
    wait_for('Control.HasFocus({})'.format(FILTER))
    action('select')
    _select_dialog()
    _group(1)  # resolution, after the genre
    action('select', delay=1)
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
    # the Clear button left of OK: Down from the list goes to OK, Left to Clear
    builtin('SetFocus({})'.format(FILTER))
    action('select')
    _select_dialog()
    wait_for('Integer.IsEqual(Container(6).NumItems,6) + Control.IsVisible(10)')
    _group(5)
    action('down')
    wait_for('Control.HasFocus(9)')
    action('left')
    wait_for('Control.HasFocus(10)')
    action('select', delay=1)
    wait_for('String.IsEmpty(Window(Home).Property(nc.libfilter.movies.path))')
    _select('Window.IsActive(selectdialog) + Control.IsVisible(6) + !Control.IsVisible(10)')  # the groups again
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
    ({'genre': ['Action']}, [ALPHA, BETA]),
    ({'genre': ['Drama', 'Science Fiction']}, [BETA, MATRIX]),
    ({'genre': ['Action'], 'res': ['1080']}, [BETA]),
])
def test_every_rule_kodi_runs(library, choice, titles):
    """The paths the dialog makes, in the grid itself."""
    builtin('SetProperty(nc.libfilter.movies.path,{},home)'.format(nightcity.lib_filter_path('movies', choice)))
    _open(count=len(titles))
    assert _titles() == titles


def test_shows_filter_by_genre_and_studio(library):
    _open('tvshows', len(library['shows']))
    builtin('SetFocus({})'.format(FILTER))
    wait_for('Control.HasFocus({})'.format(FILTER))
    action('select')
    _select_dialog()
    wait_for('Integer.IsEqual(Container(6).NumItems,2) + !Control.IsVisible(10)')  # genre and studio, nothing chosen yet: no Clear
    _group(1)
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
    _group(1)
    action('select', delay=1)  # resolution
    wait_for('Window.IsActive(selectdialog) + Integer.IsEqual(Container(3).NumItems,4)')
    wait_for('Control.IsVisible(5) + !Control.IsVisible(7) + !Control.IsVisible(9)')  # Kodi's OK only
    action('select')  # 4K
    action('right')
    assert true('Control.HasFocus(3)')  # Right stays in the list
    action('left', delay=1)
    _select_dialog()
    wait_for('Integer.IsEqual(Container(6).NumItems,6) + Control.IsVisible(10)')  # the groups again, the choice taken
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


def test_shows_filter_by_genre(library):
    builtin('SetProperty(nc.libfilter.tvshows.path,{},home)'.format(nightcity.lib_filter_path('tvshows', {'genre': ['Crime']})))
    _open('tvshows', 1)
    assert _titles() == [library['shows'][0]['label']]


def _select(condition='Window.IsActive(selectdialog)'):
    wait_for(condition, timeout=10)


def test_the_genre_group_lists_the_librarys_genres(library):
    _open()
    builtin('SetFocus({})'.format(FILTER))
    wait_for('Control.HasFocus({})'.format(FILTER))
    action('select')
    _select_dialog()
    _group(0)
    action('select', delay=1)
    _select('Window.IsActive(selectdialog) + Control.IsVisible(5) + Integer.IsEqual(Container(3).NumItems,3)')
    labels = info(*['Container(3).ListItemAbsolute({}).Label'.format(i) for i in range(3)])
    assert [labels['Container(3).ListItemAbsolute({}).Label'.format(i)] for i in range(3)] == ['Action', 'Drama', 'Science Fiction']
    action('select')  # Action
    action('left', delay=1)  # confirms, back to the groups
    _select('Window.IsActive(selectdialog) + !Control.IsVisible(5)')
    wait_for('!String.IsEmpty(Window(Home).Property(nc.libfilter.movies.path))')
    action('back', delay=1)
    wait_for('!Window.IsActive(selectdialog)')
    _count_is(2)
    assert _titles() == [ALPHA, BETA]
    assert 'Action' in _header() or 'ACTION' in _header(), _header()


# --- the keys of the select dialogs ---------------------------------------------------------------

def test_right_enters_the_group_of_the_filters_list(library):
    """Right on the list of groups opens the group, as OK; in the group it stays."""
    _open()
    builtin('SetFocus({})'.format(FILTER))
    wait_for('Control.HasFocus({})'.format(FILTER))
    action('select')
    _select_dialog()
    _group(1)  # resolution
    action('right', delay=1)
    _select('Window.IsActive(selectdialog) + Control.IsVisible(5) + Integer.IsEqual(Container(3).NumItems,4)')
    action('right')
    assert true('Control.HasFocus(3) + Control.IsVisible(5)')
    action('back', delay=1)
    _select('Window.IsActive(selectdialog) + !Control.IsVisible(5)')
    action('back', delay=1)
    wait_for('!Window.IsActive(selectdialog)')


def test_up_from_the_button_goes_back_to_the_list(library):
    """The filter's list of groups: Down past its end to its OK, Up back to the list."""
    _open()
    builtin('SetFocus({})'.format(FILTER))
    wait_for('Control.HasFocus({})'.format(FILTER))
    action('select')
    _select_dialog()
    _group(5)  # studio, the last
    action('down')
    wait_for('Control.HasFocus(9)')
    action('up')
    wait_for('Control.HasFocus(6)')
    action('back', delay=1)
    wait_for('!Window.IsActive(selectdialog)')


def test_up_from_the_buttons_of_any_select_dialog(home):
    """A select dialog of Kodi's own (here Skin.SelectBool): Right to its buttons, Up back to the list."""
    builtin('Skin.SelectBool(31502,31119|nc.test.a,31600|nc.test.b)')
    _select_dialog()
    wait_for('Control.HasFocus(3) | Control.HasFocus(6)')
    shown = 6 if true('Control.IsVisible(6)') else 3
    action('right')
    wait_for('ControlGroup(9001).HasFocus()')
    action('up')
    wait_for('Control.HasFocus({})'.format(shown))
    action('back', delay=1)
    wait_for('!Window.IsActive(selectdialog)')
    builtin('Skin.Reset(nc.test.a)')
    builtin('Skin.Reset(nc.test.b)')


# --- the sort by runtime --------------------------------------------------------------------------

def test_movies_sort_by_runtime(library):
    """Kodi's sort time orders the movies by their runtime: 1:30, 2:00, 2:16."""
    builtin('Skin.SetString(nc.sort,rating)')
    _open()
    builtin('SetFocus({})'.format(SORT))
    wait_for('Control.HasFocus({})'.format(SORT))
    action('select', delay=1)
    wait_for('String.IsEqual(Skin.String(nc.sort),time)')
    _count_is(3)
    wait_for('String.IsEqual(Container({}).ListItemAbsolute(0).Label,{})'.format(GRID, BETA))
    assert _titles() == [BETA, ALPHA, MATRIX]
    label = info('Control.GetLabel({})'.format(SORT))['Control.GetLabel({})'.format(SORT)]
    assert 'runtime' in label.lower(), label
    builtin('Skin.SetBool(nc.sortdesc)')
    wait_for('String.IsEqual(Container({}).ListItemAbsolute(0).Label,{})'.format(GRID, MATRIX))
    assert _titles() == [MATRIX, ALPHA, BETA]


def test_shows_take_a_sort_by_runtime_for_the_title(library):
    builtin('Skin.SetString(nc.sort,time)')
    _open('tvshows', len(library['shows']))
    titles = [t for t in (info(*['Container({}).ListItemAbsolute({}).Label'.format(GRID, i) for i in range(2)]).values()) if t]
    assert titles == sorted(titles, key=str.lower)
    label = info('Control.GetLabel({})'.format(SORT))['Control.GetLabel({})'.format(SORT)]
    assert 'runtime' not in label.lower(), label
    builtin('SetFocus({})'.format(SORT))
    wait_for('Control.HasFocus({})'.format(SORT))
    action('select', delay=1)
    wait_for('String.IsEqual(Skin.String(nc.sort),year)')


# --- the details of a row -------------------------------------------------------------------------

def _details_dialog():
    builtin('SetFocus({})'.format(DETAILS))
    wait_for('Control.HasFocus({})'.format(DETAILS))
    action('select')
    _select('Window.IsActive(selectdialog) + Control.IsVisible(5)')
    wait_for('Control.HasFocus(3)')


def _ticked(count):
    names = ['Container(3).ListItemAbsolute({}).IsSelected'.format(i) for i in range(count)]
    found = cond(*names)
    return [i for i in range(count) if found[names[i]]]


def test_the_details_button_is_on_the_list_only(library):
    _open()
    assert not true('Control.IsVisible({})'.format(DETAILS))
    builtin('Skin.SetString(nc.libview.movies,list)')
    wait_for('Control.IsVisible({})'.format(DETAILS))
    label = info('Control.GetLabel({})'.format(DETAILS))['Control.GetLabel({})'.format(DETAILS)].lower()
    assert 'year, runtime' in label, label


def test_the_details_dialog_chooses_what_a_row_shows(library):
    """Year and runtime by default; Left confirms the ticks, Back leaves them as they were."""
    builtin('Skin.SetString(nc.libview.movies,list)')
    _open()
    screenshot('library-details-default')
    _details_dialog()
    wait_for('Integer.IsEqual(Container(3).NumItems,6) + !Control.IsVisible(7)')
    assert _ticked(6) == [0, 1]
    screenshot('library-details-dialog')
    builtin('SetFocus(3,2,absolute)')  # rating
    wait_for('Integer.IsEqual(Container(3).CurrentItem,3)')
    action('select')
    action('left', delay=1)
    wait_for('!Window.IsActive(selectdialog) + String.IsEqual(Skin.String(nc.libdetails.movies),year.runtime.rating)')
    label = info('Control.GetLabel({})'.format(DETAILS))['Control.GetLabel({})'.format(DETAILS)].lower()
    assert 'rating' in label, label
    assert true('String.IsEmpty(Skin.String(nc.libdetails.tvshows))')
    # Back keeps what there was
    _details_dialog()
    assert _ticked(6) == [0, 1, 2]
    action('select')  # year off
    action('back', delay=1)
    wait_for('!Window.IsActive(selectdialog)')
    wait_for('!Window.IsActive(selectdialog) + String.IsEqual(Skin.String(nc.libdetails.movies),year.runtime.rating)')


def test_every_detail_and_none(library):
    builtin('Skin.SetString(nc.libview.movies,list)')
    _open()
    _details_dialog()
    for i in range(2, 6):
        builtin('SetFocus(3,{},absolute)'.format(i))
        wait_for('Integer.IsEqual(Container(3).CurrentItem,{})'.format(i + 1))
        action('select')
    builtin('SetFocus(5)')
    wait_for('Control.HasFocus(5)')
    action('select', delay=1)
    wait_for('!Window.IsActive(selectdialog) + String.IsEqual(Skin.String(nc.libdetails.movies),year.runtime.rating.res.hdr.audio)')
    builtin('SetFocus({},0,absolute)'.format(GRID))
    wait_for('Control.HasFocus({})'.format(GRID))
    time.sleep(0.5)
    screenshot('library-details-all')
    _details_dialog()
    for i in range(6):
        builtin('SetFocus(3,{},absolute)'.format(i))
        wait_for('Integer.IsEqual(Container(3).CurrentItem,{})'.format(i + 1))
        action('select')
    action('left', delay=1)
    wait_for('!Window.IsActive(selectdialog) + String.IsEqual(Skin.String(nc.libdetails.movies),none)')
    label = info('Control.GetLabel({})'.format(DETAILS))['Control.GetLabel({})'.format(DETAILS)].lower()
    assert 'none' in label, label


def test_shows_have_their_own_details(library):
    builtin('Skin.SetString(nc.libview.tvshows,list)')
    _open('tvshows', len(library['shows']))
    label = info('Control.GetLabel({})'.format(DETAILS))['Control.GetLabel({})'.format(DETAILS)].lower()
    assert 'year, episodes' in label, label
    _details_dialog()
    wait_for('Integer.IsEqual(Container(3).NumItems,5)')
    assert _ticked(5) == [0, 3]
    builtin('SetFocus(3,2,absolute)')  # seasons
    wait_for('Integer.IsEqual(Container(3).CurrentItem,3)')
    action('select')
    action('left', delay=1)
    wait_for('!Window.IsActive(selectdialog) + String.IsEqual(Skin.String(nc.libdetails.tvshows),year.seasons.episodes)')
    assert true('String.IsEmpty(Skin.String(nc.libdetails.movies))')
    screenshot('library-details-shows')
