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
