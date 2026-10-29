"""Endless TMDb navigation: info pages chained through TMDb Helper's window manager.

TMDb Helper keeps a stack of info pages (RunScript(plugin.video.themoviedb.helper,add_tmdb=...,
call_auto=1190)). The first call becomes a long running loop; while it runs the skin pushes the
next page by setting Window(Home).Property(TMDbHelper.Path.To.Add), which starts no Python at all.
"""
import re

from conftest import ROOT, parse

SKIN = ROOT / '1080i'
RUNNING = '!String.IsEmpty(Window(Home).Property(TMDbHelper.Instance))'
IDLE = 'String.IsEmpty(Window(Home).Property(TMDbHelper.Instance))'
ADD_PATH = 'SetProperty(TMDbHelper.Path.To.Add,plugin://plugin.video.themoviedb.helper/?info=details&tmdb_type='


def _onloads(name):
    return [o.text or '' for o in parse(SKIN / name).iter('onload')]


def _timer(name):
    return next(t for t in parse(SKIN / 'Timers.xml').iter('timer') if t.findtext('name') == name)


def _include(name):
    for path in SKIN.glob('Includes*.xml'):
        for el in parse(path).iter('include'):
            if el.get('name') == name:
                return el
    raise AssertionError(name)


def test_base_window_for_the_manager():
    """Window 1190 is the manager's base window. In direct mode the manager opens every info page
    itself, so 1190 is only a backdrop and starts nothing."""
    root = parse(SKIN / 'Custom_1190_TMDbHelper.xml')
    assert root.get('id') == '1190' and root.get('type') == 'window'
    assert not any('RunScript' in t for t in _onloads('Custom_1190_TMDbHelper.xml'))


def test_direct_call_auto_switched_on():
    """Without TMDbHelper.DirectCallAuto the manager wants a list 9999 in 1190 and clicks it."""
    for name in ('Startup.xml', 'Home.xml'):
        assert any('Skin.SetBool(TMDbHelper.DirectCallAuto)' in t for t in _onloads(name)), name


def test_chain_click_pushes_without_python_while_the_chain_runs():
    """In a running chain a click only sets the manager's mailbox; outside one it starts the
    manager, once: nc.chain.claim stops a second click from starting a second interpreter."""
    clicks = [(o.get('condition') or '', o.text or '') for o in _include('ChainClick').iter('onclick')]
    inside = [text for cond, text in clicks if cond.startswith(RUNNING)]
    outside = [text for cond, text in clicks if cond.startswith(IDLE)]
    assert inside == [ADD_PATH + '$PARAM[type]&tmdb_id=$PARAM[id],home)']
    assert any(t.startswith('RunScript(plugin.video.themoviedb.helper,add_tmdb=$PARAM[id],tmdb_type=$PARAM[type],call_auto=1190')
               for t in outside)
    claim = 'String.IsEmpty(Window(Home).Property(nc.chain.claim))'
    assert all(claim in cond for cond, text in clicks if cond.startswith(IDLE))
    assert any(text == 'SetProperty(nc.chain.claim,1,home)' for _, text in clicks)


def test_chain_claim_times_out():
    """The claim clears itself after a few seconds, also when the manager failed to start, and
    as soon as the manager runs: a chain left within those seconds used to ignore the next click."""
    timer = _timer('nc_chain_claim')
    assert timer.findtext('start') == '!String.IsEmpty(Window(Home).Property(nc.chain.claim))'
    stop = timer.findtext('stop')
    assert re.search(r'Skin\.TimerElapsedSecs\(nc_chain_claim\),\d\)', stop)
    assert stop.startswith(RUNNING + ' | ')
    assert timer.findtext('onstop') == 'ClearProperty(nc.chain.claim,home)'


PERSON = 'String.IsEqual(ListItem.Property(tmdb_type),person)'


def _info_control(cid):
    found = parse(SKIN / 'DialogVideoInfo.xml').find('.//control[@id="{}"]'.format(cid))
    assert found is not None, cid
    return found


def _chain_calls(element):
    return [{p.get('name'): p.get('value') for p in c.findall('param')}
            for c in element.iter('include') if c.get('content') == 'ChainClick']


def _variables():
    return {v.get('name'): v for v in parse(SKIN / 'Variables.xml').iter('variable')}


def _values(name):
    return [(v.get('condition') or '', v.text or '') for v in _variables()[name].findall('value')]


def test_info_rows_open_pages_in_the_chain():
    """Cast and crew of a title, a person's films, shows and crew jobs, similar movies: every
    click opens the item's full info page in the chain, no overlay. A click on the page's own
    list knows the page only through nc.chain.origin.*, set on load (ListItem in a list's
    onclick is the clicked item)."""
    for cid, kind in (('5500', 'person'), ('5510', '$INFO[ListItem.Property(tmdb_type)]'),
                      ('5300', 'movie')):
        calls = _chain_calls(_info_control(cid))
        assert len(calls) == 1, cid
        assert calls[0]['type'] == kind and calls[0]['id'] == '$INFO[ListItem.Property(tmdb_id)]', cid
        assert 'Window(Home).Property(nc.chain.origin.' in calls[0]['origin'], cid
        # an onclick that always holds: without one Kodi runs the item's plugin path instead
        assert 'noop' in [o.text for o in _info_control(cid).findall('onclick')], cid
    onloads = _onloads('DialogVideoInfo.xml')
    for key in ('type', 'id', 'dbid'):
        assert any(t.startswith('SetProperty(nc.chain.origin.{},'.format(key)) for t in onloads), key


def test_info_tabs_load_one_list():
    """A title page shows cast or crew, a person page films, shows or crew jobs: one TMDb list
    per page, its tab nc.info.tab (reset on load)."""
    assert 'ClearProperty(nc.info.tab,home)' in _onloads('DialogVideoInfo.xml')
    assert _info_control('5500').findtext('content') == '$VAR[InfoPeoplePath]'
    assert _info_control('5510').findtext('content') == '$VAR[InfoPersonCreditsPath]'
    tabs = [c for c in parse(SKIN / 'DialogVideoInfo.xml').iter('include') if c.get('content') == 'CreditsTab']
    assert len(tabs) == 5
    tab = _include('CreditsTab')
    clicks = [(o.get('condition') or '', o.text or '') for o in tab.iter('onclick')]
    # the tab changes only while its list does not load; OK on a tab whose list loads (the focus
    # started it) still goes down once it is in
    assert [c for c, t in clicks if t.startswith('SetProperty($PARAM[property]')] == ['!Container($PARAM[list]).IsUpdating']
    enter = [c for c, t in clicks if t.startswith('SetProperty(nc.info.enter')]
    assert len(enter) == 2 and not any(c.startswith('!Container($PARAM[list]).IsUpdating') for c in enter)


# only the credits list of the page: the hidden one of the other kind of page stays updating
PERSON_PAGE = 'String.IsEqual(ListItem.Property(tmdb_type),person)'
BUSY = ('[!{0} + Container(5500).IsUpdating] | [{0} + Container(5510).IsUpdating] | Container(5300).IsUpdating | '
        'Container(6501).IsUpdating | Container(6599).IsUpdating').format(PERSON_PAGE)


def test_a_tab_applies_on_focus_one_list_at_a_time():
    """DESIGN.md: focus applies. The tab under the cursor is the chosen one, no OK. While a
    TMDb list loads the choice waits (nc_credits_tab): never two plugin lists at once."""
    exprs = {e.get('name'): e.text for e in parse(SKIN / 'Includes_Tmdb.xml').iter('expression')}
    assert exprs['TmdbBusy'] == BUSY
    tab = _include('CreditsTab')
    assert [(o.get('condition'), o.text) for o in tab.iter('onfocus')] == [
        ('!$EXP[TmdbBusy]', 'SetProperty($PARAM[property],$PARAM[value],home)'),
        ('!$EXP[TmdbBusy]', 'ClearProperty(nc.tab.want.id,home)'),
        ('$EXP[TmdbBusy]', 'SetProperty(nc.tab.want.prop,$PARAM[property],home)'),
        ('$EXP[TmdbBusy]', 'SetProperty(nc.tab.want.value,$PARAM[value],home)'),
        ('$EXP[TmdbBusy]', 'SetProperty(nc.tab.want.id,$PARAM[id],home)'),
    ]
    timer = next(t for t in parse(SKIN / 'Timers.xml').iter('timer') if t.findtext('name') == 'nc_credits_tab')
    want = 'Window(Home).Property(nc.tab.want.id)'
    assert timer.findtext('start') == '!String.IsEmpty({})'.format(want)
    assert timer.findtext('stop') == 'String.IsEmpty({0}) | !String.IsEqual(System.CurrentControlId,{0}) | ![{1}]'.format(want, BUSY)
    stops = [(o.get('condition'), o.text) for o in timer.findall('onstop')]
    assert stops == [
        ('String.IsEqual(System.CurrentControlId,{}) + ![{}]'.format(want, BUSY),
         'SetProperty($INFO[Window(Home).Property(nc.tab.want.prop)],$INFO[Window(Home).Property(nc.tab.want.value)],home)'),
        (None, 'ClearProperty(nc.tab.want.id,home)'),
    ]


def test_person_credits_skip_documentaries_news_and_talk():
    """Like Arctic Fuse: a person's films, shows and crew jobs leave out documentaries, news and
    talk shows (appearances as themselves)."""
    values = _values('InfoPersonCreditsPath')
    infos = {re.search(r'info=(\w+)', text).group(1) for _, text in values}
    assert infos == {'stars_in_movies', 'stars_in_tvshows', 'crew_in_both'}
    for cond, text in values:
        assert cond.startswith(PERSON), cond
        assert 'exclude_key=genre&exclude_value=Documentary / News / Talk' in text, text
        assert 'tmdb_id=$INFO[ListItem.Property(tmdb_id)]' in text
        # without cacheonly TMDb Helper pages by 20 even with nextpage=false
        assert '&limit=250&nextpage=false&cacheonly=true' in text


def test_similar_row_waits_for_the_cast():
    """Two plugin lists starting together start two interpreters at once: similar movies load
    once the cast row has items."""
    assert _info_control('5300').findtext('content') == '$VAR[InfoSimilarPath]'
    for cond, _ in _values('InfoSimilarPath'):
        assert 'Integer.IsGreater(Container(5500).NumItems,0)' in cond


def test_back_button_leads_the_row():
    """Inside a chain the page offers to go back all the way: the manager closes every page and
    returns to where the chain started. The button names that place and stands at the left end
    of the row, the way back; Left from the first button reaches it."""
    row = _info_control('9000')
    calls = [c for c in row if c.tag == 'include' and c.get('content') == 'PillButton']
    first = calls[0]
    params = {p.get('name'): p.get('value') for p in first.findall('param')}
    assert params['id'] == '9004'
    assert params['label'] == '‹ $VAR[ChainBackLabel]'
    assert params['visible'] == RUNNING
    assert params['onclick'] == 'SetProperty(TMDbHelper.Command,exit,home)'
    # it never takes the focus when the page opens, only from within the row; a person page
    # has no other button
    assert params['enable'] == 'ControlGroup(9000).HasFocus() | String.IsEqual(ListItem.Property(tmdb_type),person)'


def test_back_button_names_the_place():
    """The playing video, else the page of Home or the library the first info page opened over
    (nc.chain.from, set while no chain runs), else the start."""
    var = next(v for v in parse(SKIN / 'Variables.xml').iter('variable') if v.get('name') == 'ChainBackLabel')
    values = [(v.get('condition'), v.text) for v in var.iter('value')]
    page = 'Window(Home).Property(nc.page)'
    home = 'String.IsEqual(Window(Home).Property(nc.chain.from),home)'
    assert values == [
        ('Player.HasVideo', '$LOCALIZE[31330]'),
        ('{} + String.IsEqual({},movies)'.format(home, page), '$LOCALIZE[31332]'),
        ('{} + String.IsEqual({},shows)'.format(home, page), '$LOCALIZE[31333]'),
        ('{} + String.IsEqual({},search)'.format(home, page), '$LOCALIZE[31334]'),
        (home, '$LOCALIZE[31331]'),
        ('String.IsEqual(Window(Home).Property(nc.chain.from),library)', '$LOCALIZE[31335]'),
        (None, '$LOCALIZE[31301]'),
    ]
    onloads = [(o.get('condition'), o.text) for o in parse(SKIN / 'DialogVideoInfo.xml').findall('onload')]
    assert ('{} + Window.IsActive(home)'.format(IDLE), 'SetProperty(nc.chain.from,home,home)') in onloads
    assert ('{} + Window.IsActive(1110)'.format(IDLE), 'SetProperty(nc.chain.from,library,home)') in onloads
    assert ('{} + !Window.IsActive(home) + !Window.IsActive(1110)'.format(IDLE), 'ClearProperty(nc.chain.from,home)') in onloads


TWIN = 'Container(5901).ListItem'


def test_tmdb_title_finds_its_library_copy():
    """A TMDb page of a title in the library looks the library copy up by title and year (a
    videodb list, no Python), off screen so it loads although nothing shows it."""
    loader = next(c for c in parse(SKIN / 'DialogVideoInfo.xml').iter('include')
                  if c.get('content') == 'WidgetLoader')
    params = {p.get('name'): p.get('value') for p in loader.findall('param')}
    assert params == {'id': '5901', 'content1': '$VAR[InfoTwinPath]'}
    values = _values('InfoTwinPath')
    assert [text.split('?')[0] for _, text in values] == ['videodb://movies/titles/', 'videodb://tvshows/titles/']
    for cond, text in values:
        assert '!String.IsEmpty(ListItem.Property(tmdb_type))' in cond and 'String.IsEmpty(ListItem.DBID)' in cond
        assert '"field":"title","operator":"is","value":["$INFO[ListItem.Title]"]' in text
        assert '"field":"year","operator":"is","value":["$INFO[ListItem.Year]"]' in text


def test_play_only_for_library_titles():
    """Play on a TMDb page plays (or resumes) the library copy; without one there is no play
    button, TMDb Helper's players are not offered."""
    buttons = {}
    for c in _info_control('9000').findall('include'):
        params = {p.get('name'): p.get('value') for p in c.findall('param')}
        buttons[params['id']] = (params, [(o.get('condition') or '', o.text or '') for o in c.iter('onclick')])
    play, clicks = buttons['9001']
    assert 'Integer.IsGreater(Container(5901).NumItems,0)' in play['visible']
    twin = [text for cond, text in clicks if 'Container(5901)' in text]
    assert 'NotifyAll(nightcity,play:movie:$INFO[{}.DBID]:resume)'.format(TWIN) in twin
    assert 'NotifyAll(nightcity,next_episode:$INFO[{}.DBID])'.format(TWIN) in twin
    for cond, text in clicks:
        if 'PlayMedia' in text:
            assert 'String.IsEmpty(ListItem.Property(tmdb_type))' in cond
    resume, clicks = buttons['9002']
    assert '{}.IsResumable'.format(TWIN) in resume['visible']
    assert 'NotifyAll(nightcity,play:movie:$INFO[{}.DBID]:noresume)'.format(TWIN) in \
        [text for _, text in clicks]
    labels = _values('InfoPlayLabel')
    assert any('{}.IsResumable'.format(TWIN) in cond and '{}.PercentPlayed'.format(TWIN) in text
               for cond, text in labels)


def test_play_takes_the_focus_when_the_copy_turns_up():
    """The page focuses its first visible button before the lookup is done; once the copy is
    found the focus moves to play, once per page and only from the button row."""
    assert 'SetProperty(nc.info.twinfocus,1,home)' in _onloads('DialogVideoInfo.xml')
    timer = _timer('nc_info_twin')
    start = timer.findtext('start')
    assert 'Integer.IsGreater(Container(5901).NumItems,0)' in start and 'nc.info.twinfocus' in start
    onstart = [(o.get('condition') or '', o.text) for o in timer.findall('onstart')]
    assert ('', 'ClearProperty(nc.info.twinfocus,home)') in onstart
    assert ('ControlGroup(9000).HasFocus()', 'SetFocus(9001)') in onstart


ROWS_UP = '!Window.IsActive(videobookmarks) + !Window.IsActive(1141)'
BAR_UP = '!Window.IsActive(1141) + !Window.IsActive(videobookmarks)'


def _osd(cid):
    return next(c for c in parse(SKIN / 'VideoOSD.xml').iter('control') if c.get('id') == cid)


def test_osd_down_opens_the_chapter_row():
    """OK shows the OSD bar, Down the chapter row (Kodi's chapters and bookmarks dialog), Down
    again the cast and crew row."""
    for cid in ('600', '620'):
        assert _osd(cid).findtext('ondown') == 'ActivateWindow(videobookmarks)', cid
    # the bar and what plays make room for the rows
    for cid in ('600', '620', '650'):
        assert _osd(cid).findtext('visible') == BAR_UP, cid
    details = _include('PlayerDetails').find('definition/control')
    assert details.findtext('visible') == ROWS_UP


def _bookmarks():
    return parse(SKIN / 'VideoOSDBookmarks.xml')


def test_chapter_row_of_thumbnails():
    root = _bookmarks()
    chapters = next(c for c in root.iter('control') if c.get('id') == '11')
    assert chapters.findtext('orientation') == 'horizontal'
    assert [c.get('content') for c in chapters.iter('include')] == ['ChapterCard', 'ChapterCard']
    card = _include('ChapterCard')
    assert '$VAR[ChapterThumb]' in [p.get('value') for p in card.iter('param')]
    assert 'ActivateWindow(1141)' in [d.text for d in chapters.findall('ondown')]
    assert chapters.findtext('onup') == '9000'
    buttons = next(c for c in root.iter('control') if c.get('id') == '9000')
    assert buttons.findtext('onup') == 'Dialog.Close(videobookmarks)'


def test_chapter_row_starts_no_python():
    """The row is one Down away from the cast row, whose list starts a plugin: the row itself
    focuses its list through two focus hops instead of a script."""
    assert not any('RunScript' in t for t in _onloads('VideoOSDBookmarks.xml'))
    controls = {c.get('id'): c for c in parse(ROOT / '1080i' / 'VideoOSDBookmarks.xml').iter('control')}
    hop = lambda cid: [(o.get('condition') or '', o.text) for o in controls[cid].findall('onfocus')]
    # focus actions wait in Kodi's queue: one hop still runs before the list is filled, the
    # second sees it
    assert hop('93') == [('', 'SetFocus(94)')]
    assert hop('94') == [('Integer.IsGreater(Container(11).NumItems,0)', 'SetFocus(11)'),
                         ('!Integer.IsGreater(Container(11).NumItems,0)', 'SetFocus(2)')]
    assert not any(t.findtext('name') == 'nc_chapters_focus' for t in parse(ROOT / '1080i' / 'Timers.xml').iter('timer'))

CAST_DIALOG = 'Custom_1141_OSDCast.xml'
LISTS_IDLE = '!Container(6501).IsUpdating + !Container(6599).IsUpdating'


def _cast():
    return parse(SKIN / CAST_DIALOG)


def _cast_control(cid):
    return next(c for c in _cast().iter('control') if c.get('id') == cid)


def _variable(name):
    return next(v for v in parse(SKIN / 'Variables.xml').iter('variable') if v.get('name') == name)


def test_cast_row_is_a_dialog_over_the_video():
    root = _cast()
    assert (root.get('type'), root.get('id')) == ('dialog', '1141')
    assert root.findtext('defaultcontrol') == '6501'
    # Down from the chapter row opens it, for movies and episodes
    chapters = next(c for c in _bookmarks().iter('control') if c.get('id') == '11')
    downs = [(d.get('condition'), d.text) for d in chapters.findall('ondown')]
    assert ('VideoPlayer.Content(movies) | VideoPlayer.Content(episodes)', 'ActivateWindow(1141)') in downs


def test_cast_row_tabs_and_photos():
    tabs = _cast_control('6520')
    assert tabs.findtext('onup') == 'Dialog.Close(1141)'
    assert tabs.findtext('ondown') == '6501'
    values = [p.get('value') for i in tabs.iter('include') if i.get('content') == 'CreditsTab'
              for p in i.iter('param') if p.get('name') == 'value']
    assert values == ['cast', 'crew']
    lst = _cast_control('6501')
    assert lst.findtext('orientation') == 'horizontal'
    assert lst.findtext('onup') == '6520'
    assert [c.get('content') for c in lst.iter('include') if c.get('content') == 'CastCard'] == ['CastCard', 'CastCard']
    assert lst.findtext('content') == '$VAR[OSDCreditsRow]'
    assert 'ClearProperty(nc.osd.credits,home)' in _onloads(CAST_DIALOG)


def test_cast_row_paths_use_the_playing_title():
    values = [(v.get('condition') or '', v.text) for v in _variable('OSDCreditsPath').findall('value')]
    texts = ' '.join(t for _, t in values)
    assert 'tmdb_id=$INFO[Window(Home).Property(TMDbHelper.Player.TMDb_ID)]' in texts
    assert 'tmdb_type=tv&tmdb_id=$INFO[Window(Home).Property(TMDbHelper.Player.tvshow.tmdb_id)]&season=$INFO[VideoPlayer.Season]&episode=$INFO[VideoPlayer.Episode]' in texts
    assert all('nextpage=false&cacheonly=true' in t for _, t in values)
    assert all('info=$VAR[OSDCreditsInfo]' in t for _, t in values)
    infos = [(v.get('condition') or '', v.text) for v in _variable('OSDCreditsInfo').findall('value')]
    assert infos == [('String.IsEqual(Window(Home).Property(nc.osd.credits),crew)', 'crew'), ('', 'cast')]


def test_cast_row_click_opens_the_person_and_leaves_the_osd():
    lst = _cast_control('6501')
    clicks = [(o.get('condition') or '', o.text) for o in lst.findall('onclick')]
    chain = next(i for i in lst.iter('include') if i.get('content') == 'ChainClick')
    params = {p.get('name'): p.get('value') for p in chain.iter('param')}
    assert params == {'type': 'person', 'id': '$INFO[ListItem.Property(tmdb_id)]', 'condition': LISTS_IDLE}
    started = '[!String.IsEmpty(Window(Home).Property(TMDbHelper.Instance)) | String.IsEmpty(Window(Home).Property(nc.chain.claim))]'
    for dialog in ('1141', 'videobookmarks', 'videoosd'):
        assert (LISTS_IDLE + ' + ' + started, f'Dialog.Close({dialog})') in clicks, dialog
    assert clicks[-1] == ('', 'noop')
    # the chain starts before the dialogs close
    children = list(lst)
    first_close = next(i for i, c in enumerate(children) if c.tag == 'onclick' and c.text == 'Dialog.Close(1141)')
    assert children.index(chain) < first_close


def test_cast_row_bio_is_debounced():
    """The focused person's biography loads in a hidden list only after the focus rested a
    second and no list is loading: moving along the row starts no plugin."""
    bio = _cast_control('6599')
    assert bio.findtext('content') == '$VAR[OSDBioPath]'
    assert bio.findtext('visible') in (None, 'true')  # hidden lists do not load
    values = [(v.get('condition') or '', v.text) for v in _variable('OSDBioPath').findall('value')]
    assert values == [('!String.IsEmpty(Window(Home).Property(nc.osd.bio.id))',
                       'plugin://plugin.video.themoviedb.helper/?info=details&tmdb_type=person&tmdb_id=$INFO[Window(Home).Property(nc.osd.bio.id)]')]
    assert 'ClearProperty(nc.osd.bio.id,home)' in _onloads(CAST_DIALOG)
    timer = _timer('nc_osd_bio')
    focused = 'Container(6501).ListItem.Property(tmdb_id)'
    assert timer.findtext('start') == f'Window.IsActive(1141) + String.IsEmpty(Window(Home).Property(nc.osd.chain)) + !String.IsEmpty({focused}) + !String.IsEqual(Window(Home).Property(nc.osd.bio.id),{focused})'
    assert timer.find('start').get('reset') == 'true'
    stop = timer.findtext('stop')
    assert f'!String.IsEqual(Window(Home).Property(nc.osd.bio.pending),{focused})' in stop
    assert 'Integer.IsGreaterOrEqual(Skin.TimerElapsedSecs(nc_osd_bio),1) + ' + LISTS_IDLE in stop
    assert [o.text for o in timer.findall('onstart')] == [f'SetProperty(nc.osd.bio.pending,$INFO[{focused}],home)']
    onstop = timer.find('onstop')
    assert onstop.get('condition') == f'Window.IsActive(1141) + String.IsEqual(Window(Home).Property(nc.osd.bio.pending),{focused})'
    assert onstop.text == 'SetProperty(nc.osd.bio.id,$INFO[Window(Home).Property(nc.osd.bio.pending)],home)'
    # shown only while it belongs to the focused person
    shown = [c for c in _cast().iter('control') if '$INFO[Container(6599).ListItem.Plot]' in (c.findtext('label') or '')]
    assert shown and all(c.findtext('visible') == f'String.IsEqual(Container(6599).ListItem.Property(tmdb_id),{focused})' for c in shown)


def test_cast_row_starts_one_plugin_at_a_time():
    assert not any('RunScript' in t for t in _onloads(CAST_DIALOG))


CLICKED = '$INFO[Window(Home).Property(nc.osd.click)]'


def test_cast_row_click_while_the_biography_loads_waits_for_it():
    """The biography loads a second after the focus rested; OK in that second used to do nothing.
    Now the click waits (nc.osd.click) until the lists are idle and then opens the person."""
    lst = _cast_control('6501')
    clicks = [(o.get('condition') or '', o.text) for o in lst.findall('onclick')]
    # the cast row itself reloads too, a second or so after playback started (the library
    # update of the playing title): a click then waits the same way
    assert ('Container(6501).IsUpdating | Container(6599).IsUpdating',
            'SetProperty(nc.osd.click,$INFO[ListItem.Property(tmdb_id)],home)') in clicks
    assert clicks[-1] == ('', 'noop')
    assert 'ClearProperty(nc.osd.click,home)' in _onloads(CAST_DIALOG)
    timer = _timer('nc_osd_click')
    assert timer.findtext('start') == '!String.IsEmpty(Window(Home).Property(nc.osd.click))'
    stop = timer.findtext('stop')
    assert '!Window.IsActive(1141)' in stop and LISTS_IDLE in stop
    onstop = [(o.get('condition') or '', o.text) for o in timer.findall('onstop')]
    ready = 'Window.IsActive(1141) + ' + LISTS_IDLE
    assert (ready + ' + ' + RUNNING, ADD_PATH + 'person&tmdb_id={},home)'.format(CLICKED)) in onstop
    idle = ready + ' + ' + IDLE + ' + String.IsEmpty(Window(Home).Property(nc.chain.claim))'
    assert (idle, 'RunScript(plugin.video.themoviedb.helper,add_tmdb={},tmdb_type=person,call_auto=1190)'.format(CLICKED)) in onstop
    assert (idle, 'SetProperty(nc.chain.claim,1,home)') in onstop
    for dialog in ('1141', 'videobookmarks', 'videoosd'):
        assert any(text == 'Dialog.Close({})'.format(dialog) and cond.startswith(ready) for cond, text in onstop), dialog
    assert onstop[-1] == ('', 'ClearProperty(nc.osd.click,home)')


GUARD = '!String.IsEmpty(Window(Home).Property(nc.chain.guard))'


def test_back_waits_until_the_manager_saw_the_page():
    """TMDb Helper's manager polls every 0.5 s for the page it opened; Back before it saw the page
    left the chain hanging on an empty backdrop for 30 s, then closed every page. In a chain the
    first second of a page holds Back (nc.chain.back) and does it when the second is over."""
    from focus import LISTS, Page
    from navigation import FOCUSABLE
    onloads = _onloads('DialogVideoInfo.xml')
    assert 'ClearProperty(nc.chain.back,home)' in onloads
    root = parse(SKIN / 'DialogVideoInfo.xml')
    guards = [o for o in root.findall('onload') if o.text == 'SetProperty(nc.chain.guard,1,home)']
    assert [o.get('condition') for o in guards] == [RUNNING]
    page = Page('DialogVideoInfo.xml')
    for cid, c in page.controls.items():
        if c.get('type') in FOCUSABLE | LISTS and cid != '5901':
            backs = [(o.get('condition') or '', o.text) for o in c.findall('onback')]
            # Back counts as handled only when it moves the focus (CGUIWindow::OnMove)
            assert backs == [(GUARD, 'SetProperty(nc.chain.back,1,home)'), (GUARD, '9000')], cid
    timer = _timer('nc_chain_guard')
    assert timer.findtext('start') == GUARD
    assert timer.find('start').get('reset') == 'true'
    assert timer.findtext('stop') == 'Integer.IsGreaterOrEqual(Skin.TimerElapsedSecs(nc_chain_guard),1)'
    onstop = [(o.get('condition') or '', o.text) for o in timer.findall('onstop')]
    assert onstop == [('', 'ClearProperty(nc.chain.guard,home)'),
                      ('!String.IsEmpty(Window(Home).Property(nc.chain.back)) + Window.IsActive(movieinformation)', 'Action(Back)'),
                      ('', 'ClearProperty(nc.chain.back,home)')]


LIVE = '!String.IsEmpty(Window(Home).Property(nc.info.live))'


def test_info_lists_start_once_per_page():
    """Kodi starts a list's plugin when the page opens, before its onload: with the credits tab
    of the page before (crew on a title, then a crew member's page) the list started its old tab
    and, once onload reset the tab, the new one: two interpreters at once, Kodi crashed. A tab
    counts only with nc.info.live, set by onload after the reset and cleared when a page closes,
    so a page opens on its first tab and onload does not change its lists."""
    for name in ('InfoPeoplePath', 'InfoPersonCreditsPath'):
        for cond, _ in _values(name):
            assert (LIVE in cond) == ('nc.info.tab' in cond), (name, cond)
    assert not any('WindowClose' in (a.text or '') for a in parse(SKIN / 'DialogVideoInfo.xml').iter('animation'))
    root = parse(SKIN / 'DialogVideoInfo.xml')
    onloads = [o.text for o in root.findall('onload')]
    live = onloads.index('SetProperty(nc.info.live,1,home)')
    for reset in ('ClearProperty(nc.info.tab,home)', 'ClearProperty(nc.info.ep.query,home)'):
        assert onloads.index(reset) < live, reset
    assert 'ClearProperty(nc.info.live,home)' in [o.text for o in root.findall('onunload')]


def test_similar_row_waits_for_the_cast_of_this_page():
    """The cast list keeps the items of the page before until its own load is done, so 'has
    items' alone started the similar movies together with the cast (two interpreters at once)."""
    for cond, _ in _values('InfoSimilarPath'):
        assert 'Integer.IsGreater(Container(5500).NumItems,0) + !Container(5500).IsUpdating' in cond


def test_info_rows_do_not_open_the_items_of_the_page_before():
    """While a list loads it still shows the items of the page before: OK on one would open a
    person or title of another page, so it waits until the list is loaded."""
    for cid, idle in (('5500', '!Container(5500).IsUpdating'), ('5510', '!Container(5510).IsUpdating'),
                      ('5300', '!Container(5500).IsUpdating + !Container(5300).IsUpdating')):
        calls = _chain_calls(_info_control(cid))
        assert calls[0].get('condition') == idle, cid


def test_home_sends_its_command_at_once():
    """Home's command runs in the skin service, which starts no interpreter: it no longer waits
    for TMDb Helper's manager to end after a chain (nc_home_script is gone)."""
    root = parse(SKIN / 'Home.xml')
    onloads = [(o.get('condition') or '', o.text) for o in root.findall('onload')]
    assert ('!String.IsEmpty(Window(Home).Property(nc.service))', 'NotifyAll(nightcity,home)') in onloads
    assert 'nc_home_script' not in [t.findtext('name') for t in parse(SKIN / 'Timers.xml').iter('timer')]
    assert not any('nc.home.script' in path.read_text() for path in SKIN.glob('*.xml'))


def test_osd_sends_its_command_at_once():
    """Back from a chain the OSD still brings up the chapter row and keeps nc.osd.chain for the
    cast row's plugin, but its own command no longer waits for TMDb Helper's manager."""
    root = parse(SKIN / 'VideoOSD.xml')
    onloads = [(o.get('condition') or '', o.text) for o in root.findall('onload')]
    assert ('', 'NotifyAll(nightcity,streams_watch)') in onloads
    timer = _timer('nc_osd_chain')
    assert [(o.get('condition') or '', o.text) for o in timer.findall('onstop')][0] == ('', 'ClearProperty(nc.osd.chain,home)')



def _control(name, cid):
    return next(c for c in parse(SKIN / name).iter('control') if c.get('id') == cid)


LEAVE = ('NotifyAll(nightcity,info_leave:{0}:$INFO[Container({0}).CurrentItem]:$INFO[Window(Home).Property(nc.info.tab)]:'
         '$INFO[Window(Home).Property(TMDbHelper.Position)]:$INFO[Window(Home).Property(nc.chain.origin.id)]:$VAR[ChainOriginDBID])')


def test_a_click_into_the_chain_keeps_the_way_back():
    """Back in a chain reopens the page before as a new page: the click keeps its list, item and
    tab first (scripts/nightcity.py info_leave), so the page goes back there."""
    for cid in ('5500', '5510', '5300'):
        children = list(_control('DialogVideoInfo.xml', cid))
        leave = [i for i, c in enumerate(children) if c.tag == 'onclick' and c.text == LEAVE.format(cid)]
        chain = [i for i, c in enumerate(children) if c.tag == 'include' and c.get('content') == 'ChainClick']
        assert leave and chain and leave[0] < chain[0], cid


def test_a_reopened_chain_page_goes_back_where_it_was_left():
    onloads = [(o.get('condition'), o.text) for o in parse(SKIN / 'DialogVideoInfo.xml').iter('onload')]
    assert (RUNNING, 'NotifyAll(nightcity,info_back)') in onloads


def test_season_tabs_list_the_show_of_a_reopened_episode():
    """TMDb Helper reopens a library episode without its show id: the tabs listed every show and
    the episodes those of another show. The service fills it in (nc.info.show)."""
    variables = {v.get('name'): v for v in parse(SKIN / 'Variables.xml').iter('variable')}
    for cid, name in (('5200', 'InfoSeasonsPath'), ('5100', 'InfoEpisodesPath')):
        assert _control('DialogVideoInfo.xml', cid).findtext('content') == '$VAR[{}]'.format(name)
        # no show id yet: no path, never videodb://tvshows/titles// (every show)
        values = list(variables[name])
        assert len(values) == 1 and values[0].get('condition') and '/$VAR[InfoShowDBID]/' in values[0].text, name
    # nor before the tabs chose a season: titles/<show>// lists the season folder
    assert '!String.IsEmpty(Container(5200).ListItem.Season)' in variables['InfoEpisodesPath'][0].get('condition')
    assert [v.text for v in variables['InfoShowDBID']] == ['$INFO[ListItem.TvShowDBID]', '$INFO[Window(Home).Property(nc.info.show)]']
    assert not [v for v in variables.values() for x in v if 'titles/$INFO[ListItem.TvShowDBID]' in (x.text or '')]
    assert 'ClearProperty(nc.info.show,home)' in _onloads('DialogVideoInfo.xml')


def test_osd_chain_ends_back_on_the_person_left():
    """A chain from the OSD cast row ends on that row, on the person it was left from: Up at the
    top of the person page used to end on the chapter row."""
    clicks = [o.text for o in _control('Custom_1141_OSDCast.xml', '6501').iter('onclick')]
    keep = ['SetProperty(nc.osd.ret,$INFO[Container(6501).CurrentItem],home)',
            'SetProperty(nc.osd.ret.tab,$INFO[Window(Home).Property(nc.osd.credits)],home)']
    assert all(k in clicks for k in keep)
    late = [o.text for o in _timer('nc_osd_click').iter('onstop')]
    assert all(k in late for k in keep)
    # at once over the chapter row, which hides meanwhile; the row's lists wait for the manager
    reopen = [(o.get('condition'), o.text) for o in parse(SKIN / 'VideoOSDBookmarks.xml').iter('onload')]
    assert ('!String.IsEmpty(Window(Home).Property(nc.osd.ret)) + !String.IsEmpty(Window(Home).Property(nc.osd.chain))', 'ActivateWindow(1141)') in reopen
    assert all(o.text != 'ActivateWindow(1141)' for o in _timer('nc_osd_chain').iter('onstop'))
    onloads = [(o.get('condition'), o.text) for o in parse(SKIN / 'Custom_1141_OSDCast.xml').iter('onload')]
    back = '!String.IsEmpty(Window(Home).Property(nc.osd.ret))'
    assert ('String.IsEmpty(Window(Home).Property(nc.osd.ret))', 'ClearProperty(nc.osd.credits,home)') in onloads
    assert (back, 'SetProperty(nc.osd.credits,$INFO[Window(Home).Property(nc.osd.ret.tab)],home)') in onloads
    assert (back, 'NotifyAll(nightcity,osd_back:$INFO[Window(Home).Property(nc.osd.ret)]:$INFO[Window(Home).Property(nc.osd.ret.tab)])') in onloads
    assert onloads[-1] == (None, 'ClearProperty(nc.osd.ret,home)')
    assert 'ClearProperty(nc.osd.ret,home)' in _onloads('Home.xml')


def test_osd_cast_row_loads_nothing_while_a_chain_ends():
    """The cast row opens at once after a chain; its plugin lists wait until TMDb Helper's
    manager is gone (nc.osd.chain): two interpreters starting at once crash Kodi."""
    assert _control('Custom_1141_OSDCast.xml', '6501').findtext('content') == '$VAR[OSDCreditsRow]'
    var = next(v for v in parse(SKIN / 'Variables.xml').iter('variable') if v.get('name') == 'OSDCreditsRow')
    assert [(v.get('condition'), v.text) for v in var] == [
        ('String.IsEmpty(Window(Home).Property(nc.osd.chain))', '$VAR[OSDCreditsPath]')]
    assert 'String.IsEmpty(Window(Home).Property(nc.osd.chain))' in _timer('nc_osd_bio').findtext('start')
    row = parse(SKIN / 'VideoOSDBookmarks.xml').find('controls/control')
    assert row.findtext('visible') == '!Window.IsActive(1141) + String.IsEmpty(Window(Home).Property(nc.osd.ret))'


def test_a_page_on_its_way_back_parks_the_focus_out_of_sight():
    """Until the list it was left from is in, the reopened page shows no focus (stand-in 9098)
    instead of a second on its buttons; a key moves on to the buttons."""
    stand_in = _control('DialogVideoInfo.xml', '9098')
    assert stand_in.get('type') == 'button'
    assert all(stand_in.findtext(k) == '9000' for k in ('onup', 'ondown', 'onleft', 'onright'))
    assert stand_in.find('texturefocus') is not None and not (stand_in.findtext('texturefocus') or '').strip()

    parks = [(o.get('condition'), o.text) for o in parse(SKIN / 'DialogVideoInfo.xml').iter('onload')]
    assert (RUNNING + ' + String.IsEqual(Window(Home).Property(TMDbHelper.Position),Window(Home).Property(nc.ret.top))',
            'SetFocus(9098)') in parks
