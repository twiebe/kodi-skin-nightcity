"""Chapter row thumbnails: Kodi cuts them from local files and LAN shares only. For Jellyfin
streams the OSD script puts the server's chapter images into nc.chapter.N (Home), N = Kodi's
chapter number; chapters of other streams show as compact cards without an image."""
import sys

from conftest import ROOT, parse

sys.path.insert(0, str(ROOT / 'scripts'))
import nightcity  # noqa: E402

SKIN = ROOT / '1080i'
REMOTE = '!String.IsEmpty(Window(Home).Property(nc.chapters.remote))'
COMPACT = (REMOTE + ' + String.IsEmpty(Window(Home).Property(nc.chapter.1))'
           ' + String.IsEqual(ListItem.Property(ischapter),true)')


def _variable(name):
    for el in parse(SKIN / 'Variables.xml').iter('variable'):
        if el.get('name') == name:
            return [(v.get('condition'), v.text) for v in el.findall('value')]
    raise AssertionError(name)


def _include(name):
    for path in SKIN.glob('Includes*.xml'):
        for el in parse(path).iter('include'):
            if el.get('name') == name:
                return el
    raise AssertionError(name)


def test_streams_take_the_servers_images():
    assert _variable('ChapterThumb') == [(REMOTE, '$VAR[ChapterServerThumb]'),
                                         (None, '$INFO[ListItem.Art(thumb)]')]


def test_every_chapter_the_script_fills_has_its_image():
    """Kodi cannot nest labels (nc.chapter.$INFO[...]): one value per chapter number, as many
    as the script fills."""
    assert _variable('ChapterServerThumb') == [
        ('String.IsEqual(ListItem.Property(chapter),{})'.format(n),
         '$INFO[Window(Home).Property(nc.chapter.{})]'.format(n))
        for n in range(1, nightcity.CHAPTER_THUMBS + 1)]


def test_chapter_card_shows_the_chapter_thumb():
    card = _include('ChapterCard')
    images = [p.get('value') for p in card.iter('param') if p.get('name') == 'image']
    assert images == ['$VAR[ChapterThumb]']


def test_chapters_without_images_are_compact():
    """A stream without server images: a short card with time and name instead of an empty
    image frame. Bookmarks keep their card, Kodi takes their thumbnail from the picture."""
    card = _include('ChapterCard').find('definition')
    groups = card.findall('control')
    assert [g.findtext('visible') for g in groups] == ['!' + '[' + COMPACT + ']', COMPACT]
    compact = groups[1]
    cut = compact.find('include')
    params = {p.get('name'): p.get('value') for p in cut.findall('param')}
    assert cut.get('content') == 'CutCard'
    assert (params['width'], params['height']) == ('320', '112')
    assert 'image' not in params
    labels = [c.findtext('label') for c in compact.iter('control') if c.get('type') == 'label']
    assert labels == ['$INFO[ListItem.Label2]', '$INFO[ListItem.Label]']
