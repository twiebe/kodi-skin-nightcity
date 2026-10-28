from conftest import ROOT, parse

REQUIRED = [
    # Tasks 1, 4, 6-8
    'Font.xml', 'Includes.xml', 'Home.xml', 'SkinSettings.xml', 'Timers.xml', 'DialogKeyboard.xml',
    # Task 9
    'MyVideoNav.xml', 'DialogVideoInfo.xml', 'DialogVideoManager.xml',
    # Task 10
    'VideoFullScreen.xml', 'VideoOSD.xml', 'DialogSeekBar.xml', 'DialogFullScreenInfo.xml',
    'DialogPlayerProcessInfo.xml', 'VideoOSDBookmarks.xml', 'DialogSubtitles.xml', 'DialogSlider.xml',
    # Task 11
    'Startup.xml', 'Pointer.xml', 'DialogBusy.xml', 'DialogConfirm.xml', 'DialogSelect.xml',
    'DialogContextMenu.xml', 'DialogNumeric.xml', 'DialogNotification.xml',
    'DialogExtendedProgressBar.xml', 'DialogTextViewer.xml', 'DialogButtonMenu.xml',
    'DialogVolumeBar.xml', 'DialogSettings.xml', 'DialogAddonSettings.xml', 'DialogAddonInfo.xml',
    'AddonBrowser.xml', 'Settings.xml', 'SettingsCategory.xml', 'SettingsSystemInfo.xml',
    'SettingsProfile.xml', 'FileBrowser.xml', 'DialogMediaSource.xml', 'FileManager.xml',
    'SmartPlaylistEditor.xml', 'SmartPlaylistRule.xml',
    # settings console
    'EventLog.xml',
]


def test_required_windows_exist():
    missing = [name for name in REQUIRED if not (ROOT / '1080i' / name).exists()]
    assert not missing


def test_no_music_pvr_windows():
    names = [p.name for p in (ROOT / '1080i').glob('*.xml')]
    bad = [n for n in names if n.startswith(('MyMusic', 'MyPVR', 'DialogPVR')) or n in ('MyPics.xml', 'MyGames.xml')]
    assert not bad


def test_text_viewer_scrolls_with_remote():
    """DialogTextViewer text is cut off unless a focusable scrollbar pages it."""
    window = parse(ROOT / '1080i' / 'DialogTextViewer.xml')
    textbox = next(c for c in window.iter('control') if c.get('id') == '5')
    page = textbox.findtext('pagecontrol')
    scrollbar = next((c for c in window.iter('control') if c.get('id') == page), None)
    assert scrollbar is not None and scrollbar.get('type') == 'scrollbar'
    assert window.findtext('defaultcontrol') == page


def test_tmdbhelper_service_enabled():
    """TMDb Helper's poller idles until the skin sets Skin.SetBool(TMDbHelper.Service)."""
    for name in ('Startup.xml', 'Home.xml'):
        onloads = [el.text for el in parse(ROOT / '1080i' / name).iter('onload')]
        assert any('Skin.SetBool(TMDbHelper.Service)' in (t or '') for t in onloads), name


def test_info_bar_resolution_has_p():
    text = (ROOT / '1080i' / 'DialogFullScreenInfo.xml').read_text(encoding='utf-8')
    assert 'value="$INFO[VideoPlayer.VideoResolution]"' not in text


def _osd_buttons(group_id):
    osd = parse(ROOT / '1080i' / 'VideoOSD.xml')
    row = next(c for c in osd.iter('control') if c.get('id') == group_id)
    calls = [c for c in row.findall('include') if c.get('content') == 'PillButton']
    return {next(p.get('value') for p in c.findall('param') if p.get('name') == 'id'): c for c in calls}


def _arg(call, name):
    return next((p.get('value') for p in call.findall('param') if p.get('name') == name), '')


def test_osd_button_rows():
    """Play controls, stop and skip forward left; subtitles, audio, video and "…" right. "…"
    swaps subtitles, audio and video for stats."""
    assert list(_osd_buttons('600')) == ['601', '602', '603', '604', '611']
    right = _osd_buttons('620')
    assert list(right) == ['605', '606', '607', '609', '610']
    assert _arg(right['609'], 'visible') == '!String.IsEmpty(Window(Home).Property(nc.osd.more))'
    assert _arg(right['609'], 'label') == '$LOCALIZE[31155]'
    for button in ('605', '606', '607'):
        assert _arg(right[button], 'visible') == 'String.IsEmpty(Window(Home).Property(nc.osd.more))'


def test_stats_string():
    for lang, text in (('en_gb', ''),):
        po = (ROOT / 'language' / 'resource.language.{}'.format(lang) / 'strings.po').read_text(encoding='utf-8')
        assert 'msgctxt "#31155"\nmsgid "stats"\nmsgstr "{}"'.format(text) in po


def test_chapters_dialog_one_heading():
    """The chapters dialog has a single heading, no "bookmarks" kicker above it."""
    root = parse(ROOT / '1080i' / 'VideoOSDBookmarks.xml')
    heading = next(c for c in root.iter('include') if c.get('content') == 'RowHeader')
    assert not _arg(heading, 'kicker') and '31140' in _arg(heading, 'label')


def test_chapters_episode_bookmark_only_when_enabled():
    """Kodi disables button 4 (episode bookmark) unless the file can take one; a disabled button
    is hidden instead of sitting empty in the row."""
    root = parse(ROOT / '1080i' / 'VideoOSDBookmarks.xml')
    button = next(c for c in root.iter('include') if c.get('content') == 'Button' and _arg(c, 'id') == '4')
    assert _arg(button, 'visible') == 'Control.IsEnabled(4)'


def test_osd_track_panels():
    """Subtitles and audio open a track panel above the row: up from the button jumps into its
    list, down goes back, the last row opens Kodi's full settings."""
    text = (ROOT / '1080i' / 'VideoOSD.xml').read_text(encoding='utf-8')
    right = _osd_buttons('620')
    for button, panel, settings in (('605', '651', 'osdsubtitlesettings'), ('606', '652', 'osdaudiosettings')):
        assert right[button].findtext('onup').startswith('SetFocus({},'.format(panel))
        assert not _arg(right[button], 'onfocus')  # one watcher per OSD, not a script per focus
        call = next(c for c in parse(ROOT / '1080i' / 'VideoOSD.xml').iter('include')
                    if c.get('content') == 'TrackPanel' and _arg(c, 'id') == panel)
        assert _arg(call, 'button') == button and _arg(call, 'settings') == settings


def test_play_icon_is_classic():
    """Play labels use the plain triangle ▶, not the pointed ►."""
    for name in ('Variables.xml', 'Includes_Home.xml'):
        assert '►' not in (ROOT / '1080i' / name).read_text(encoding='utf-8'), name


def test_track_panel_slots_match_script():
    """The script caps the panel at PANEL_SLOTS rows; the layout needs a TrackItem for each."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('nightcity', ROOT / 'scripts' / 'nightcity.py')
    nightcity = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nightcity)
    panel = next(i for i in parse(ROOT / '1080i' / 'Includes_Player.xml').iter('include')
                 if i.get('name') == 'TrackPanel')
    assert len([i for i in panel.iter('include') if i.get('content') == 'TrackItem']) == nightcity.PANEL_SLOTS


def test_chapters_dialog_focuses_chapters():
    """The chapter row opens on the chapter list, add bookmark only without entries (focus hops
    93 and 94, test_tmdb_navigation.py)."""
    root = parse(ROOT / '1080i' / 'VideoOSDBookmarks.xml')
    assert root.findtext('defaultcontrol') == '93'


def test_osd_watches_tracks_once():
    """The OSD starts one script that keeps the panels current while it is open, and clears the
    rows when it closes, so the next file never shows the last file's tracks."""
    root = parse(ROOT / '1080i' / 'VideoOSD.xml')
    assert 'NotifyAll(nightcity,streams_watch)' in [o.text for o in root.iter('onload')]
    unload = [o.text for o in root.iter('onunload')]
    assert 'ClearProperty(nc.audio.rows,home)' in unload and 'ClearProperty(nc.sub.rows,home)' in unload


def test_player_resolution_suffix():
    """4K and 8K stay as they are, only numeric heights get a p."""
    values = {v.get('condition'): v.text for v in parse(ROOT / '1080i' / 'Variables.xml').iter('variable')
              if v.get('name') == 'PlayerResolution' for v in v.iter('value')}
    assert values['String.IsEqual(VideoPlayer.VideoResolution,8K)'] == '8K'
    assert values['Integer.IsGreater(VideoPlayer.VideoResolution,0)'] == '$INFO[VideoPlayer.VideoResolution]p'
    assert values[None] == '$INFO[VideoPlayer.VideoResolution]'


def test_windows_start_one_script_on_load():
    """Kodi (Python 3.12+) can crash when two interpreters start at the same moment: every window
    starts at most one script when it loads."""
    for path in sorted((ROOT / '1080i').glob('*.xml')):
        scripts = [o.text for o in parse(path).iter('onload') if 'RunScript' in (o.text or '')]
        assert len(scripts) <= 1, (path.name, scripts)


def test_home_covers_episode_return():
    """After a stop the script reopens the episode's info page; until it is up, Home shows only
    the backdrop (nc.returning, set by the script on the stop) instead of its content."""
    root = parse(ROOT / '1080i' / 'Home.xml')
    controls = root.find('controls')
    cover = list(controls)[-1]
    assert cover.findtext('visible') == '!String.IsEmpty(Window(Home).Property(nc.returning)) + !Player.HasVideo'
    info = parse(ROOT / '1080i' / 'DialogVideoInfo.xml')
    assert 'ClearProperty(nc.returning,home)' in [o.text for o in info.iter('onload')]
    script = (ROOT / 'scripts' / 'nightcity.py').read_text(encoding='utf-8')
    assert script.count("'nc.returning'") >= 3  # set while following, cleared when giving up


def _variable(name):
    var = next(v for v in parse(ROOT / '1080i' / 'Variables.xml').iter('variable') if v.get('name') == name)
    return [(v.get('condition'), v.text) for v in var.iter('value')]


def test_seekbar_shows_details():
    """With the seek line the player shows what plays: poster, kicker, title, short plot and badges
    for resolution, SDR/HDR and the audio format."""
    seekbar = parse(ROOT / '1080i' / 'DialogSeekBar.xml')
    assert 'PlayerDetails' in [i.get('content') or i.text for i in seekbar.iter('include')]
    details = next(i for i in parse(ROOT / '1080i' / 'Includes_Player.xml').iter('include')
                   if i.get('name') == 'PlayerDetails')
    text = ''.join(p.get('value') or '' for p in details.iter('param')) + ''.join(details.itertext())
    for part in ('$VAR[PlayerPoster]', '$VAR[PlayerKicker]', '$INFO[VideoPlayer.Title]', '$VAR[PlayerPlot]',
                 '$VAR[PlayerResolution]', '$VAR[PlayerHdr]', '$VAR[PlayerAudio]'):
        assert part in text, part


def test_player_hdr_badge():
    values = dict((c, t) for c, t in _variable('PlayerHdr'))
    assert values['String.IsEqual(VideoPlayer.HdrType,dolbyvision)'] == 'DV'
    assert values['String.IsEqual(VideoPlayer.HdrType,hdr10)'] == 'HDR10'
    assert values['String.IsEqual(VideoPlayer.HdrType,hlg)'] == 'HLG'
    assert _variable('PlayerHdr')[-1] == ('!String.IsEmpty(VideoPlayer.VideoResolution)', 'SDR')


def test_player_audio_badge():
    """Codec names as people know them, then the channel layout."""
    codecs = dict((c, t) for c, t in _variable('PlayerAudioCodec'))
    for codec, name in (('truehd', 'TrueHD'), ('eac3', 'DD+'), ('ac3', 'DD'), ('dtshd_ma', 'DTS-HD MA'),
                        ('dtshd_hra', 'DTS-HD HRA'), ('dca', 'DTS'), ('aac', 'AAC'), ('flac', 'FLAC')):
        assert codecs['String.IsEqual(VideoPlayer.AudioCodec,{})'.format(codec)] == name
    channels = dict((c, t) for c, t in _variable('PlayerAudioChannels'))
    assert channels['String.IsEqual(VideoPlayer.AudioChannels,6)'] == '5.1'
    assert channels['String.IsEqual(VideoPlayer.AudioChannels,8)'] == '7.1'
    assert channels['String.IsEqual(VideoPlayer.AudioChannels,2)'] == '2.0'
    assert _variable('PlayerAudio') == [(None, '$VAR[PlayerAudioCodec]$VAR[PlayerAudioChannels, ,]')]


def test_info_page_ends_the_claim():
    loads = [o.text for o in parse(ROOT / '1080i' / 'DialogVideoInfo.xml').iter('onload')]
    assert 'ClearProperty(nc.info.opening,home)' in loads


def test_confirm_buttons_fit_their_labels():
    """Kodi fills the yes/no/custom labels, e.g. "Save password" or "Sign in again": a fixed
    width cut them off and scrolled them as "again | Sign"."""
    root = parse(ROOT / '1080i' / 'DialogConfirm.xml')
    buttons = [c for c in root.iter('include') if c.get('content') == 'Button']
    assert [_arg(b, 'id') for b in buttons] == ['11', '10', '12']
    assert all(_arg(b, 'width') == 'auto' for b in buttons)


def test_confirm_hides_buttons_without_label():
    """A visible condition overrides Kodi hiding the custom button, so a yes/no dialog showed an
    empty third button. Each button shows only with a label."""
    root = parse(ROOT / '1080i' / 'DialogConfirm.xml')
    for b in (c for c in root.iter('include') if c.get('content') == 'Button'):
        assert _arg(b, 'visible') == '!String.IsEmpty(Control.GetLabel({}))'.format(_arg(b, 'id'))


def test_settings_level_button_cycles_the_level():
    """Kodi changes the settings level only on the SettingsLevelChange action, a plain click on
    button 20 did nothing."""
    root = parse(ROOT / '1080i' / 'SettingsCategory.xml')
    button = next(c for c in root.iter('include') if c.get('content') == 'ListButton' and _arg(c, 'id') == '20')
    assert _arg(button, 'onclick') == 'SettingsLevelChange'


def test_addon_browser_rows_match_the_settings_pages():
    """The add-on browser lists in the size of the settings rows, not in the smaller list font."""
    root = parse(ROOT / '1080i' / 'AddonBrowser.xml')
    listing = next(c for c in root.iter('include') if c.get('content') == 'DialogList')
    assert _arg(listing, 'font') == 'font_label'
    assert not [f for f in root.iter('font') if f.text == 'font_small']


def test_player_plot_shows_whole_lines():
    """140 px of font_body (38 px lines) showed the top half of a fourth line; three whole lines,
    the rest scrolls."""
    root = parse(ROOT / '1080i' / 'Includes_Player.xml')
    details = next(i for i in root.iter('include') if i.get('name') == 'PlayerDetails')
    plot = next(t for t in details.iter('control') if t.get('type') == 'textbox')
    assert int(plot.findtext('height')) == 116
    assert plot.findtext('autoscroll') == 'true'
