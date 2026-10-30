"""Music (docs/music-design.md): the Music page of Home, the album and artist page, the library,
the player screen and its OSD. Navigation and dead ends of the new windows are covered by
test_navigation.py like every window; here the music specific rules."""
import re
import xml.etree.ElementTree as ET

from conftest import ROOT, parse
from focus import Page, State
from navigation import dead_ends, load, unreachable

PAGE = 'String.IsEqual(Window(Home).Property(nc.page),music)'
SHOWN = '!Skin.HasSetting(nc.menu.hide.music) + Library.HasContent(music)'


def controls(root):
    return {c.get('id'): c for c in root.iter('control') if c.get('id')}


def actions(el, tag='onclick'):
    return [(a.get('condition') or '', (a.text or '').strip()) for a in el.findall(tag)]


def strings():
    text = (ROOT / 'language' / 'resource.language.en_gb' / 'strings.po').read_text(encoding='utf-8')
    return dict((int(i), t) for i, t in re.findall(r'msgctxt "#(\d+)"\nmsgid "([^"]*)"', text))


# --- Music page on Home ----------------------------------------------------------------------

def test_music_tab_between_shows_and_search():
    menu = controls(load('Home.xml'))['9100']
    ids = [c.get('id') for c in menu.findall('control')]
    assert ids.index('9103') < ids.index('9107') < ids.index('9104')


def test_music_tab_only_with_music_and_hideable():
    c = controls(load('Home.xml'))
    assert c['9107'].findtext('visible') == SHOWN
    assert c['9119'].findtext('visible') == SHOWN  # its gap goes with it
    home = parse(ROOT / '1080i' / 'Home.xml')
    loads = [(o.get('condition') or '', o.text) for o in home.findall('onload')]
    assert ('{} + [Skin.HasSetting(nc.menu.hide.music) | !Library.HasContent(music)]'.format(PAGE),
            'SetProperty(nc.page,home,home)') in loads


def test_music_tab_switches_the_page_on_focus():
    """DESIGN.md: focus applies. The album spotlight stays where it is
    (tests/static/test_spotlight_switch.py)."""
    tab = controls(load('Home.xml'))['9107']
    assert actions(tab, 'onfocus') == [('', 'SetProperty(nc.page,music,home)')]


def test_settings_switch_for_the_music_entry():
    c = controls(load('SkinSettings.xml'))
    assert c['516'].findtext('onclick') == 'Skin.ToggleSetting(nc.menu.hide.music)'
    assert c['516'].findtext('selected') == '!Skin.HasSetting(nc.menu.hide.music)'
    menu = [k.get('id') for k in c['500'].findall('control')]
    assert menu.index('512') < menu.index('516') < menu.index('513')  # in the order of the menu


def _home_state(focus_page='music', **extra):
    hidden = {'Skin.HasSetting(nc.menu.hide.{})'.format(n): False for n in ('movies', 'shows', 'music', 'search')}
    hidden['Library.HasContent(music)'] = True
    hidden['Player.HasAudio'] = False
    for name in ('SpotlightSource', 'nc.movies.spotlight', 'nc.shows.spotlight'):
        hidden['String.IsEqual(Skin.String({}),off)'.format(name)] = False
    hidden.update(extra)
    return State(props={'nc.page': focus_page}, extra=hidden,
                 containers={'9002': 'items', '9801': 'items', '9822': 'items', '9803': 'items',
                             '9804': 'items', '9805': 'items'})


def test_music_page_walks_down_and_up():
    """Tab, Down: the spotlight buttons (play first); Down: the rows; Up: the buttons; Up: the
    menu."""
    page = Page('Home.xml')
    state = _home_state()
    assert page.move('9107', 'ondown', state)[0] == '9852'
    assert page.move('9852', 'ondown', state)[0] == '9801'
    assert page.move('9801', 'onup', state)[0] == '9852'
    # up to the menu, where Kodi focuses the tab the menu had last (the music tab)
    assert controls(load('Home.xml'))['9850'].findtext('onup') == '9100'


def test_music_spotlight_steps_at_the_ends():
    """Left on the first button: the album before; right on the last: the next one."""
    group = controls(load('Home.xml'))['9850']
    assert actions(group, 'onleft') == [('', 'Skin.TimerStart(nc_spot_hold)'), ('', 'Control.Move(9002,-1)')]
    assert actions(group, 'onright') == [('', 'Skin.TimerStart(nc_spot_hold)'), ('', 'Control.Move(9002,1)')]
    # as the remote sees it: the arrow after the last button takes no focus and passes Right on
    page, state = Page('Home.xml'), _home_state()
    assert page.move('9852', 'onleft', state) == (None, ['Skin.TimerStart(nc_spot_hold)', 'Control.Move(9002,-1)'])
    assert page.move('9854', 'onright', state) == (None, ['Skin.TimerStart(nc_spot_hold)', 'Control.Move(9002,1)'])


def test_music_spotlight_buttons():
    c = controls(load('Home.xml'))
    assert '9851' not in c  # what plays is in the top line (9108)
    # play goes to the player screen (scripts/nightcity.py music_play); Back there comes back
    assert c['9852'].findall('onclick')[0].text == \
        'NotifyAll(nightcity,music_play:album:$INFO[Container(9002).ListItem.DBID]:1)'
    assert [a.text for a in c['9853'].findall('onclick')][:2] == ['SetFocus(9002)', 'Action(Info)']
    assert c['9854'].findall('onclick')[0].text == 'ActivateWindow(Music,musicdb://albums/,return)'
    spot = c['9002']
    assert spot.find('content').get('target') == 'music'
    assert spot.findtext('content') == 'special://skin/playlists/MusicSpotlight.xsp'


def test_music_rows():
    c = controls(load('Home.xml'))
    rows = [(k.get('id'), controls(k)) for k in c['9810'].findall('control')]
    paths = []
    for group, inner in rows:
        lists = [x for x in inner.values() if x.get('type') == 'list']
        assert len(lists) == 1, group
        content = lists[0].find('content')
        assert content.get('target') == 'music', group
        paths.append(content.text)
    assert paths == ['musicdb://recentlyaddedalbums/', 'musicdb://recentlyplayedalbums/',
                     'special://skin/playlists/MusicRandomAlbums.xsp', 'musicdb://artists/', 'musicdb://genres/']


def test_music_cards_open_info_or_the_library():
    """DESIGN.md: OK goes. Albums and artists open their page, a genre the library on it."""
    c = controls(load('Home.xml'))
    clicks = actions(c['9801'])
    assert ('String.IsEqual(ListItem.DBType,album) | String.IsEqual(ListItem.DBType,artist)', 'Action(Info)') in clicks
    assert ('String.IsEqual(ListItem.DBType,genre)', 'ActivateWindow(Music,$INFO[ListItem.FolderPath],return)') in clicks


def test_music_playlists():
    spot = parse(ROOT / 'playlists' / 'MusicSpotlight.xsp')
    assert spot.get('type') == 'albums' and spot.findtext('order') == 'random' and spot.find('limit') is None
    rnd = parse(ROOT / 'playlists' / 'MusicRandomAlbums.xsp')
    assert rnd.get('type') == 'albums' and rnd.findtext('order') == 'random'


def test_now_playing_in_the_top_line():
    """What plays, a button of the top line while music plays: OK opens the player screen."""
    c = controls(load('Home.xml'))
    button = c['9108']
    assert button.findtext('visible') == 'Player.HasAudio'
    assert [a.text for a in button.findall('onclick')] == ['ActivateWindow(visualisation)']
    assert button.findtext('label') == '$VAR[MusicNowPlayingLabel]'
    assert c['9190'].findall('control')[0] is button  # left of the quick menu icon
    # Down goes into the shown page, like the menu
    assert actions(button, 'ondown') == actions(c['9100'], 'ondown')


def test_now_playing_between_menu_and_icon():
    """Right from the menu, Left from the icon; without music both skip it."""
    page = Page('Home.xml')
    playing = _home_state('home', **{'Player.HasAudio': True})
    assert page.move('9104', 'onright', playing)[0] == '9108'
    assert page.move('9109', 'onleft', playing)[0] == '9108'
    silent = _home_state('home')
    assert page.move('9104', 'onright', silent)[0] == '9109'
    assert page.move('9109', 'onleft', silent)[0] == '9104'


def test_now_playing_gone_moves_the_focus():
    """No dead end when the music stops with the focus on it: Home without a focus goes to the
    page's own tab, and the quick menu's way back to it (nc.quick.from) goes too."""
    timers = {t.findtext('name'): t for t in parse(ROOT / '1080i' / 'Timers.xml').iter('timer')}
    timer = timers['nc_np_gone']
    start = timer.findtext('start')
    for part in ('!Player.HasAudio', 'String.IsEmpty(System.CurrentControlId)',
                 'String.IsEqual(Window(Home).Property(nc.quick.from),9108)'):
        assert part in start
    assert 'nc.np.gone' in start
    assert [o.text for o in timer.findall('onstop')] == ['ClearProperty(nc.quick.from,home)', 'SetFocus(9189)',
                                                         'ClearProperty(nc.np.gone,home)']
    c = controls(load('Home.xml'))
    # Right goes to the icon's group (the grouplist's neighbour); Back there comes back
    assert c['9190'].findall('control')[1].get('id') == '9199'
    assert actions(c['9108'], 'onunfocus') == [('', 'SetProperty(nc.quick.from,9108,home)'),
                                               ('!Player.HasAudio', 'SetProperty(nc.np.gone,1,home)')]


def test_player_screen_back_reopens_the_page():
    window = parse(ROOT / '1080i' / 'MusicVisualisation.xml')
    assert [o.text for o in window.findall('onunload')] == ['NotifyAll(nightcity,music_back)']


def test_music_page_navigation_without_dead_ends():
    for skin in ({}, {'nc.menu.hide.music': True}):
        assert dead_ends('Home.xml', skin) == []


# --- album, artist and song page -------------------------------------------------------------

ARTIST = 'String.IsEqual(ListItem.DBType,artist)'


def test_music_info_buttons_click_kodis_hidden_ones():
    """Kodi labels its buttons 8 and 12 itself: they stay hidden, the pills click them."""
    c = controls(load('DialogMusicInfo.xml'))
    for kodi in ('8', '12'):
        assert c[kodi].findtext('visible') == 'false' and c[kodi].findtext('enable') == 'false'
    assert ('String.IsEqual(ListItem.DBType,song)', 'SendClick(8)') in actions(c['9001'])
    # an album plays through the script: it opens the player screen, Back comes back here
    assert ('String.IsEqual(ListItem.DBType,album)', 'NotifyAll(nightcity,music_play:album:$INFO[ListItem.DBID]:1)') \
        in actions(c['9001'])
    assert (ARTIST, 'NotifyAll(nightcity,music_play:artist:$INFO[ListItem.DBID]:1)') in actions(c['9001'])
    assert ('', 'SendClick(12)') in actions(c['9002'])


def test_music_info_up_leaves_down_goes_to_the_rows():
    c = controls(load('DialogMusicInfo.xml'))
    assert actions(c['9000'], 'onup') == [('', 'Action(Back)')]
    assert actions(c['9000'], 'ondown') == [('Control.IsVisible(5410)', '5050'), ('!Control.IsVisible(5410)', '5301')]
    # only an album has tracks; never hidden by its own list: Kodi fills no hidden list
    assert c['5410'].findtext('visible') == 'String.IsEqual(ListItem.DBType,album)'


def test_music_info_track_plays_the_album_from_there():
    """The tracks come from the library (5050): Kodi's own list 50 runs no onclick."""
    c = controls(load('DialogMusicInfo.xml'))
    assert '50' not in c
    assert c['5050'].find('content').text == '$VAR[MusicInfoTracksPath]'
    [(condition, click)] = actions(c['5050'])
    assert 'String.IsEqual(Container(5050).ListItem.DBType,song)' in condition
    assert click == ('NotifyAll(nightcity,music_play:album:$INFO[Window(Home).Property(nc.music.album)]'
                     ':$INFO[Container(5050).CurrentItem])')


def test_music_info_cards_open_their_page():
    c = controls(load('DialogMusicInfo.xml'))
    assert actions(c['5301']) == [('', 'NotifyAll(nightcity,music_info:$INFO[ListItem.DBType]:$INFO[ListItem.DBID])')]
    content = c['5301'].find('content')
    assert content.text == '$VAR[MusicInfoMorePath]' and content.get('target') == 'music'


def test_music_info_more_path():
    """An artist: its albums by id. An album: the other albums of its artist, by name (Kodi has no
    artist id on an album item); the title comes from the tags, a script-opened page has no label."""
    variables = {v.get('name'): v for v in parse(ROOT / '1080i' / 'Variables.xml').iter('variable')}
    values = [(v.get('condition'), v.text) for v in variables['MusicInfoMorePath'].findall('value')]
    assert values[0] == (ARTIST + ' + !String.IsEmpty(ListItem.DBID)', 'musicdb://albums/?artistid=$INFO[ListItem.DBID]')
    assert '"isnot","value":["$VAR[MusicInfoTitle]"]' in values[1][1]
    title = [(v.get('condition'), v.text) for v in variables['MusicInfoTitle'].findall('value')]
    assert ('String.IsEqual(ListItem.DBType,album) + !String.IsEmpty(ListItem.Album)', '$INFO[ListItem.Album]') in title


def test_music_info_without_dead_ends():
    assert dead_ends('DialogMusicInfo.xml', {}) == []


# --- library, player screen and OSD ----------------------------------------------------------

def test_music_library_views():
    window = parse(ROOT / '1080i' / 'MyMusicNav.xml')
    assert window.findtext('views') == '50,51'
    c = controls(load('MyMusicNav.xml'))
    assert 'ui/mask_200x200.png' in ET.tostring(c['51']).decode()  # square music cards
    assert {'2', '3', '4'} <= set(c)  # view, sort by, descending


def test_player_screen_makes_room_for_the_osd():
    """What plays moves down while the OSD is closed; the next track and the OK hint go with it."""
    c = controls(load('MusicVisualisation.xml'))
    slide = c['9100'].find('animation')
    assert slide.get('condition') == '!Window.IsActive(musicosd)' and slide.get('end') == '0,240'
    assert c['2'].get('type') == 'visualisation' and c['2'].findtext('visible') == 'Visualisation.Enabled'


def test_music_osd_buttons_and_queue():
    c = controls(load('MusicOSD.xml'))
    assert parse(ROOT / '1080i' / 'MusicOSD.xml').findtext('defaultcontrol') == '602'
    assert [k.get('id') for k in c['600'].findall('control')] == ['601', '602', '603', '604']
    # the order of the video player: previous, play/pause, stop, next
    assert [actions(k)[0][1] for k in c['600'].findall('control')] == [
        'PlayerControl(Previous)', 'PlayerControl(Play)', 'PlayerControl(Stop)', 'PlayerControl(Next)']
    assert [k.get('id') for k in c['620'].findall('control')] == ['621', '622']
    assert ('', 'PlayerControl(Random)') in actions(c['621'])
    assert ('', 'PlayerControl(Repeat)') in actions(c['622'])
    # Down: the queue, the cursor already on the playing track (music_queue_select, onload)
    for group in ('600', '620'):
        assert actions(c[group], 'ondown') == [('Control.IsVisible(701)', '701'), ('Control.IsVisible(700)', '700'),
                                                ('', 'noop')]
        assert actions(c[group], 'onup') == [('', 'noop')]
    window = parse(ROOT / '1080i' / 'MusicOSD.xml')
    assert 'NotifyAll(nightcity,music_queue_select)' in [o.text for o in window.findall('onload')]
    # one album: lines (701); else cards (700); only the shown list loads
    one = 'String.IsEmpty(Window(Home).Property(nc.music.queue.album))'
    assert c['700'].findtext('visible') == one and c['701'].findtext('visible') == '!' + one
    for list_id in ('700', '701'):
        assert c[list_id].findtext('content') == 'playlistmusic://'
        assert actions(c[list_id]) == [
            ('', 'NotifyAll(nightcity,music_goto:$INFO[Container({}).CurrentItem])'.format(list_id))]
        assert actions(c[list_id], 'onup') == [('', '600')]


def test_music_queue_marks_the_playing_track():
    """The cursor, which opens on the playing track, shows its title in the accent colour also
    while the list has no focus. The playing track keeps a dark blue mark (state, DESIGN.md
    colours) wherever the cursor is: in the track list a bar before its number, like the current
    value of a list dialog; on a card a line under its title, a bar would get lost by the cover.
    No progress line: Kodi redraws a list item only while the cursor is on it, so the line stood
    still elsewhere."""
    c = controls(load('MusicOSD.xml'))
    for list_id in ('700', '701'):
        for layout in ('itemlayout', 'focusedlayout'):
            controls_in = list(c[list_id].find(layout).iter('control'))
            assert not [p for p in controls_in if p.get('type') == 'progress']
            bars = [i for i in controls_in if i.get('type') == 'image'
                    and (i.findtext('visible') or '').strip() == 'ListItem.IsPlaying']
            assert len(bars) == 1, (list_id, layout)
            width, height = int(bars[0].findtext('width')), int(bars[0].findtext('height'))
            if list_id == '701':
                assert width == 3 and height > width  # the bar before the number
            else:
                assert height == 3 and width > height  # the line under the title
            assert bars[0].find('texture').get('colordiffuse') == 'state'
            assert bars[0].findtext('texture') == 'ui/white.png'
        text = ET.tostring(c[list_id]).decode()
        assert '▶' not in text and 'accent2' not in text
    focused = ET.tostring(c['700'].find('focusedlayout')).decode()
    assert '<textcolor>accent</textcolor>' in focused  # the cursor's title


def test_music_osd_hides_like_the_video_osd():
    timers = {t.findtext('name'): t for t in parse(ROOT / '1080i' / 'Timers.xml').iter('timer')}
    timer = timers['nc_musicosd_hide']
    for part in ('!Skin.HasSetting(nc.osd.autohide.off)', 'Player.HasAudio', 'Window.IsModalDialogTopmost(musicosd)'):
        assert part in timer.findtext('start')
    assert timer.findtext('reset') == timers['nc_osd_hide'].findtext('reset')
    assert 'Skin.String(nc.osd.hide.wait)' in timer.findtext('stop')
    assert [o.text for o in timer.findall('onstop')] == ['Dialog.Close(musicosd)']


def test_music_windows_without_dead_ends():
    for name in ('MyMusicNav.xml', 'MusicOSD.xml'):
        assert dead_ends(name, {}) == []


def test_music_strings_without_long_dashes():
    for i, text in strings().items():
        if i >= 31400:
            assert '—' not in text and '–' not in text, i
