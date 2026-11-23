"""Player OSD: skip buttons, chapter marks, panels that step along the button row, the video
panel, the seek delta and the OSD on pause."""
import pytest

from conftest import ROOT, parse
from navigation import evaluate, load

OSD = 'VideoOSD.xml'
STATS = 'Skin.HasSetting(nc.osd.stats)'


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
    assert forward.findtext('label') == '⏭'
    assert forward.findtext('onclick') == 'PlayerControl(Next)'
    assert controls['601'].findtext('label') == '⏮'


@pytest.mark.parametrize('skin, row', [({}, ['605', '606', '607', '608']),
                                       ({'nc.osd.stats': '1'}, ['605', '606', '607', '608', '609'])])
def test_stats_button_follows_its_setting(skin, row):
    """One level of buttons: the "…" toggle that swapped the track buttons for stats is gone.
    Stats (Kodi's playback information) shows at the far right only with its skin setting
    (nc.osd.stats, off by default); without it chapters ends the row."""
    controls = {c.get('id'): c for c in load(OSD, skin).iter('control') if c.get('id')}
    shown = [c.get('id') for c in controls['620'].findall('control')
             if all(evaluate(v.text, skin) for v in c.findall('visible'))]
    assert shown == row
    assert controls['609'].findtext('onclick') == 'ActivateWindow(playerprocessinfo)'
    assert '610' not in controls


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


def _bar(info):
    bar = next(i for i in parse(ROOT / '1080i' / 'Includes_Player.xml').iter('include') if i.get('name') == 'PlayerBar')
    return [c for c in bar.iter('control') if c.findtext('info') == info]


def _drawn(control, tag):
    """The rows of the line (0 is its top) a texture of a progress or ranges control covers, with
    their alpha, and its width, as Kodi lays it out (GUIProgressControl::UpdateLayout): scaled
    by control size / track texture size and centred on the track. Without a track texture it
    keeps its own height and moves down by half of it."""
    from PIL import Image

    def image(name):
        path = control.findtext(name)
        return Image.open(ROOT / 'media' / path).convert('RGBA') if path else None
    track, texture = image('texturebg'), image(tag)
    scale_y = int(control.findtext('height')) / track.height if track else 1.0
    scale_x = int(control.findtext('width')) / track.width if track else 1.0
    top = int(control.findtext('top') or 0) + abs(scale_y * 0.5 * (texture.height - (track.height if track else 0)))
    rows = {}
    for y in range(texture.height):
        for row in range(int(top + scale_y * y), int(top + scale_y * (y + 1) + 0.999)):
            if top + scale_y * y <= row + 0.5 < top + scale_y * (y + 1):
                rows[row] = texture.getpixel((0, y))[3]
    return rows, scale_x * texture.width


def test_position_fills_the_line():
    """The played part lies on the 4 px line. With an empty track texture Kodi drew the fill at
    its texture's own 8 px, 4 px down: a thick bar under the line."""
    base = next(c for c in _bar('Player.ProgressCache') if c.get('type') == 'progress')
    played = next(c for c in _bar('Player.SeekBar') if c.findtext('midtexture') == 'ui/white.png')
    assert _drawn(base, 'midtexture')[0] == _drawn(played, 'midtexture')[0] == {0: 255, 1: 255, 2: 255, 3: 255}


def test_chapter_marks_leave_the_line_alone():
    """A mark is the track's colour, 4 px above and below the line. Over the line it is clear:
    there its dimmed blue stacked on the track (and on the buffer) and showed brighter than
    the track, and on the played part it vanished anyway."""
    chapters = _bar('Player.Chapters')[0]
    rows, width = _drawn(chapters, 'righttexture')
    assert {row for row, alpha in rows.items() if alpha} == {-4, -3, -2, -1, 4, 5, 6, 7}
    assert set(rows.values()) <= {0, 255}
    assert width == 2


def test_seek_head_is_cyan_and_closes_the_line():
    """The head is the cursor of the line: cyan as the played part. It reaches 6 px over and
    6 px under the line, a block that closes the played part off."""
    head = next(c for c in _bar('Player.SeekBar') if c.findtext('righttexture'))
    assert head.find('righttexture').get('colordiffuse') == 'accent'
    rows, width = _drawn(head, 'righttexture')
    assert {row for row, alpha in rows.items() if alpha} == set(range(-6, 10))
    assert set(rows.values()) <= {0, 255}
    assert width == 4


def test_panels_step_along_the_button_row():
    """Left and right in a panel move to the neighbouring button of the row, whose panel then
    shows; the subtitle panel's left neighbour is the last button of the left row."""
    controls = _controls(OSD)
    for panel, left, right in (('651', '611', '606'), ('652', '605', '607'), ('653', '606', '608')):
        assert controls[panel].findtext('onleft') == 'SetFocus({})'.format(left), panel
        assert controls[panel].findtext('onright') == 'SetFocus({})'.format(right), panel


@pytest.mark.parametrize('button, panel, prefix, settings', [('605', '651', 'sub', 'osdsubtitlesettings'),
                                                            ('606', '652', 'audio', 'osdaudiosettings')])
def test_ok_on_a_track_button_opens_all_settings(button, panel, prefix, settings):
    """Up goes into the track list on the playing track, OK opens Kodi's full settings (delays,
    subtitle look) at once: the list's last row was hard to reach, one step too far left it."""
    controls = _controls(OSD)
    assert controls[button].findtext('onclick') == 'ActivateWindow({})'.format(settings)
    assert controls[button].findtext('onup') == 'SetFocus({},$INFO[Window(Home).Property(nc.{}.pos)],absolute)'.format(panel, prefix)


@pytest.mark.parametrize('panel', ['651', '652'])
def test_track_panels_wrap_upward(panel):
    """Up on the first row lands on the last one, all settings: a container whose up leads to
    itself wraps (CGUIBaseContainer::OnUp). Down on the last row still goes back to the button."""
    controls = _controls(OSD)
    assert controls[panel].findtext('onup') == panel
    assert controls[panel].findtext('ondown') in ('605', '606')


@pytest.mark.parametrize('heading', ['$LOCALIZE[31053]', '$LOCALIZE[31054]'])
def test_track_panel_heads_show_only_their_heading(heading):
    """The head is the panel's name alone; where OK leads is in the footer (test_level_hints.py)."""
    labels = [c.findtext('label') or '' for c in load(OSD).iter('control') if c.get('type') == 'label']
    assert '[UPPERCASE]{}[/UPPERCASE]'.format(heading) in labels, heading
    assert not any(label.startswith('[UPPERCASE]' + heading + '$VAR') for label in labels)


def test_video_button_shows_a_panel():
    """Video works like audio and subtitles: focus shows a panel with what the video is, Up goes
    into it, onto its one row, all settings, which OK on the button opens at once; down goes
    back to the button. Up on the row stays: it is the panel's first and last row at once."""
    controls = _controls(OSD)
    button = controls['607']
    assert button.findtext('onup') == 'SetFocus(653)'
    assert button.findtext('onclick') == 'ActivateWindow(osdvideosettings)'
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


def test_chapters_button_opens_the_chapter_panel():
    """Chapters is a button of the right row, between video and "…": OK or Up opens the chapter
    panel (Kodi's chapters and bookmarks dialog) above the row, which stays. It always says
    chapters: Kodi has no condition for bookmarks, and the panel is where one is added, so the
    button is always there, also in a video without chapters."""
    osd = _controls(OSD)
    assert [c.get('id') for c in osd['620'].findall('control')] == ['605', '606', '607', '608', '609']
    button = osd['608']
    assert button.findtext('label') == '$LOCALIZE[31140]'
    assert button.findtext('onclick') == 'ActivateWindow(videobookmarks)'
    assert button.findtext('onup') == 'ActivateWindow(videobookmarks)'
    assert [v.text for v in button.findall('visible')] in ([], ['true'])
    assert not any(v.get('name') == 'PlayerChaptersLevel' for v in parse(ROOT / '1080i' / 'Variables.xml').iter('variable'))
    text = (ROOT / 'language' / 'resource.language.de_de' / 'strings.po').read_text(encoding='utf-8')
    assert 'msgctxt "#31140"\nmsgid "chapters"\nmsgstr "Kapitel"' in text
    assert '"#31056"' not in text
    # the rows stay under the panel, the cast row replaces them
    for cid in ('600', '620'):
        assert osd[cid].findtext('visible') == '!Window.IsActive(1141)', cid
    assert osd['650'].findtext('visible') == '!Window.IsActive(1141) + !Window.IsActive(videobookmarks)'
    for path in (ROOT / '1080i').glob('*.xml'):
        assert 'nc.chapters.panel' not in path.read_text(encoding='utf-8'), path.name


def test_chapter_panel_above_the_button():
    """The panel sits above the button row and below the seek line's top: a frame with the
    chapters' thumbnails and the bookmark buttons in its head. Up from the list goes to the
    buttons, Down or Back from either back onto the button; Left and Right past the ends move on
    to the neighbouring buttons, as in the track panels, after the panel closed at once (SetFocus
    goes to the topmost dialog): right of chapters is stats with its setting, else the row wraps
    to the left row."""
    dialog = load('VideoOSDBookmarks.xml')
    assert not any('RunScript' in (o.text or '') for o in dialog.iter())
    assert dialog.findtext('defaultcontrol') == '90'
    controls = {c.get('id'): c for c in dialog.iter('control') if c.get('id')}
    chapters, buttons = controls['11'], controls['9000']
    assert chapters.findtext('orientation') == 'horizontal'
    assert int(chapters.findtext('top')) + int(chapters.findtext('height')) <= 840
    assert [c.get('id') for c in buttons.findall('control')] == ['2', '4', '3']
    actions = lambda c, tag: [(o.get('condition') or '', o.text) for o in c.findall(tag)]
    assert actions(chapters, 'onup') == [('', '9000')]
    assert actions(chapters, 'ondown') == actions(chapters, 'onback') == [('', '90')]
    assert actions(buttons, 'onup') == [('', 'noop')]
    assert actions(buttons, 'onback') == [('', '90')]
    for control in (chapters, buttons, controls['90']):
        assert actions(control, 'onleft') == [('', 'Dialog.Close(videobookmarks,true)'), ('', 'SetFocus(607)')]
        assert actions(control, 'onright') == [('', 'Dialog.Close(videobookmarks,true)'), (STATS, 'SetFocus(609)'),
                                               ('!' + STATS, 'SetFocus(601)')]
    assert actions(buttons, 'ondown') == [('Integer.IsGreater(Container(11).NumItems,0)', '11'),
                                          ('!Integer.IsGreater(Container(11).NumItems,0)', '90')]


def test_chapter_panel_shows_with_the_focus_on_its_button():
    """As the track panels: the chapters button shows its panel as it gets the focus. Kodi fills
    the chapter list only in its own dialog, so that dialog opens on a stand-in for the button
    (90), the OSD keeping its focus on 608 below. On the stand-in Up or OK go into the list (add
    bookmark without entries), Down to the cast row of a library title, which closed opens the
    panel again (nc.osd.chapters), Back closes the OSD as on any button."""
    osd = _controls(OSD)
    assert osd['608'].findtext('onfocus') == 'ActivateWindow(videobookmarks)'
    stand_in = {c.get('id'): c for c in load('VideoOSDBookmarks.xml').iter('control') if c.get('id')}['90']
    actions = lambda tag: [(o.get('condition') or '', o.text) for o in stand_in.findall(tag)]
    filled, empty = 'Integer.IsGreater(Container(11).NumItems,0)', '!Integer.IsGreater(Container(11).NumItems,0)'
    assert actions('onup') == [(filled, '11'), (empty, '2')]
    assert actions('onclick') == [(filled, 'SetFocus(11)'), (empty, 'SetFocus(2)')]
    cast = 'VideoPlayer.Content(movies) | VideoPlayer.Content(episodes)'
    assert actions('ondown')[:3] == [(cast, 'SetProperty(nc.osd.chapters,1,home)'),
                                     (cast, 'Dialog.Close(videobookmarks,true)'), (cast, 'ActivateWindow(1141)')]
    assert actions('onback') == [('', 'Dialog.Close(videobookmarks,true)'), ('', 'Dialog.Close(videoosd)')]
    unloads = [(o.get('condition'), o.text) for o in load('Custom_1141_OSDCast.xml').findall('onunload')]
    assert unloads[0] == ('!String.IsEmpty(Window(Home).Property(nc.osd.chapters)) + String.IsEmpty(Window(Home).Property(nc.osd.ret))'
                          ' + Window.IsActive(videoosd)', 'ActivateWindow(videobookmarks)')
    assert unloads[-1] == (None, 'ClearProperty(nc.osd.chapters,home)')
    assert 'ClearProperty(nc.osd.chapters,home)' in [o.text for o in load(OSD).findall('onunload')]


def test_down_from_the_controls_opens_the_cast_row():
    """Down from either row goes straight to the cast and crew row of a library title; the
    chapters are a button now, not a step on the way."""
    osd = _controls(OSD)
    cast = 'VideoPlayer.Content(movies) | VideoPlayer.Content(episodes)'
    for cid in ('600', '620'):
        assert [(o.get('condition'), o.text) for o in osd[cid].findall('ondown')] == [(cast, 'ActivateWindow(1141)')], cid
    for name in ('VideoOSD.xml', 'Custom_1141_OSDCast.xml', 'Timers.xml'):
        assert 'ActivateWindow(videobookmarks)' not in [o.text for o in load(name).iter('ondown')], name
    assert 'Dialog.Close(videobookmarks)' not in (ROOT / '1080i' / 'Custom_1141_OSDCast.xml').read_text(encoding='utf-8')
    assert 'Dialog.Close(videobookmarks)' not in (ROOT / '1080i' / 'Timers.xml').read_text(encoding='utf-8')


def test_back_from_a_chain_opens_the_cast_row():
    """A chain started from the player's cast row ends on the OSD with the cast row up again
    (VideoFullScreen.xml): a stand-in takes the focus and, queued after the OSD is up, opens
    the row once (nc.osd.rows); its lists wait for TMDb Helper's manager (OSDCreditsRow). The
    bar takes the focus before the row opens, so the row closes onto it."""
    root = load(OSD)
    chain = '!String.IsEmpty(Window(Home).Property(nc.osd.chain))'
    onload = [(o.get('condition') or '', o.text) for o in root.findall('onload')]
    assert (chain, 'SetProperty(nc.osd.rows,1,home)') in onload
    assert (chain, 'SetFocus(699)') in onload
    rows = 'Window(Home).Property(nc.osd.rows)'
    stand_in = _controls(OSD)['699']
    assert [(o.get('condition'), o.text) for o in stand_in.findall('onfocus')] == [
        ('!String.IsEmpty({})'.format(rows), 'ClearProperty(nc.osd.rows,home)'),
        # the bar first: the cast row closes onto it, not onto the stand-in out of sight
        ('!String.IsEmpty({})'.format(rows), 'SetFocus(602)'),
        ('!String.IsEmpty({})'.format(rows), 'ActivateWindow(1141)'),
        ('String.IsEmpty({})'.format(rows), 'SetFocus(602)')]
    for move in ('onup', 'ondown', 'onleft', 'onright'):
        assert stand_in.findtext(move) == '602', move


def _stats_lines():
    tree = parse(ROOT / '1080i' / 'DialogPlayerProcessInfo.xml')
    return {dict((p.get('name'), p.get('value')) for p in inc.iter('param'))['key']:
            dict((p.get('name'), p.get('value')) for p in inc.iter('param'))
            for inc in tree.iter('include') if inc.get('content') == 'FactLine'}


def test_stats_name_the_dolby_vision_profile_on_kodi_22():
    """Kodi 22's VideoPlayer.HdrDetail (DV profile and layer, 8.4, 7FEL) after the HDR type; only
    there and only with HDR, Kodi 21 has no such label."""
    hdr = _stats_lines()['hdr']
    assert hdr['value'].startswith('$VAR[PlayerHdr]') and '$INFO[VideoPlayer.HdrDetail' in hdr['value']
    assert hdr['visible'] == '$EXP[KodiPiers] + !String.IsEmpty(VideoPlayer.HdrType)'


def test_the_stats_panel_grows_by_the_hdr_line_only():
    """Kodi 21 and SDR keep the panel as it was: its back only grows with the hdr line."""
    tree = parse(ROOT / '1080i' / 'DialogPlayerProcessInfo.xml')
    backs = {img.findtext('visible'): img.findtext('height')
             for img in tree.iter('control') if img.get('type') == 'image'}
    hdr = _stats_lines()['hdr']['visible']
    assert backs == {'![{}]'.format(hdr): '380', hdr: '432'}
