"""Info on a spotlight (movies, shows, music) parks the focus on the spotlight's data list, which
shows nothing, and asks Kodi for the info page there. Back from that page left the focus on the
hidden list: left and right still moved the spotlight, but no button showed the cursor. Back
returns to the info button (DESIGN.md: back returns where you left)."""
from conftest import ROOT, parse

# info button: hidden data lists it parks on (the movie hero's: home's, the movies page's)
BUTTONS = {'9011': ('9000', '9003'), '9552': ('9001',), '9853': ('9002',)}
PARKED = ('9000', '9001', '9002', '9003')
OPEN = '[Window.IsVisible(movieinformation) | Window.IsVisible(musicinformation)]'


def _clicks(cid):
    for path in (ROOT / '1080i').glob('*.xml'):
        for inc in parse(path).iter('include'):
            params = {p.get('name'): p.get('value') for p in inc.findall('param')}
            if params.get('id') == cid:
                return [params.get('onclick'), params.get('onclick2')] + [o.text for o in inc.findall('onclick')]
    raise AssertionError(cid)


def test_info_buttons_remember_themselves():
    """First: Action(Info) opens the page modally, the click's later actions run only once the
    page closed, too late for the timer."""
    for cid, data in BUTTONS.items():
        clicks = [c for c in _clicks(cid) if c and c != 'noop']
        assert clicks == (['SetProperty(nc.spot.back,{},home)'.format(cid)] + ['SetFocus({})'.format(d) for d in data]
                          + ['Action(Info)']), cid


def test_back_from_the_info_page_returns_to_the_info_button():
    timers = {t.findtext('name'): t for t in parse(ROOT / '1080i' / 'Timers.xml').iter('timer')}
    timer = timers['nc_spot_back']
    # the info page opened from a spotlight ...
    assert timer.findtext('start') == '!String.IsEmpty(Window(Home).Property(nc.spot.back)) + ' + OPEN
    # ... and Home is in front again (also after a chain or a playback started from it)
    assert timer.findtext('stop') == ('Window.IsActive(home) + !Window.IsVisible(movieinformation) + '
                                      '!Window.IsVisible(musicinformation) + !System.HasActiveModalDialog')
    onstop = [(o.get('condition') or '', o.text) for o in timer.findall('onstop')]
    parked = ' | '.join(['Control.HasFocus({})'.format(d) for d in PARKED]
                        # a still spotlight parks on the card of the title its hero shows
                        + ['ControlGroup({}).HasFocus()'.format(g) for g in ('9210', '9410', '9510')])
    assert onstop == [('[{}]'.format(parked), 'SetFocus($INFO[Window(Home).Property(nc.spot.back)])'),
                      ('', 'ClearProperty(nc.spot.back,home)')]
