"""tools/screenshots.py: the showcase library it writes into an instance and its list of shots."""
import os
import pathlib
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'tools'))
import screenshots  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _media(tmp_path):
    """An instance's media folder: hard links of the pool template's files, the clips made."""
    template = tmp_path / 'template' / 'The Matrix (1999).nfo'
    template.parent.mkdir()
    template.write_text('<movie><title>The Matrix</title></movie>')
    media = tmp_path / 'media'
    (media / 'movies' / 'The Matrix (1999)').mkdir(parents=True)
    os.link(template, media / 'movies' / 'The Matrix (1999)' / 'The Matrix (1999).nfo')
    (media / 'showcase').mkdir()
    for kind in screenshots.CLIPS:
        (media / 'showcase' / (kind + '.mkv')).write_bytes(kind.encode())
    return media, template


def test_showcase_titles_with_their_tmdb_ids(tmp_path):
    media, _ = _media(tmp_path)
    screenshots.write_media(media)
    folder = media / 'movies' / 'Dune Part Two (2024)'
    assert (folder / 'Dune Part Two (2024).mkv').read_bytes() == b'movie'
    nfo = ET.parse(folder / 'Dune Part Two (2024).nfo').getroot()
    assert (nfo.findtext('title'), nfo.findtext('uniqueid')) == ('Dune: Part Two', '693134')
    assert len(list((media / 'movies').iterdir())) == len(screenshots.MOVIES)
    show = media / 'shows' / 'Cyberpunk Edgerunners'
    assert ET.parse(show / 'tvshow.nfo').getroot().findtext('uniqueid') == '105248'
    assert sorted(p.name for p in (show / 'Season 01').iterdir())[0] == 'Cyberpunk Edgerunners S01E01.mkv'
    assert len(list((show / 'Season 01').iterdir())) == screenshots.EPISODES


def test_the_pool_template_stays_as_it_was(tmp_path):
    """The instance's media are hard links of the template's: replacing a title must unlink."""
    media, template = _media(tmp_path)
    screenshots.write_media(media)
    assert template.read_text() == '<movie><title>The Matrix</title></movie>'
    assert 'tmdb' in (media / 'movies' / 'The Matrix (1999)' / 'The Matrix (1999).nfo').read_text()


def test_every_shot_is_in_addon_xml_in_order():
    listed = [s.text for s in ET.parse(ROOT / 'addon.xml').getroot().iter('screenshot')]
    assert listed == ['resources/screenshots/{}.jpg'.format(file) for file, _ in screenshots.SHOTS.values()]


def test_a_library_that_does_not_sync_says_what_kodi_has():
    movies = [{'label': 'Dune: Part Two', 'art': {'poster': 'p', 'fanart': 'f'}},
              {'label': 'Blade Runner 2049', 'art': {'poster': 'p'}}]
    shows = [{'label': 'Arcane', 'art': {}}]
    gaps = screenshots.library_gaps(movies, shows)
    assert gaps.startswith('Kodi has 2 of {} films and 1 of {} shows'.format(len(screenshots.MOVIES), len(screenshots.SHOWS)))
    assert 'Blade Runner 2049 (fanart)' in gaps and 'Arcane (poster, fanart)' in gaps
    assert 'Dune' not in gaps
    assert screenshots.library_gaps(movies[:1] * len(screenshots.MOVIES),
                                    [movies[0]] * len(screenshots.SHOWS)) == ''


def test_a_timeout_names_the_state_it_saw_last():
    import pytest
    with pytest.raises(RuntimeError, match='the Kodi library: Kodi has 0 of'):
        screenshots.wait_until(lambda: False, 0, 'the Kodi library', state=lambda: 'Kodi has 0 of 16 films')


def test_a_big_library_names_five_and_counts_the_rest():
    movies = [{'label': 'Bulk {:04d}'.format(n), 'art': {}} for n in range(1000)]
    gaps = screenshots.library_gaps(movies, [])
    assert 'Bulk 0004 (poster, fanart) and 995 more' in gaps and 'Bulk 0005' not in gaps


def test_without_skin_the_screenshots_are_nightcitys():
    args = screenshots.parse_args([])
    assert args.skin == 'nightcity'
    assert pathlib.Path(args.out) == screenshots.ROOT / 'resources' / 'screenshots'


def test_the_screenshots_of_confuse_go_to_its_overlay():
    args = screenshots.parse_args(['--skin', 'confuse'])
    assert pathlib.Path(args.out) == screenshots.ROOT / 'skins' / 'confuse' / 'resources' / 'screenshots'


def test_out_wins_over_the_folder_of_the_skin():
    assert screenshots.parse_args(['--skin', 'confuse', '--out', '/x']).out == '/x'


def test_the_mount_of_each_skin():
    root = screenshots.ROOT
    assert screenshots.skin_mount('nightcity') == '{}:/home/kodi/.kodi/addons/skin.nightcity'.format(root)
    assert screenshots.skin_mount('confuse') == '{}:/home/kodi/.kodi/addons/skin.confuse'.format(root / '_build' / 'confuse')


def test_the_instance_gets_the_skin_in_its_guisettings(tmp_path):
    settings = tmp_path / 'guisettings.xml'
    settings.write_text('<settings><setting id="lookandfeel.skin">skin.nightcity</setting></settings>')
    screenshots.select_skin(settings, 'confuse')
    assert '>skin.confuse</setting>' in settings.read_text()


def test_screenshots_select_the_skin_like_the_setup():
    import kodidev_setup
    assert screenshots.select_skin is kodidev_setup.select_skin


def test_the_clip_is_the_same_on_every_run(monkeypatch, tmp_path):
    """Its gradient shows behind the player: tools/compare_shots.py compares fresh instances."""
    calls = []
    monkeypatch.setattr(screenshots.subprocess, 'run', lambda args, **kw: calls.append(args))
    screenshots.make_clip(tmp_path / 'clip.mkv', 60, 2)
    source = next(a for a in calls[0] if a.startswith('gradients='))
    assert ':seed=' in source


class _Recording:
    """Stands in for Kodi in prepare(): records calls, answers just enough for the movies and episodes."""

    def __init__(self, tmp_path):
        self.data, self.calls = tmp_path, []
        (tmp_path / 'kodi' / 'addons' / screenshots.WEATHER).mkdir(parents=True)

    def rpc(self, method, params=None):
        self.calls.append((method, params))
        if method == 'VideoLibrary.GetMovies':
            titles = ('Blade Runner 2049', 'Ghost in the Shell', 'Arrival')
            return {'movies': [{'title': t, 'movieid': n, 'runtime': 100} for n, t in enumerate(titles)]}
        if method == 'VideoLibrary.GetEpisodes':
            return {'episodes': []}
        if method == 'Addons.GetAddons':
            return {'addons': [{'addonid': screenshots.WEATHER}]}
        return {}

    def builtin(self, command):
        self.calls.append(('builtin', command))

    def wait(self, *args, **kwargs):
        pass


def _prepared(monkeypatch, tmp_path):
    kodi = _Recording(tmp_path)
    monkeypatch.setattr(screenshots, 'home', lambda k, page='home': k.calls.append(('home', page)))
    monkeypatch.setattr(screenshots, 'settle', lambda k, seconds=3: k.calls.append(('settle', seconds)))
    monkeypatch.setattr(screenshots.time, 'sleep', lambda s: None)
    screenshots.prepare(kodi)
    return kodi.calls


def test_continue_watching_keeps_its_order_on_a_second_run(monkeypatch, tmp_path):
    """The player shot plays Blade Runner: without its own date it moves to the front of the row and
    a second run on the instance differs from the first."""
    dates = {params['movieid']: params['lastplayed'] for method, params in _prepared(monkeypatch, tmp_path)
             if method == 'VideoLibrary.SetMovieDetails'}
    assert len(dates) == 3
    assert dates[1] > dates[0] > dates[2], 'Ghost in the Shell, Blade Runner 2049, Arrival'


def test_album_art_is_in_the_texture_cache_before_the_shots(monkeypatch, tmp_path):
    """Kodi draws new art from its source and later from a re-encoded copy in its cache: a first
    run would differ from a second. The reload makes the shots load the copy."""
    calls = _prepared(monkeypatch, tmp_path)
    music = calls.index(('home', 'music'))
    assert calls[music + 1][0] == 'settle'
    assert calls.index(('builtin', 'ReloadSkin()')) > music
