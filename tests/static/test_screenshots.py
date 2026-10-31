"""Screenshots (tools/screenshots.py): the ones addon.xml lists and README.md shows exist, and they
stay small, since they ship in the zip."""
import re

from PIL import Image

from conftest import ROOT, parse

SHOTS = ROOT / 'resources' / 'screenshots'


def addon_screenshots():
    return [s.text for s in parse(ROOT / 'addon.xml').iter('screenshot')]


def readme_images():
    return re.findall(r'!\[[^\]]*\]\(([^)\s]+)\)', (ROOT / 'README.md').read_text(encoding='utf-8'))


def test_addon_xml_lists_every_screenshot_once():
    assert addon_screenshots() == ['resources/screenshots/' + p.name for p in sorted(SHOTS.glob('*.jpg'))]
    assert len(addon_screenshots()) == 8


def test_addon_xml_screenshots_exist():
    for path in addon_screenshots():
        assert (ROOT / path).is_file(), path


def test_readme_shows_some_of_them():
    images = readme_images()
    assert 3 <= len(images) <= 4
    for path in images:
        assert not path.startswith(('/', 'http')), path  # relative, so GitHub renders them
        assert (ROOT / path).is_file(), path
        assert path in addon_screenshots(), path


def test_screenshots_are_small_720p_jpegs():
    for path in SHOTS.iterdir():
        with Image.open(path) as image:
            assert (image.format, image.size) == ('JPEG', (1280, 720)), path.name
    assert sum(p.stat().st_size for p in SHOTS.iterdir()) < 1024 * 1024


def test_make_target_passes_the_keys_by_name_only():
    """`make screenshots` hands the API keys to the container from the environment, never as a
    value on the command line or in the image."""
    makefile = (ROOT / 'Makefile').read_text()
    assert '-e MDBLIST_API_KEY -e OMDB_API_KEY' in makefile
    assert not re.search(r'(MDBLIST|OMDB)_API_KEY\s*[:?]?=', makefile)
    assert 'API_KEY' not in (ROOT / 'tools' / 'screenshots.Dockerfile').read_text()
