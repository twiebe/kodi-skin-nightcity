"""The genre filter of the music library, end to end, on the seeded library: 7 albums in Rock (2),
Ambient (1), Synthwave (2) and Jazz (2). The filter is a smart playlist rule in the path Kodi shows,
so the window's history keeps it."""
import pytest

from conftest import action, builtin, cond, info, screenshot, wait_for

pytestmark = pytest.mark.e2e

FILTER = 9061
GENRES = ['Ambient', 'Jazz', 'Rock', 'Synthwave']  # as the dialog lists them


def _holds(condition):
    return cond(condition)[condition]


@pytest.fixture
def music(home):
    if not _holds('Library.HasContent(music)'):
        pytest.skip('no music library in this Kodi')
    builtin('ClearProperty(nc.musicfilter.path,home)')
    builtin('ClearProperty(nc.musicfilter.label,home)')
    yield
    builtin('Dialog.Close(all,true)')
    if _holds('Window.IsActive(music)'):
        builtin('Container.Update(musicdb://albums/,replace)')  # the window keeps its last folder
        wait_for('String.IsEqual(Container.FolderPath,musicdb://albums/)', timeout=20)
    builtin('ActivateWindow(home)')
    builtin('ClearProperty(nc.musicfilter.path,home)')
    builtin('ClearProperty(nc.musicfilter.label,home)')


def _open(path):
    """The music window on PATH. Kodi may keep the folder it showed last instead (a folder below the
    path asked for, or genres): it goes there anew."""
    builtin('ActivateWindow(Music,{},return)'.format(path))
    wait_for('Window.IsActive(music) + !Container.IsUpdating', timeout=20)
    builtin('Container.Update({},replace)'.format(path))
    wait_for('String.IsEqual(Container.FolderPath,{}) + !Container.IsUpdating'.format(path), timeout=20)


def _count_is(count):
    wait_for('Integer.IsEqual(Container.NumItems,{}) + !Container.IsUpdating'.format(count), timeout=20)


def _header():
    return info('Control.GetLabel(9026)')['Control.GetLabel(9026)']


def _filter(*genres):
    """Ticks GENRES in the filter's dialog, Left confirms."""
    builtin('SetFocus({})'.format(FILTER))
    wait_for('Control.HasFocus({})'.format(FILTER))
    action('select')
    wait_for('Window.IsActive(selectdialog) + Control.IsVisible(5) + Integer.IsEqual(Container(3).NumItems,{})'.format(len(GENRES)), timeout=10)
    wait_for('Control.HasFocus(3) + !Control.IsVisible(7)')  # one OK, as the library's filter
    for genre in genres:
        index = GENRES.index(genre)
        builtin('SetFocus(3,{},absolute)'.format(index))
        wait_for('Integer.IsEqual(Container(3).CurrentItem,{})'.format(index + 1))
        action('select')
    action('left', delay=1)
    wait_for('!Window.IsActive(selectdialog)')


@pytest.mark.parametrize('node, count, rock_and_jazz', [('albums', 7, 4), ('artists', 4, 2), ('songs', 30, 17)])
def test_the_genre_filter_narrows_albums_artists_and_songs(music, node, count, rock_and_jazz):
    _open('musicdb://{}/'.format(node))
    _count_is(count)
    _filter('Rock', 'Jazz')
    wait_for('String.StartsWith(Container.FolderPath,musicdb://{}/?xsp=)'.format(node), timeout=10)
    _count_is(rock_and_jazz)
    assert 'Jazz, Rock' in _header() or 'JAZZ, ROCK' in _header(), _header()
    label = info('Control.GetLabel({})'.format(FILTER))['Control.GetLabel({})'.format(FILTER)]
    assert 'Jazz, Rock' in label, label
    if node == 'albums':
        screenshot('music-filter-albums')
    # nothing ticked is all again
    _filter('Rock', 'Jazz')
    wait_for('String.IsEqual(Container.FolderPath,musicdb://{}/)'.format(node), timeout=10)
    _count_is(count)
    assert 'Rock' not in _header()


def test_the_filter_is_on_the_lists_of_all_only(music):
    _open('musicdb://albums/')
    assert _holds('Control.IsVisible({})'.format(FILTER))
    builtin('Container.Update(musicdb://albums/1/)')  # an album: Kodi shows it as musicdb://albums/1/-2/?albumid=1
    wait_for('String.StartsWith(Container.FolderPath,musicdb://albums/1/) + !Container.IsUpdating', timeout=20)
    assert not _holds('Control.IsVisible({})'.format(FILTER))
    _open('musicdb://genres/')
    assert not _holds('Control.IsVisible({})'.format(FILTER))


def test_back_on_the_dialog_keeps_the_list(music):
    _open('musicdb://albums/')
    builtin('SetFocus({})'.format(FILTER))
    wait_for('Control.HasFocus({})'.format(FILTER))
    action('select')
    wait_for('Window.IsActive(selectdialog) + Control.IsVisible(5)', timeout=10)
    action('select')  # Ambient
    action('back', delay=1)
    wait_for('!Window.IsActive(selectdialog)')
    assert _holds('String.IsEqual(Container.FolderPath,musicdb://albums/)')
    _count_is(7)


def test_a_filter_left_behind_does_not_name_the_list(music):
    """The header names the genres only on the path they made."""
    _open('musicdb://albums/')
    _filter('Ambient')
    _count_is(1)
    builtin('ActivateWindow(home)')
    wait_for('Window.IsActive(home)')
    _open('musicdb://albums/')
    _count_is(7)
    assert 'Ambient' not in _header() and 'AMBIENT' not in _header(), _header()
    label = info('Control.GetLabel({})'.format(FILTER))['Control.GetLabel({})'.format(FILTER)]
    assert 'Ambient' not in label, label
