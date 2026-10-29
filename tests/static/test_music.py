"""Music (docs/music-design.md): the Music page of Home, the album and artist page, the library,
the player screen and its OSD. Navigation and dead ends of the new windows are covered by
test_navigation.py like every window; here the music specific rules."""
import re

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
    """DESIGN.md: focus applies. A switch to the page moves the album spotlight on by one."""
    tab = controls(load('Home.xml'))['9107']
    assert ('', 'SetProperty(nc.page,music,home)') in actions(tab, 'onfocus')
    assert ('!' + PAGE, 'Control.Move(9002,1)') in actions(tab, 'onfocus')
    assert ('!' + PAGE, 'Skin.TimerStart(nc_spot_hold)') in actions(tab, 'onfocus')


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


def test_music_spotlight_buttons():
    c = controls(load('Home.xml'))
    assert c['9851'].findtext('visible') == 'Player.HasAudio'  # now playing, first while music plays
    assert c['9851'].findtext('onclick') == 'ActivateWindow(visualisation)'
    assert c['9852'].findall('onclick')[0].text == 'PlayMedia(musicdb://albums/$INFO[Container(9002).ListItem.DBID]/,isdir)'
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
    labels = [c for c in load('Home.xml').iter('control') if c.findtext('visible') == 'Player.HasAudio'
              and c.get('type') == 'label']
    assert len(labels) == 1
    assert 'MusicPlayer.Title' in labels[0].findtext('label')


def test_music_page_navigation_without_dead_ends():
    for skin in ({}, {'nc.menu.hide.music': True}):
        assert dead_ends('Home.xml', skin) == []


def test_music_strings_without_long_dashes():
    for i, text in strings().items():
        if i >= 31400:
            assert '—' not in text and '–' not in text, i
