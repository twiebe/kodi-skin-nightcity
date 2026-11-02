"""The next episode prompt (Custom_1151_NextEpisode.xml): in an episode's last seconds, while
another follows in the playlist, a button comes up over the video with the focus, without the
OSD. OK plays the next episode, Back hides it for this episode."""
from conftest import ROOT, parse

SKIN = ROOT / '1080i'
WINDOW = 'Custom_1151_NextEpisode.xml'
SHOWN = 'nc.next.hide'


def _root():
    return parse(SKIN / WINDOW)


def _button():
    """The PillButton include of the prompt: its params, and the include for its nested actions."""
    inc = next(i for i in _root().iter('include') if any(p.get('value') == '1152' for p in i.findall('param')))
    return {p.get('name'): p.get('value') for p in inc.findall('param')}, inc


def _actions(control, tag):
    return [(o.get('condition') or '', o.text) for o in control.findall(tag)]


def test_prompt_is_a_modal_dialog_kodi_opens_by_its_condition():
    """Kodi opens a custom dialog with a visible condition by itself; only a modal one gets the
    keys (CGUIWindowManager::HandleAction), a modeless one leaves them to the video."""
    root = _root()
    assert (root.get('type'), root.get('id'), root.get('modality')) == ('dialog', '1151', 'modal')
    assert root.findtext('defaultcontrol') == '1152'


def test_prompt_shows_in_the_last_seconds_before_a_next_episode():
    visible = _root().findtext('visible')
    for condition in ('Window.IsActive(fullscreenvideo)', '!Window.IsActive(videoosd)',
                      'VideoPlayer.Content(episodes)',
                      'Integer.IsLess(VideoPlayer.PlaylistPosition,VideoPlayer.PlaylistLength)',
                      'Integer.IsLess(Player.TimeRemaining(secs),31)',
                      '!String.IsEqual(Window(Home).Property({}),Player.FilenameAndPath)'.format(SHOWN)):
        assert condition in visible, condition


def test_prompt_keys():
    """OK plays the next playlist item (PlayerControl(Next) would only move on a chapter), Back
    hides the prompt for this file, Left and Right seek as over the video."""
    params, button = _button()
    assert button.text == 'PillButton' or button.get('content') == 'PillButton'
    assert params['onclick'] == 'Playlist.PlayOffset(video,1)' and button.find('onclick') is None
    assert _actions(button, 'onback') == [('', 'SetProperty({},$ESCINFO[Player.FilenameAndPath],home)'.format(SHOWN))]
    assert _actions(button, 'onleft') == [('', 'Seek(-10)')]
    assert _actions(button, 'onright') == [('', 'Seek(10)')]
    assert _actions(button, 'onup') == [('', 'noop')] and _actions(button, 'ondown') == [('', 'noop')]
    assert '$LOCALIZE[31137]' in params['label']
    assert 'Player.TimeRemaining(secs)' in params['label']


def test_osd_has_no_next_episode_pill_any_more():
    """The prompt replaces it; the OSD's ⏭ plays on to the next chapter or item."""
    osd = (SKIN / 'VideoOSD.xml').read_text(encoding='utf-8')
    assert '31137' not in osd
