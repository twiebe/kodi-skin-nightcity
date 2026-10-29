"""TMDb lists never show the page before (test_stale_lists.py in static): Matrix, a person, a
film, Back, another film. While the second film's lists still hold the first film's items, they
are faded out (TmdbFresh<list> false); once loaded they show. The similar movies wait for the
cast and stay on the first film for seconds: the test moves down to them at once, so the row is
on screen, and checks the screen."""
import pathlib
import time
import xml.etree.ElementTree as ET

import pytest
from PIL import Image

from conftest import action, builtin, cond, info, rpc, screenshot, wait_for
from test_tmdb_chain import _leave_chain, _list_in, _page, matrix  # noqa: F401 (fixture)

pytestmark = pytest.mark.e2e

ROOT = pathlib.Path(__file__).resolve().parents[2]
LISTS = ('5500', '5300')


def fresh(cid):
    root = ET.parse(ROOT / '1080i' / 'Includes_Tmdb.xml').getroot()
    return next(e.text.strip() for e in root.iter('expression') if e.get('name') == 'TmdbFresh' + cid)


def _true(condition):
    return cond(condition)[condition]


def content(cid):
    labels = ['Container({}).ListItem({}).Label'.format(cid, i) for i in range(4)]
    got = rpc('XBMC.GetInfoLabels', {'labels': labels})
    return '|'.join(got[k] for k in labels)


def shows_before(cid, before):
    """The list holds the items of the page before (`before`, its content()) while TmdbFresh
    holds. These are two calls, so TmdbFresh is read first: the list may take its new items
    between them, never the old ones back. Read the other way round, a list that turned to
    its new items between the calls looked old and fresh at once."""
    return _true(fresh(cid)) and content(cid) == before


def row_brightness(path):
    """Mean brightness of the row on screen below the head of the page (y 680 to 1000 of
    1080), where its cards are."""
    img = Image.open(path).convert('L')
    w, h = img.size
    box = img.crop((int(w * 40 / 1920), int(h * 680 / 1080), int(w * 1880 / 1920), int(h * 1000 / 1080)))
    pixels = list(box.getdata())
    return sum(pixels) / len(pixels)


def _to_film(index):
    _list_in('5510')
    builtin('SetFocus(5510,{},absolute)'.format(index))
    time.sleep(0.5)
    action('select')
    wait_for('String.IsEqual(Window(Home).Property(TMDbHelper.Position),3)', timeout=30)


def test_next_film_never_shows_the_film_before(matrix):
    builtin('NotifyAll(nightcity,info:movie:{})'.format(matrix))
    wait_for('Window.IsActive(movieinformation)', timeout=30)
    _list_in('5500')
    builtin('SetFocus(5500,0,absolute)')
    time.sleep(0.5)
    action('select')
    _page(2)
    wait_for('Integer.IsGreater(Container(5510).NumItems,40) + !Container(5510).IsUpdating', timeout=30)
    # films TMDb Helper has not cached yet, or their lists load before anything can be seen
    pick = 5 + int(time.time()) % 30
    _to_film(pick)
    # both lists loaded for the first film
    wait_for('{} + {}'.format(fresh('5500'), fresh('5300')), timeout=40)
    first = info('ListItem.Label')['ListItem.Label']
    before = {c: content(c) for c in LISTS}
    action('back')
    _page(2)
    _to_film(pick + 1)
    wait_for('!String.IsEmpty(ListItem.Label) + !String.IsEqual(ListItem.Label,{})'.format(first))
    if content('5300') != before['5300']:
        # Kodi emptied the row with the page, so nothing stale can show this time
        pytest.skip('the similar row did not hold the first film: nothing to test')
    builtin('SetFocus(5300)')
    wait_for('Control.HasFocus(5300)')
    time.sleep(0.4)  # the rows scroll
    shot = screenshot('stale-loading')
    faded = None
    if content('5300') == before['5300']:  # still the first film's similar movies on the shot
        assert not shows_before('5300', before['5300'])
        # the faded row leaves the backdrop: 10 to 27 measured, a bright backdrop passes 25
        # alone; a row with its posters is 50 to 107
        faded = row_brightness(shot)
        assert faded < 40, faded
    # never the first film's items while shown, until both lists are in
    end = time.time() + 40
    while time.time() < end and not (_true(fresh('5500')) and _true(fresh('5300'))):
        for c in LISTS:
            assert not shows_before(c, before[c]), (c, before[c])
        time.sleep(0.03)
    assert _true(fresh('5500')) and _true(fresh('5300')), 'the second film never showed its lists'
    # its similar movies show, once their posters are in: on the same backdrop well above the
    # faded row
    least = 25 if faded is None else faded + 25
    for _ in range(10):
        time.sleep(1.5)
        if row_brightness(screenshot('stale-second-film')) > least:
            break
    assert row_brightness(screenshot('stale-second-film')) > least, (faded, least)


def test_a_new_search_never_shows_the_search_before(home):
    """TMDb search rows keep the results of the search before for seconds after a new search,
    without IsUpdating: the row stays hidden until its loader holds the new results."""
    addons = rpc('Addons.GetAddons', {'type': 'xbmc.python.pluginsource', 'enabled': True})['addons']
    if 'plugin.video.themoviedb.helper' not in [a['addonid'] for a in addons]:
        pytest.skip('TMDb Helper not installed')
    builtin('SetFocus(9104)')
    wait_for('String.IsEqual(Window(Home).Property(nc.page),search)')
    builtin('NotifyAll(nightcity,search:matrix)')
    wait_for('Control.IsVisible(9714) + String.IsEqual(Container(9704).ListItem(0).Property(param.query),matrix)', timeout=30)
    builtin('NotifyAll(nightcity,search:alien)')
    stale = ('Control.IsVisible(9714) + !String.IsEqual(Container(9724).ListItem(0).Property(param.query),'
             'Window(Home).Property(nc.search))')
    end = time.time() + 8
    while time.time() < end:
        if _true(stale):
            # Control.IsVisible is the state of the frame drawn last. The service sets the new
            # term from its own thread, so for up to one frame the row drawn before it still
            # reads visible next to the new term; the frame after hides it. A row shown with
            # the search before stays so for seconds (the TMDb rows keep it that long).
            time.sleep(0.1)
            assert not _true(stale)
        if _true('Control.IsVisible(9714) + String.IsEqual(Container(9704).ListItem(0).Property(param.query),alien)'):
            break
        time.sleep(0.05)
    wait_for('Control.IsVisible(9714) + String.IsEqual(Container(9704).ListItem(0).Property(param.query),alien)', timeout=30)
