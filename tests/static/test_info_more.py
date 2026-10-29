"""… on the info page of a TMDb title without a library copy (DialogVideoInfo 9005): Kodi's
context menu of the title as TMDb Helper lists it, with TMDb Helper's entries (related lists,
Trakt, add to library). The one-item list behind it (9006) starts a plugin, so it loads only
on OK and once the page's own plugin lists are idle: two interpreters starting at once can
crash Kodi."""
from conftest import ROOT, parse

SKIN = ROOT / '1080i'
MORE = '!String.IsEmpty(Window(Home).Property(nc.info.more))'
LOAD = '!String.IsEmpty(Window(Home).Property(nc.info.more.load))'
IDLE = '!Container(5500).IsUpdating + !Container(5300).IsUpdating'
DETAILS = ('plugin://plugin.video.themoviedb.helper/?info=details&tmdb_type=$INFO[ListItem.Property(tmdb_type)]'
           '&tmdb_id=$INFO[ListItem.Property(tmdb_id)]')


def _info():
    return parse(SKIN / 'DialogVideoInfo.xml')


def _control(cid):
    return next(c for c in _info().iter('control') if c.get('id') == cid)


def _pill(cid):
    for inc in _info().iter('include'):
        params = {p.get('name'): p.get('value') for p in inc.findall('param')}
        if inc.get('content') == 'PillButton' and params.get('id') == cid:
            return params
    raise AssertionError(cid)


def _timer(name):
    return next(t for t in parse(SKIN / 'Timers.xml').iter('timer') if t.findtext('name') == name)


def test_ok_on_more_asks_for_the_titles_menu():
    pill = _pill('9005')
    assert pill['label'] == '…'
    assert pill['onclick'] == 'SetProperty(nc.info.more,1,home)'


def test_the_menu_list_holds_the_title_as_tmdb_helper_lists_it():
    menu = _control('9006')
    assert menu.get('type') == 'list'
    assert menu.find('content').get('target') == 'videos'
    assert menu.findtext('visible') == LOAD
    # a hidden list still loads its content when the page opens: the path stays empty until OK
    assert menu.findtext('content') == '$VAR[InfoMorePath]'
    values = [(v.get('condition'), v.text) for v in next(
        el for el in parse(SKIN / 'Variables.xml').iter('variable') if el.get('name') == 'InfoMorePath').findall('value')]
    # never with empty ids: TMDb Helper would start for nothing next to the page's own lists
    assert values == [(LOAD + ' + !String.IsEmpty(ListItem.Property(tmdb_id))', DETAILS)]
    for key in ('onup', 'ondown', 'onleft', 'onright'):
        assert menu.findtext(key) == '9005', key


def test_the_list_loads_once_the_pages_lists_are_idle():
    timer = _timer('nc_info_more')
    start = timer.findtext('start')
    assert MORE in start and IDLE in start and 'Window.IsActive(movieinformation)' in start
    assert [a.text for a in timer.findall('onstart')] == ['SetProperty(nc.info.more.load,1,home)']
    stop = timer.findtext('stop')
    assert 'Integer.IsGreater(Container(9006).NumItems,0)' in stop
    assert 'Integer.IsGreaterOrEqual(Skin.TimerElapsedSecs(nc_info_more),10)' in stop
    actions = [(a.get('condition'), a.text) for a in timer.findall('onstop')]
    ready = 'Window.IsActive(movieinformation) + Integer.IsGreater(Container(9006).NumItems,0)'
    assert actions == [(ready, 'SetFocus(9006)'), (ready, 'Action(ContextMenu)'),
                       (None, 'ClearProperty(nc.info.more,home)')]


def test_focus_goes_back_to_the_pill_once_the_menu_closed():
    """Kodi runs queued actions inside the menu's own loop, so a SetFocus right behind
    Action(ContextMenu) would reach the menu: a timer moves it once the menu is gone."""
    timer = _timer('nc_info_more_back')
    assert timer.findtext('start') == ('Window.IsActive(movieinformation) + Control.HasFocus(9006)'
                                       ' + !Window.IsVisible(contextmenu)')
    assert [a.text for a in timer.findall('onstart')] == ['SetFocus(9005)']


def test_a_new_page_forgets_the_menu():
    onloads = [o.text for o in _info().findall('onload')]
    assert 'ClearProperty(nc.info.more,home)' in onloads
    assert 'ClearProperty(nc.info.more.load,home)' in onloads


def test_a_closing_page_forgets_the_menu():
    """The dialog stays in memory and the next page loads its lists before its onload: with the
    request left over, list 9006 started TMDb Helper with empty ids next to the new page's plugin
    lists (two interpreters at once crash Kodi)."""
    onunloads = [o.text for o in _info().findall('onunload')]
    assert 'ClearProperty(nc.info.more,home)' in onunloads
    assert 'ClearProperty(nc.info.more.load,home)' in onunloads


def test_the_menu_opens_at_the_buttons():
    """Kodi opens the menu at the focused control: the list lies on the button row, drawing
    nothing (empty layouts), not off screen, where the menu would open in the corner."""
    menu, row = _control('9006'), _control('9000')
    assert (menu.findtext('left'), menu.findtext('top')) == (row.findtext('left'), row.findtext('top'))
    assert all(len(layout) == 0 for layout in menu.findall('itemlayout') + menu.findall('focusedlayout'))


def test_the_wait_skips_the_person_credits():
    """… is never on a person page; there the credits list 5510 has no path and can keep
    IsUpdating from the page before, which held the menu back for good."""
    assert '5510' not in _timer('nc_info_more').findtext('start')
