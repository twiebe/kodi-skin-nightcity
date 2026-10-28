"""Chapter row thumbnails: for Jellyfin streams the OSD script puts the server's chapter images
into nc.chapter.N (Home), N = Kodi's chapter number. Without them the card shows Kodi's own
thumbnail: Kodi cuts some from http streams too (seen on CoreELEC with Arctic Fuse 3)."""
import sys

from conftest import ROOT, parse

sys.path.insert(0, str(ROOT / 'scripts'))
import nightcity  # noqa: E402

SKIN = ROOT / '1080i'
REMOTE = '!String.IsEmpty(Window(Home).Property(nc.chapters.remote))'
SERVER = REMOTE + ' + !String.IsEmpty(Window(Home).Property(nc.chapter.1))'


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
    assert _variable('ChapterThumb') == [(SERVER, '$VAR[ChapterServerThumb]'),
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


def test_chapters_without_server_images_keep_kodis_card():
    """No compact cards: a stream without server images keeps the 16:9 card with Kodi's own
    thumbnail, which Kodi can cut from http streams too."""
    card = _include('ChapterCard').find('definition')
    groups = card.findall('control')
    assert len(groups) == 1 and groups[0].find('visible') is None
    assert not [p for p in card.iter('param') if p.get('name') == 'height' and p.get('value') == '112']


def test_chapter_card_shows_the_time_once():
    """The start time stands under the card, not again on the thumbnail."""
    card = next(i for i in parse(ROOT / '1080i' / 'Includes_Player.xml').iter('include')
                if i.get('name') == 'ChapterCard')
    labels = [l.findtext('label') for l in card.iter('control') if l.get('type') == 'label']
    assert labels.count('$INFO[ListItem.Label2]') == 1
