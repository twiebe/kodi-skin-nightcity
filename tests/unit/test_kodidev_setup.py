"""tools/kodidev_setup.py: the titles the TMDb tests open, made from a clip of kodi-dev's seed."""
import pathlib
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'tools'))
import kodidev_setup  # noqa: E402


def _media(tmp_path):
    clip = tmp_path / 'movies' / 'Kdev Alpha (2001)' / 'Kdev Alpha (2001).mkv'
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b'mkv')
    return tmp_path


def _ids(nfo):
    return {u.get('type'): u.text for u in ET.parse(nfo).getroot().iter('uniqueid')}


def test_the_matrix_with_its_tmdb_and_imdb_ids(tmp_path):
    media = _media(tmp_path)
    kodidev_setup.add_tmdb_titles(media)
    folder = media / 'movies' / 'The Matrix (1999)'
    assert (folder / 'The Matrix (1999).mkv').read_bytes() == b'mkv'
    assert _ids(folder / 'The Matrix (1999).nfo') == {'imdb': 'tt0133093', 'tmdb': '603'}


def test_breaking_bad_with_three_episodes(tmp_path):
    media = _media(tmp_path)
    kodidev_setup.add_tmdb_titles(media)
    show = media / 'shows' / 'Breaking Bad'
    assert _ids(show / 'tvshow.nfo') == {'tmdb': '1396', 'imdb': 'tt0903747', 'tvdb': '81189'}
    for n in (1, 2, 3):
        episode = show / 'Season 01' / 'Breaking Bad S01E0{}'.format(n)
        assert episode.with_suffix('.mkv').read_bytes() == b'mkv'
        root = ET.parse(episode.with_suffix('.nfo')).getroot()
        assert (root.findtext('season'), root.findtext('episode')) == ('1', str(n))


def test_running_again_changes_nothing(tmp_path):
    media = _media(tmp_path)
    kodidev_setup.add_tmdb_titles(media)
    before = {p: p.stat().st_mtime_ns for p in media.rglob('*')}
    assert kodidev_setup.add_tmdb_titles(media) is False
    assert {p: p.stat().st_mtime_ns for p in media.rglob('*')} == before
