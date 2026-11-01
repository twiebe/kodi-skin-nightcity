"""The trailer on a movie's info page: a button right of play, the trailer in full screen over
the page (scripts/nightcity.py trailer)."""
from conftest import ROOT, parse

SKIN = ROOT / '1080i'
INFO = 'DialogVideoInfo.xml'
WANTED = '!String.IsEmpty(Window(Home).Property(nc.trailer))'


def _root():
    return parse(SKIN / INFO)


def _button_ids():
    """The ids of the pills in the button row, in order."""
    row = _root().find('.//control[@id="9000"]')
    ids = []
    for el in row:
        if el.tag == 'include':
            ids += [p.get('value') for p in el.findall('param') if p.get('name') == 'id']
        elif el.tag == 'control':
            ids.append(el.get('id'))
    return ids


def _pill(cid):
    for inc in _root().iter('include'):
        params = {p.get('name'): p.get('value') for p in inc.findall('param')}
        if params.get('id') == cid:
            return params, [(o.get('condition') or '', o.text) for o in inc.iter('onclick')]
    raise AssertionError(cid)


def _actions(control, tag):
    return [(o.get('condition') or '', o.text) for o in control.findall(tag)]


def test_trailer_sits_right_of_play():
    ids = _button_ids()
    assert ids[ids.index('9001') + 1] == '9008'


def test_trailer_shows_on_a_movie_with_a_trailer_it_can_play():
    """On a movie's page, a library movie or a TMDb title in a chain alike: both have
    ListItem.Trailer (TMDb Helper's is a YouTube link, which needs the YouTube add-on). Never over
    a video that plays (a chain from the OSD): the trailer would end it."""
    params, clicks = _pill('9008')
    visible = params['visible']
    assert 'String.IsEqual(ListItem.DBType,movie)' in visible
    assert '!String.IsEmpty(ListItem.Trailer)' in visible
    assert '[!String.StartsWith(ListItem.Trailer,plugin://plugin.video.youtube/) | System.AddonIsEnabled(plugin.video.youtube)]' in visible
    # it stays while its own trailer plays, and while it has the focus: after Back the player
    # takes a few frames to stop, a button hidden meanwhile lost the focus to play (9001)
    assert '[!Player.HasVideo | {} | Control.HasFocus(9008)]'.format(WANTED) in visible
    assert '$LOCALIZE[31041]' in params['label']


def test_trailer_click_covers_the_page_and_takes_the_keys():
    """The click shows the full screen video at once and gives the keys to it (9099), then the
    service plays the trailer and follows it."""
    params, _ = _pill('9008')
    assert params['onclick'] == 'SetProperty(nc.trailer,1,home)'
    assert params['onclick2'] == 'SetFocus(9099)'
    button = _root().find('.//control[@id="9000"]')
    nested = [inc for inc in button.findall('include') if any(p.get('value') == '9008' for p in inc.findall('param'))][0]
    assert [o.text for o in nested.findall('onclick')] == ['NotifyAll(nightcity,trailer)']
    assert [i.text for i in nested.findall('include')] == ['ChainBackGuard']


def test_trailer_plays_in_full_screen_over_everything():
    controls = _root().find('controls')
    overlay = list(controls)[-1]
    assert overlay.get('id') == '9095'
    assert overlay.findtext('visible') == WANTED
    video = overlay.find('control[@type="videowindow"]')
    assert [video.findtext(k) for k in ('left', 'top', 'width', 'height')] == ['0', '0', '1920', '1080']
    # under the video a dark screen, also while the trailer loads
    first = overlay.findall('control')[0]
    assert first.get('type') == 'image' and first.findtext('width') == '1920'


def test_keys_while_the_trailer_plays():
    """Back ends it on the trailer button: Kodi counts Back as handled, and keeps the page, only
    when it moves the focus by a control id (CGUIWindow::OnMove), not with SetFocus. OK pauses,
    Left and Right seek, Up and Down do nothing."""
    keys = _root().find('.//control[@id="9099"]')
    assert keys.get('type') == 'button'
    assert keys.find('visible') is None  # takes the focus in the frame the click shows the overlay
    assert _actions(keys, 'onback') == [
        ('', 'ClearProperty(nc.trailer,home)'),
        ('Player.HasVideo + String.IsEmpty(VideoPlayer.DBID)', 'PlayerControl(Stop)'), ('', '9008')]
    assert _actions(keys, 'onclick') == [('Player.HasVideo', 'PlayerControl(Play)')]
    assert _actions(keys, 'onleft') == [('Player.HasVideo', 'Seek(-10)')]
    assert _actions(keys, 'onright') == [('Player.HasVideo', 'Seek(10)')]
    assert _actions(keys, 'onup') == [('', 'noop')] and _actions(keys, 'ondown') == [('', 'noop')]


def test_trailer_label_is_english():
    po = (ROOT / 'language' / 'resource.language.en_gb' / 'strings.po').read_text(encoding='utf-8')
    assert 'msgctxt "#31041"\nmsgid "trailer"\n' in po
