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
    ListItem.Trailer (TMDb Helper's is a YouTube link; without the YouTube add-on the click offers
    it). Never over
    a video that plays (a chain from the OSD): the trailer would end it."""
    params, clicks = _pill('9008')
    visible = params['visible']
    assert 'String.IsEqual(ListItem.DBType,movie)' in visible
    assert '!String.IsEmpty(ListItem.Trailer)' in visible
    # without the YouTube add-on too: the click offers it (scripts/nightcity.py trailer)
    assert 'youtube' not in visible
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
    # the recommendations wait until the trailer is over (scripts/nightcity.py trailer)
    assert [o.text for o in nested.findall('onclick')] == ['SetProperty(nc.trailer.lists,1,home)', 'NotifyAll(nightcity,trailer)']
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


def test_recommendations_wait_while_a_trailer_plays():
    """Kodi reloads the page's plugin lists when playback starts and stops: with the trailer the
    page stays open, so the recommendations hold off (nc.trailer.lists) and the cast reloads
    alone; two plugins starting at once crash Kodi."""
    variables = {v.get('name'): v for v in parse(SKIN / 'Variables.xml').iter('variable')}
    for value in variables['InfoSimilarPath'].findall('value'):
        assert 'String.IsEmpty(Window(Home).Property(nc.trailer.lists))' in value.get('condition')


def test_the_playing_title_offers_no_play():
    """The page of the title that plays: a movie, or an episode page on the episode that plays
    (a chain from the OSD's cast row reaches it, the OSD's info button opens it). Resume and from
    start would start it again from the beginning, ... (Kodi's context menu) offers the same:
    they hide, and one button leads back to the video (9009; in a chain 9004 does). The same test
    as "ends at" (EndsAtTags): the page's item, an episode page's episode in its list."""
    info = parse(SKIN / 'Includes_Info.xml')
    tags = next(i for i in info.iter('include') if i.get('name') == 'EndsAtTags')
    playing = next(p.get('value') for p in tags.iter('param') if p.get('name') == 'playing')
    expressions = {e.get('name'): e.text for e in info.iter('expression')}
    movie = 'String.IsEqual(ListItem.DBType,movie) + [{}]'.format(playing.replace('$PARAM[item]', 'ListItem'))
    episode = 'String.IsEqual(ListItem.DBType,episode) + [{}]'.format(playing.replace('$PARAM[item]', 'Container(5100).ListItem'))
    assert expressions['InfoPlaying'] == '[{}] | [{}]'.format(movie, episode)
    for cid in ('9001', '9002', '9005'):
        params, _ = _pill(cid)
        assert params['visible'].endswith(' + !$EXP[InfoPlaying]'), cid
    more = next(c for c in parse(SKIN / 'DialogVideoInfo.xml').iter('control') if c.get('id') == '9003')
    assert more.findtext('visible').endswith(' + !$EXP[InfoPlaying]')
    params, _ = _pill('9004')
    assert '$EXP[InfoPlaying]' in params['enable']
    params, clicks = _pill('9009')
    assert params['label'] == '‹ $LOCALIZE[31330]'
    assert params['visible'] == '$EXP[InfoPlaying] + String.IsEmpty(Window(Home).Property(TMDbHelper.Instance))'
    assert (params['onclick'], params['onclick2']) == ('Dialog.Close(movieinformation)', 'ActivateWindow(fullscreenvideo)')



def test_more_pill_keeps_its_text_colour_on_the_playing_title():
    """Kodi marks the item that plays as selected, and a label in a list draws a selected item in
    its selectedcolor (white unless set): on the page of the playing movie the focused ... read
    white on cyan. The pill's label keeps its colour either way."""
    base = parse(SKIN / 'Includes_Base.xml')
    pill = next(i for i in base.iter('include') if i.get('name') == 'MorePill')
    label = next(c for c in pill.iter('control') if c.get('type') == 'label')
    assert label.findtext('selectedcolor') == label.findtext('textcolor') == '$PARAM[textcolor]'


def test_back_held_out_of_a_player_chain_opens_the_controls():
    """Back held ends a chain from the OSD's cast row on the player's controls, their own first
    button (nc.chain.return controls, scripts/nightcity.py back_to_start); a chain walked back
    page by page returns to the cast row (nc.chain.return osd)."""
    onloads = [(o.get('condition'), o.text) for o in parse(SKIN / 'VideoFullScreen.xml').findall('onload')]
    held = 'String.IsEqual(Window(Home).Property(nc.chain.return),controls)'
    assert (held, 'ClearProperty(nc.chain.return,home)') in onloads
    assert (held, 'ActivateWindow(videoosd)') in onloads
    assert not [text for cond, text in onloads if cond == held and 'nc.osd.chain' in text]
