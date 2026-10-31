"""Player OSD: skip buttons, chapter marks, panels that step along the button row, the video
panel, the seek delta and the OSD on pause."""
from conftest import ROOT, parse
from navigation import load

OSD = 'VideoOSD.xml'
MORE = 'Window(Home).Property(nc.osd.more)'


def _controls(name):
    return {c.get('id'): c for c in load(name).iter('control') if c.get('id')}


def _variable(name):
    var = next(v for v in parse(ROOT / '1080i' / 'Variables.xml').iter('variable') if v.get('name') == name)
    return [(v.get('condition'), v.text) for v in var.iter('value')]


def test_skip_forward_beside_stop():
    """⏭ right of stop mirrors ⏮ at the other end of the row: next chapter, or the next item."""
    controls = _controls(OSD)
    row = [c.get('id') for c in controls['600'].findall('control')]
    assert row[-2:] == ['604', '611']
    forward = controls['611']
    assert forward.findtext('label') == '[UPPERCASE]⏭[/UPPERCASE]'
    assert forward.findtext('onclick') == 'PlayerControl(Next)'
    assert controls['601'].findtext('label') == '[UPPERCASE]⏮[/UPPERCASE]'


def test_chapters_only_on_the_first_level():
    """"…" swaps subtitles, audio and video for stats."""
    controls = _controls(OSD)
    for button in ('605', '606', '607'):
        assert controls[button].findtext('visible') == 'String.IsEmpty({})'.format(MORE), button
    assert controls['609'].findtext('visible') == '!String.IsEmpty({})'.format(MORE)


def test_chapter_marks_have_a_colour():
    """The marks were drawn in the background colour and only showed where they cut the line.
    Kodi's ranges run from one chapter start to the next (0 to the second chapter, ...), so the
    marks sit at the range ends: at the starts, the last chapter had none and the first one sat
    at 0."""
    bar = next(i for i in parse(ROOT / '1080i' / 'Includes_Player.xml').iter('include') if i.get('name') == 'PlayerBar')
    chapters = next(c for c in bar.iter('control') if c.findtext('info') == 'Player.Chapters')
    # the track's own dimmed blue: pink and then the bright line blue stood out too much
    track = next(c for c in bar.iter('control') if c.findtext('info') == 'Player.ProgressCache')
    assert chapters.find('righttexture').get('colordiffuse') == track.find('texturebg').get('colordiffuse') == 'border_dim'
    assert chapters.find('righttexture').text == 'ui/tick.png'
    assert not chapters.find('lefttexture').text


def test_panels_step_along_the_button_row():
    """Left and right in a panel move to the neighbouring button of the row, whose panel then
    shows; the subtitle panel's left neighbour is the last button of the left row."""
    controls = _controls(OSD)
    for panel, left, right in (('651', '611', '606'), ('652', '605', '607'), ('653', '606', '610')):
        assert controls[panel].findtext('onleft') == 'SetFocus({})'.format(left), panel
        assert controls[panel].findtext('onright') == 'SetFocus({})'.format(right), panel


def test_video_button_shows_a_panel():
    """Video works like audio and subtitles: focus shows a panel with what the video is, up or OK
    goes into it, its row opens Kodi's video settings, down goes back to the button."""
    controls = _controls(OSD)
    button = controls['607']
    assert button.findtext('onup') == 'SetFocus(653)'
    assert button.findtext('onclick') == 'SetFocus(653)'
    row = controls['653']
    assert row.findtext('onclick') == 'ActivateWindow(osdvideosettings)'
    # Kodi gives the rows of a grouplist its up and down, whatever the rows say
    rows = next(g for g in load(OSD).iter('control')
                if g.get('type') == 'grouplist' and g.find("control[@id='653']") is not None)
    assert rows.findtext('ondown') == '607' and rows.findtext('onup') == 'noop'
    assert row.find('ondown') is None and row.find('onup') is None
    assert '$LOCALIZE[31139]' in row.findtext('label')
    panel = next(g for g in load(OSD).iter('control') if g.find(".//control[@id='653']") is not None)
    assert 'Control.HasFocus(607) | Control.HasFocus(653)' in [v.text for v in panel.findall('visible')]
    text = ''.join(panel.itertext())
    for part in ('VideoPlayer.VideoCodec', '$VAR[PlayerResolution]', '$VAR[PlayerHdr]',
                 'Player.Process(videofps)', 'VideoPlayer.VideoAspect', 'VideoPlayer.VideoBitrate'):
        assert part in text, part


def test_video_panel_strings():
    for lang, text in (('en_gb', ''),):
        po = (ROOT / 'language' / 'resource.language.{}'.format(lang) / 'strings.po').read_text(encoding='utf-8')
        assert 'msgctxt "#31230"\nmsgid "frame rate"\nmsgstr "{}"'.format(text) in po


def test_seek_delta_while_stepping():
    """Kodi fills Player.SeekStepSize while the steps add up and Player.SeekOffset only once the
    seek ran, so the bubble shows the step size first."""
    assert _variable('SeekDelta') == [('!String.IsEmpty(Player.SeekStepSize)', '$INFO[Player.SeekStepSize]'),
                                      (None, '$INFO[Player.SeekOffset]')]
    bubble = next(i for i in parse(ROOT / '1080i' / 'Includes_Player.xml').iter('include') if i.get('name') == 'SeekBubble')
    label = next(c for c in bubble.iter('control') if c.get('type') == 'label').findtext('label')
    assert label.startswith('$VAR[SeekDelta,[COLOR state_text],[/COLOR]  ]')
    assert 'Player.SeekOffset' not in label


def test_pause_opens_the_osd_once():
    """A modeless dialog with a visible condition opens the OSD when playback pauses and remembers
    it (nc.osd.paused), so closing the OSD while paused does not bring it back; resuming clears the
    flag and closes an OSD that the pause opened and that is still open."""
    root = parse(ROOT / '1080i' / 'Custom_1150_PauseOSD.xml')
    assert root.get('type') == 'dialog' and root.get('id') == '1150'
    flag = 'String.IsEmpty(Window(Home).Property(nc.osd.paused))'
    visible = root.findtext('visible')
    assert '[Player.Paused + !Player.Caching + Window.IsActive(fullscreenvideo) + {}]'.format(flag) in visible
    assert '[!Player.Paused + !{}]'.format(flag) in visible
    onload = [(o.get('condition'), o.text) for o in root.findall('onload')]
    assert ('Player.Paused', 'SetProperty(nc.osd.paused,1,home)') in onload
    # only over the bare video: not when the OSD is already up or another dialog has the remote
    opens = [c for c, t in onload if t == 'ActivateWindow(videoosd)']
    assert opens == ['Player.Paused + !Window.IsActive(videoosd) + !System.HasActiveModalDialog']
    assert (opens[0], 'SetProperty(nc.osd.auto,1,home)') in onload
    assert ('!Player.Paused', 'ClearProperty(nc.osd.paused,home)') in onload
    closes = [(c, t) for c, t in onload if t == 'Dialog.Close(videoosd)']
    assert closes == [('!Player.Paused + !String.IsEmpty(Window(Home).Property(nc.osd.auto))', 'Dialog.Close(videoosd)')]
    assert ('!Player.Paused', 'ClearProperty(nc.osd.auto,home)') in onload
    assert 'ClearProperty(nc.osd.auto,home)' in [o.text for o in parse(ROOT / '1080i' / OSD).iter('onunload')]
    assert root.find('controls') is not None and not list(root.find('controls'))
    assert not [o for o in root.iter('onload') if 'RunScript' in (o.text or '')]


def _actions(control, tag):
    return [a.text for a in control.findall(tag)]


def test_chapters_button_is_gone():
    """The chapter row is one Down from the bar: no chapters button, no row that pops up over
    the bar in the button's place."""
    osd = _controls(OSD)
    assert '608' not in osd
    for cid in ('600', '620', '650'):
        assert osd[cid].findtext('visible') == '!Window.IsActive(1141) + !Window.IsActive(videobookmarks)', cid
    for path in (ROOT / '1080i').glob('*.xml'):
        assert 'nc.chapters.panel' not in path.read_text(encoding='utf-8'), path.name
    dialog = load('VideoOSDBookmarks.xml')
    assert not any('RunScript' in (o.text or '') for o in dialog.iter())
    controls = {c.get('id'): c for c in dialog.iter('control') if c.get('id')}
    assert '90' not in controls
    ups = [(o.get('condition') or '', o.text) for o in controls['9000'].findall('onup')]
    assert ups == [('', 'Dialog.Close(videobookmarks)')]


def test_back_from_a_chain_opens_the_chapter_row():
    """A chain started from the player's cast row ends on the OSD with the chapter row up
    (VideoFullScreen.xml): a stand-in takes the focus and, queued after the OSD is up, opens
    the row once (nc.osd.rows); when the row closes the focus comes back to it and moves on to
    the bar."""
    root = load(OSD)
    chain = '!String.IsEmpty(Window(Home).Property(nc.osd.chain))'
    onload = [(o.get('condition') or '', o.text) for o in root.findall('onload')]
    assert (chain, 'SetProperty(nc.osd.rows,1,home)') in onload
    assert (chain, 'SetFocus(699)') in onload
    rows = 'Window(Home).Property(nc.osd.rows)'
    stand_in = _controls(OSD)['699']
    assert [(o.get('condition'), o.text) for o in stand_in.findall('onfocus')] == [
        ('!String.IsEmpty({})'.format(rows), 'ClearProperty(nc.osd.rows,home)'),
        ('!String.IsEmpty({})'.format(rows), 'ActivateWindow(videobookmarks)'),
        ('String.IsEmpty({})'.format(rows), 'SetFocus(602)')]
    for move in ('onup', 'ondown', 'onleft', 'onright'):
        assert stand_in.findtext(move) == '602', move
