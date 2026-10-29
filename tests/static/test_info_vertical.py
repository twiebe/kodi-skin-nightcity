"""The info page is walked level by level with Up and Down, like the settings with Left and Right.

Down goes one row deeper and never wraps; Up goes one row back, and Up on the button row at the
top leaves the page one level up (Action(Back)): to the row it was opened from, or one page back
in a TMDb chain. An episode lists its own cast and crew (guest stars included) from TMDb Helper
below the episode list.
"""
from conftest import ROOT, parse

SKIN = ROOT / '1080i'
EPISODE = 'String.IsEqual(ListItem.DBType,episode)'
FOCUSED_EP = 'Container(5100).ListItem.DBID'


def _root():
    return parse(SKIN / 'DialogVideoInfo.xml')


def _control(cid, root=None):
    found = (root if root is not None else _root()).find('.//control[@id="{}"]'.format(cid))
    assert found is not None, cid
    return found


def _nav(cid, direction):
    return [(e.get('condition') or '', (e.text or '').strip()) for e in _control(cid).findall(direction)]


def _values(name):
    var = next(v for v in parse(SKIN / 'Variables.xml').iter('variable') if v.get('name') == name)
    return [(v.get('condition') or '', v.text or '') for v in var.findall('value')]


def _timer(name):
    return next(t for t in parse(SKIN / 'Timers.xml').iter('timer') if t.findtext('name') == name)


def _onloads():
    return [o.text or '' for o in _root().iter('onload')]


def test_up_on_the_button_row_goes_back():
    """The button row is the top of every info page (library, TMDb title, person)."""
    assert _nav(9000, 'onup') == [('', 'Action(Back)')]


def test_episode_rows_scroll_with_the_credits():
    """Season tabs and episodes are the first row of the vertical grouplist 5400, the cast and
    crew row comes below them, one row on screen at a time like on a movie."""
    rows = _control(5400)
    assert rows.findtext('orientation') == 'vertical'
    assert 'String.IsEqual(ListItem.DBType,episode)' not in (rows.findtext('visible') or '')
    first = rows.findall('control')[0]
    assert first.findtext('visible') == EPISODE
    for cid in ('5200', '5100'):
        assert first.find('.//control[@id="{}"]'.format(cid)) is not None, cid


def test_down_from_the_episodes_opens_their_credits():
    assert _nav(5100, 'ondown') == [
        # only into credits of this episode (test_rows_focus.py)
        ('$EXP[TmdbFresh5500] + !Container(5500).IsUpdating + Integer.IsGreater(Container(5500).NumItems,0)', '5500'),
        # the tabs while the list loads, shows the episode before or the chosen tab has nothing
        ('Control.IsVisible(5403)', '5520'),
        ('Control.IsVisible(50)', '50'),
        ('', 'noop'),
    ]


def test_up_from_the_credits_returns_to_the_episodes():
    for cid in ('5520', '50'):
        nav = _nav(cid, 'onup')
        # Kodi's own cast can sit below an empty tab row: up to the tabs first
        if cid == '50':
            assert nav.pop(0) == ('Control.IsVisible(5403)', '5520')
        assert nav[0] == (EPISODE, '5100'), cid
        assert nav[-1] == ('', '9000'), cid
    # a list goes up to the tab it shows, not to the tab focused last time
    tab = 'String.IsEqual(Window(Home).Property(nc.info.tab),{})'
    assert _nav(5500, 'onup') == [(tab.format('crew'), '5522'), ('', '5521')]
    assert _nav(5510, 'onup') == [(tab.format('tv'), '5524'), (tab.format('crew'), '5525'), ('', '5523')]
    assert _nav(5200, 'onup') == [('', '9000')]
    assert _nav(5100, 'onup') == [('', '5200')]


def test_episode_credits_path():
    """Cast (with guest stars) or crew of the episode from TMDb Helper, the show found by its
    title like the OSD cast row does. Only once nc.info.ep.query names season and episode."""
    values = [(c, t) for c, t in _values('InfoPeoplePath') if c.startswith(EPISODE)]
    assert len(values) == 2
    ready = '!String.IsEmpty(Window(Home).Property(nc.info.ep.query))'
    for cond, text in values:
        assert ready in cond, cond
        assert text.startswith('plugin://plugin.video.themoviedb.helper/?info=')
        assert '&tmdb_type=tv&query=$INFO[ListItem.TVShowTitle]&$INFO[Window(Home).Property(nc.info.ep.query)]' in text
        assert text.endswith('&nextpage=false&cacheonly=true')
    assert 'String.IsEqual(Window(Home).Property(nc.info.tab),crew)' in values[0][0]
    assert 'info=crew&' in values[0][1] and 'info=cast&' in values[1][1]


def test_episode_credits_load_once_the_focus_rested():
    """Moving along the episode list starts no plugin: the credits follow the selected episode
    a second after it stopped changing, once info_select is done and no list loads."""
    timer = _timer('nc_info_ep')
    start = timer.findtext('start')
    assert timer.find('start').get('reset') == 'true'
    for part in ('Window.IsActive(movieinformation)', EPISODE,
                 '!String.IsEmpty(Window(Home).Property(nc.info.ready))',
                 '!String.IsEmpty({})'.format(FOCUSED_EP),
                 '!String.IsEqual(Window(Home).Property(nc.info.ep.id),{})'.format(FOCUSED_EP)):
        assert part in start, part
    assert [o.text for o in timer.findall('onstart')] == ['SetProperty(nc.info.ep.pending,$INFO[{}],home)'.format(FOCUSED_EP)]
    stop = timer.findtext('stop')
    assert '!String.IsEqual(Window(Home).Property(nc.info.ep.pending),{})'.format(FOCUSED_EP) in stop
    assert 'Integer.IsGreaterOrEqual(Skin.TimerElapsedSecs(nc_info_ep),1) + !Container(5500).IsUpdating' in stop
    onstops = [(o.get('condition') or '', o.text) for o in timer.findall('onstop')]
    same = 'Window.IsActive(movieinformation) + String.IsEqual(Window(Home).Property(nc.info.ep.pending),{})'.format(FOCUSED_EP)
    assert onstops == [
        (same, 'SetProperty(nc.info.ep.query,season=$INFO[Container(5100).ListItem.Season]&episode=$INFO[Container(5100).ListItem.Episode],home)'),
        (same, 'SetProperty(nc.info.ep.id,$INFO[Window(Home).Property(nc.info.ep.pending)],home)'),
    ]
    onloads = _onloads()
    for name in ('query', 'id', 'pending'):
        assert 'ClearProperty(nc.info.ep.{},home)'.format(name) in onloads, name


def test_episode_credits_row_shows_while_it_can_load():
    """A hidden list does not update: the credits row stays visible on an episode page once the
    path is set, so the list sees it change."""
    visible = _control(5403).findtext('visible')
    assert '[{} + !String.IsEmpty(Window(Home).Property(nc.info.ep.query))]'.format(EPISODE) in visible


def test_kodi_cast_of_an_episode_only_for_the_opened_one():
    """Kodi fills list 50 with the cast of the episode the page was opened for: shown only when
    TMDb has none for it and that episode is selected."""
    visible = _control(5401).findtext('visible')
    assert '[!{} | [String.IsEqual({},ListItem.DBID) + String.IsEqual(Window(Home).Property(nc.info.ep.id),{})]]'.format(
        EPISODE, FOCUSED_EP, FOCUSED_EP) in visible


def test_episode_person_click_returns_to_the_selected_episode():
    """The chain's origin for an episode page is the episode the credits row shows, not the one
    the page opened with: Back from the person page shows the episode whose cast was clicked.
    Not Container(5100).ListItem.DBID: in a list's onclick that reads the clicked item."""
    assert _values('ChainOriginDBID') == [
        ('String.IsEqual(Window(Home).Property(nc.chain.origin.type),episode) + !String.IsEmpty(Window(Home).Property(nc.info.ep.id))',
         '$INFO[Window(Home).Property(nc.info.ep.id)]'),
        ('', '$INFO[Window(Home).Property(nc.chain.origin.dbid)]'),
    ]
    for cid in ('5500', '5510', '5300'):
        call = next(c for c in _control(cid).iter('include') if c.get('content') == 'ChainClick')
        origin = next(p.get('value') for p in call.findall('param') if p.get('name') == 'origin')
        assert 'origin_dbid=$VAR[ChainOriginDBID]' in origin, cid


def test_episode_hint_names_the_cast_row():
    hint = next(c for c in _root().iter('control') if '$LOCALIZE[31135]' in (c.findtext('label') or ''))
    assert '↓ $LOCALIZE[31124]' in hint.findtext('label')


def test_down_from_the_buttons_skips_the_season_tabs():
    """Like the cast and crew tabs: down lands on the episodes, the season tabs above them are
    reached with up from there."""
    assert _nav(9000, 'ondown')[0] == ('String.IsEqual(ListItem.DBType,episode)', '5100')
