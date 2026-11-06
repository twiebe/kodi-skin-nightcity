"""tools/kodidev_setup.py: the titles the TMDb tests open, made from a clip of kodi-dev's seed."""
import pathlib
import sys
import xml.etree.ElementTree as ET

import pytest

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


def _folders(tmp_path, monkeypatch):
    kodi_dev = tmp_path / 'kodi-dev'
    kodi_dev.mkdir()
    monkeypatch.setattr(kodidev_setup, 'KODI_DEV', kodi_dev)
    settings = kodi_dev / 'guisettings.xml'
    settings.write_text('<settings><setting id="lookandfeel.skin">skin.nightcity</setting></settings>')
    monkeypatch.setattr(kodidev_setup, 'GUISETTINGS', settings)
    return kodi_dev / 'compose.override.yaml', settings


def test_both_skins_are_mounted_once(tmp_path, monkeypatch):
    override, _ = _folders(tmp_path, monkeypatch)
    kodidev_setup.ensure_mounts()
    kodidev_setup.ensure_mounts()
    text = override.read_text()
    root = kodidev_setup.ROOT
    assert text.count('{}:/home/kodi/.kodi/addons/skin.nightcity'.format(root)) == 1
    assert text.count('{}:/home/kodi/.kodi/addons/skin.confuse'.format(root / '_build' / 'confuse')) == 1


def test_a_mount_of_another_addon_stays(tmp_path, monkeypatch):
    override, _ = _folders(tmp_path, monkeypatch)
    override.write_text('services:\n  kodi:\n    volumes:\n      - /a:/home/kodi/.kodi/addons/plugin.a\n')
    kodidev_setup.ensure_mounts()
    assert '/a:/home/kodi/.kodi/addons/plugin.a' in override.read_text()


def test_the_skin_in_guisettings_follows_the_option(tmp_path, monkeypatch):
    _, settings = _folders(tmp_path, monkeypatch)
    kodidev_setup.select_skin(settings, kodidev_setup.parse_args(['--skin', 'confuse']).skin)
    assert '>skin.confuse</setting>' in settings.read_text()
    kodidev_setup.select_skin(settings, kodidev_setup.parse_args([]).skin)
    assert '>skin.nightcity</setting>' in settings.read_text()


def test_a_guisettings_without_the_skin_setting_is_an_error(tmp_path, monkeypatch):
    _, settings = _folders(tmp_path, monkeypatch)
    settings.write_text('<settings></settings>')
    with pytest.raises(SystemExit, match='lookandfeel.skin'):
        kodidev_setup.select_skin(settings, 'confuse')
