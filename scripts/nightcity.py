"""Helpers the skin runs with RunScript(special://skin/scripts/nightcity.py,<command>,...).

They do what skin XML cannot: pick the next episode of a show, preselect items in lists,
count genres and apply one-off settings. The pure functions at the top have no Kodi imports so
they can be tested without Kodi.
"""
import json
import re
import sys
import threading
import urllib.parse


def _key(item):
    return item['season'], item['episode']


def pick_next_episode(episodes):
    """The episode a click on a show should open.

    A started episode wins (the latest one if there are several), then the first unwatched
    episode of a regular season, then the first episode of the first regular season, then the
    first episode at all.
    """
    if not episodes:
        return None
    ordered = sorted(episodes, key=_key)
    started = [e for e in ordered if (e.get('resume') or {}).get('position', 0) > 0]
    if started:
        return started[-1]
    regular = [e for e in ordered if e['season'] >= 1]
    unwatched = [e for e in regular if not e.get('playcount')]
    if unwatched:
        return unwatched[0]
    return regular[0] if regular else ordered[0]


def index_of(items, key, value):
    """Position of the first item whose key equals value, 0 if there is none."""
    for i, item in enumerate(items):
        if item.get(key) == value:
            return i
    return 0


def find_index(labels, target):
    """Position of target in labels, None if it is not there."""
    return labels.index(target) if target in labels else None


def top_genres(counts, n=3):
    """counts maps a genre label to (genreid, number of titles); the n biggest as (id, label)."""
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1][1], kv[0]))
    return [(genreid, label) for label, (genreid, _) in ranked[:n]]


def genre_counts(movies, genres):
    """Number of movies per genre as {label: (genreid, count)}; genres without movies are left out."""
    ids = {g['label']: g['genreid'] for g in genres}
    counts = {}
    for movie in movies:
        for label in movie.get('genre', []):
            if label in ids:
                genreid, n = counts.get(label, (ids[label], 0))
                counts[label] = (genreid, n + 1)
    return counts


def player_open_params(mediatype, dbid, mode):
    """JSON-RPC Player.Open parameters for a library item; mode is resume or noresume. None
    without a database id."""
    if not dbid:
        return None
    return {'item': {'{}id'.format(mediatype): int(dbid)}, 'options': {'resume': mode == 'resume'}}


CHANNELS = {1: 'mono', 2: 'stereo', 6: '5.1', 8: '7.1'}
PANEL_ROWS = 8  # rows the track panels of the OSD show at once
PANEL_SLOTS = 14  # rows a track panel has (TrackItem entries in Includes_Player.xml)


def _language(stream, names):
    code = stream.get('language') or ''
    return names(code) or code, code.upper()


def audio_rows(streams, current, names):
    """Rows of the audio panel: label, language tag and '1' for the playing track. Kodi's
    stream name holds the title, the layout is added when the name lacks it; without a name,
    language and layout. The language code is the tag."""
    rows = []
    for stream in streams:
        language, tag = _language(stream, names)
        channels = stream.get('channels')
        layout = CHANNELS.get(channels, '{}ch'.format(channels)) if channels else ''
        name = stream.get('name') or ''
        if name:
            label = name if not layout or layout.lower() in name.lower() else '{} · {}'.format(name, layout)
        else:
            label = ' '.join(p for p in (language or '#{}'.format(stream['index'] + 1), layout) if p)
        rows.append({'label': label, 'tag': tag, 'current': '1' if stream['index'] == current.get('index') else ''})
    return rows


def subtitle_rows(subs, current, enabled, names):
    """Rows of the subtitle panel; no row is current while subtitles are off."""
    rows = []
    for sub in subs:
        language, tag = _language(sub, names)
        parts = [language or '#{}'.format(sub['index'] + 1), sub.get('name') or '']
        parts += ['forced'] if sub.get('isforced') else []
        parts += ['SDH'] if sub.get('isimpaired') else []
        on = enabled and sub['index'] == current.get('index')
        rows.append({'label': ' · '.join(p for p in parts if p), 'tag': tag, 'current': '1' if on else ''})
    return rows


SETTINGS = {'audio': 'osdaudiosettings', 'sub': 'osdsubtitlesettings'}


def _window(rows, n):
    """At most n rows, keeping the current one: from the start, or ending on the current row."""
    at = current_position(rows)
    start = max(0, at - n + 1) if len(rows) > n else 0
    return rows[start:start + n]


def panel(kind, props, names, words):
    """All rows of the OSD track panel `kind` (audio or sub) from Player.GetProperties: tracks,
    for subtitles an "off" row first, and a last row that opens Kodi's full settings. Each row
    has label, tag, current ('1' or '') and the action a click runs. Long lists keep the
    playing track and fit PANEL_SLOTS; the full settings show the rest."""
    if kind == 'audio':
        tracks = props.get('audiostreams', [])
        rows = audio_rows(tracks, props.get('currentaudiostream') or {}, names)
        for row, track in zip(rows, tracks):
            row['action'] = ('audio', track['index'])
        rows = _window(rows, PANEL_SLOTS - 1)
    else:
        tracks = props.get('subtitles', [])
        enabled = bool(props.get('subtitleenabled') and tracks)
        rows = subtitle_rows(tracks, props.get('currentsubtitle') or {}, enabled, names)
        for row, track in zip(rows, tracks):
            row['action'] = ('subtitle', track['index'])
        rows = _window(rows, PANEL_SLOTS - 2)
        rows.insert(0, {'label': words['off'], 'tag': '', 'current': '' if enabled else '1',
                        'action': ('subtitle', 'off')})
    rows.append({'label': '… ' + words['more'], 'tag': '', 'current': '', 'action': ('settings', SETTINGS[kind])})
    return rows


def row_is_current(rows, n):
    """Whether row n (1 = first) exists and is the current one."""
    return 1 <= n <= len(rows) and bool(rows[n - 1]['current'])


def current_position(rows):
    """List position of the current row, 0 without one."""
    return next((n for n, row in enumerate(rows) if row['current']), 0)


SEARCH_KINDS = (('movies', 'videodb://movies/titles/'), ('tvshows', 'videodb://tvshows/titles/'),
                ('episodes', 'videodb://tvshows/titles/-1/-1/'))
TMDB_SEARCH = 'plugin://plugin.video.themoviedb.helper/?info=search&tmdb_type={}&query={}'
RECENT = 5  # remembered search terms


def search_paths(term):
    """Content paths of the search page rows for `term`: library titles containing it and
    TMDb Helper's online search. All empty without a term."""
    keys = [kind for kind, _ in SEARCH_KINDS] + ['tmdb_movies', 'tmdb_tvshows']
    if not term:
        return dict.fromkeys(keys, '')
    paths = {}
    for kind, base in SEARCH_KINDS:
        rule = {'rules': {'and': [{'field': 'title', 'operator': 'contains', 'value': [term]}]}, 'type': kind}
        paths[kind] = base + '?xsp=' + urllib.parse.quote(json.dumps(rule), safe='')
    query = urllib.parse.quote(term, safe='')
    paths['tmdb_movies'] = TMDB_SEARCH.format('movie', query)
    paths['tmdb_tvshows'] = TMDB_SEARCH.format('tv', query)
    return paths


def search_batches(term):
    """search_paths in two batches: the TMDb tv search after the movie search, as two TMDb Helper
    searches starting at once start two Python interpreters at once, which crashes Kodi."""
    paths = search_paths(term)
    return dict(paths, tmdb_tvshows=''), {'tmdb_tvshows': paths['tmdb_tvshows']}


TMDB_STAGGER = 2.0  # s between the two TMDb searches (the search page's timer waits as long)


def remember(history, term, n=RECENT):
    """History with `term` in front, without a second copy (any case), at most n terms."""
    term = term.strip()
    if not term:
        return history
    return ([term] + [t for t in history if t.lower() != term.lower()])[:n]


# Home pages (skin settings, SkinSettings.xml; tools/make_sections.py builds the rows from this): the
# sections each page offers, in dialog order, with their options as (value, label id). Slot n of a
# page is Skin.String(nc.<page>.slot<n>): a section key, none for an empty slot, empty for the
# slot's default. Its option is nc.<page>.slot<n>.opt, empty for the first option.
SLOTS = 8
BOTH, MOVIES, SHOWS = ('both', 21475), ('movies', 342), ('shows', 20343)
ALL, UNWATCHED = ('all', 593), ('unwatched', 16101)
SECTIONS = {  # key: (name, description) string ids
    'continue': (31233, 31241), 'nextup': (31234, 31242), 'newmovies': (31235, 31243),
    'newepisodes': (31236, 31244), 'genres': (135, 31245), 'random': (31237, 31246),
    'unwatched': (16101, 31247), 'toprated': (31238, 31248), 'favourites': (1036, 31249),
    'trending': (31239, 31250), 'recent': (31240, 31251), 'sets': (20434, 31252),
    'inprogress': (575, 31253),
}
CATALOGUE = {
    'home': [('continue', (BOTH, MOVIES, SHOWS)), ('nextup', ()), ('newmovies', (ALL, UNWATCHED)),
             ('newepisodes', (ALL, UNWATCHED)), ('genres', (MOVIES, SHOWS)), ('random', (ALL, UNWATCHED)),
             ('unwatched', (MOVIES, SHOWS, BOTH)), ('toprated', (MOVIES, SHOWS)), ('favourites', ()),
             ('trending', (MOVIES, SHOWS)), ('recent', (BOTH, MOVIES, SHOWS))],
    'movies': [('continue', ()), ('newmovies', (ALL, UNWATCHED)), ('unwatched', ()), ('random', (ALL, UNWATCHED)),
               ('toprated', ()), ('genres', ()), ('sets', ()), ('trending', ())],
    'shows': [('nextup', ()), ('newepisodes', (ALL, UNWATCHED)), ('inprogress', ()), ('unwatched', ()),
              ('genres', ()), ('trending', ())],
}
# the rows each page had before the slots: what an empty Skin.String stands for
DEFAULTS = {'home': ('continue', 'newmovies', 'newepisodes', 'nextup'),
            'movies': ('newmovies', 'continue', 'unwatched', 'genres'),
            'shows': ('nextup', 'newepisodes', 'inprogress', 'unwatched')}


def default_slots(page):
    return list(DEFAULTS[page]) + ['none'] * (SLOTS - len(DEFAULTS[page]))


def slot_values(page, raw):
    """(key, option) of the slots from their raw Skin.String pairs: empty is the slot's default,
    an unknown key an empty slot."""
    keys = [key for key, _ in CATALOGUE[page]]
    slots = []
    for (key, opt), default in zip(raw, default_slots(page)):
        key = key or default
        slots.append((key, opt) if key in keys else ('none', ''))
    return slots


def section_rows(page, slots, n):
    """Entries of the dialog for slot n: (value, slot that already shows it or None), empty
    first and move last."""
    used = {key: i for i, (key, _) in enumerate(slots, 1) if key != 'none'}
    rows = [('none', None)]
    rows += [(key, used[key] if used.get(key, n) != n else None) for key, _ in CATALOGUE[page]]
    return rows + [('move', None)]


def apply_pick(slots, n, value):
    """Slots to change when `value` is picked for slot n: {slot: (key, option)}. A section shown
    elsewhere swaps places with slot n."""
    current = slots[n - 1]
    if value == current[0]:
        return {}
    for m, slot in enumerate(slots, 1):
        if m != n and slot[0] == value and value != 'none':
            return {n: slot, m: current}
    return {n: (value, '')}


def _rpc(method, **params):
    import xbmc
    request = {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}
    response = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
    if 'error' in response:
        raise RuntimeError('{}: {}'.format(method, response['error']))
    return response['result']


INFO_CLAIM = 5.0  # s an info page opened by a script counts as on its way


def info_claimed(value, now):
    """Whether nc.info.opening (the time a script began to open an info page) is recent: two
    info pages opening at once crash Kodi."""
    try:
        return now - float(value) < INFO_CLAIM
    except ValueError:
        return False


def _claim_info():
    import time
    _home().setProperty('nc.info.opening', str(time.time()))


CHAIN_DBITEM = 'plugin://script.skinvariables/?info=get_dbitem_{}_details&dbid={}'


def chain_path(mediatype, dbid):
    """The page of a library item on TMDb Helper's window manager stack. In direct mode
    (TMDbHelper.DirectCallAuto) the manager builds these items itself, script.skinvariables is
    not needed."""
    return CHAIN_DBITEM.format(mediatype, dbid)


def chain_running(home):
    """Whether TMDb Helper's window manager runs a chain of info pages; it owns the info dialog
    then, a second one opened by a script would crash Kodi or confuse its Back handling."""
    return bool(home.getProperty('TMDbHelper.Instance'))


def _chain_push(home, path):
    """Put a page on the running chain: the manager's loop picks the property up."""
    home.setProperty('TMDbHelper.Path.To.Add', path)


CHAIN_EXIT = 10.0  # s to wait for the manager to close its pages


def _chain_exit(home):
    """Ask a running chain to close all its pages and wait until it has."""
    home.setProperty('TMDbHelper.Command', 'exit')
    _wait('String.IsEmpty(Window(Home).Property(TMDbHelper.Instance))', timeout=CHAIN_EXIT)


def next_episode(tvshowid):
    """Open the info page of the episode a click on a show should open (pick_next_episode); in a
    running chain it goes onto the manager's stack instead."""
    home = _home()
    running = chain_running(home)
    if not running:
        _claim_info()
    episodes = _rpc('VideoLibrary.GetEpisodes', tvshowid=int(tvshowid),
                    properties=['season', 'episode', 'playcount', 'resume', 'file', 'title'])
    found = pick_next_episode(episodes.get('episodes', []))
    if not found:
        return
    if running:
        _chain_push(home, chain_path('episode', found['episodeid']))
        return
    import xbmcgui
    item = xbmcgui.ListItem(found['title'], path=found['file'])
    tag = item.getVideoInfoTag()
    tag.setDbId(found['episodeid'])
    tag.setMediaType('episode')
    xbmcgui.Dialog().info(item)


def _home():
    import xbmcgui
    return xbmcgui.Window(10000)


# genre rows: media type -> (library method, result key, Window(Home) property prefix)
GENRE_KINDS = {'movie': ('VideoLibrary.GetMovies', 'movies', 'nc.genre'),
               'tvshow': ('VideoLibrary.GetTVShows', 'tvshows', 'nc.tvgenre')}


def _genres(kind='movie'):
    method, key, _ = GENRE_KINDS[kind]
    genres = _rpc('VideoLibrary.GetGenres', type=kind).get('genres', [])
    items = _rpc(method, properties=['genre']).get(key, [])
    return genre_counts(items, genres)


def _set_genre(home, genreid, label, kind='movie'):
    prop = GENRE_KINDS[kind][2]
    home.setProperty(prop + '.id', str(genreid))
    home.setProperty(prop + '.label', label)


def genres():
    """Fill the genre tabs of movies (nc.genre.1-3.id/label) and shows (nc.tvgenre...) with the
    biggest genres and pick the first one unless a genre is already chosen."""
    home = _home()
    for kind, (_, _, prop) in GENRE_KINDS.items():
        top = top_genres(_genres(kind))
        for n in range(1, 4):
            genreid, label = top[n - 1] if n <= len(top) else ('', '')
            home.setProperty('{}.{}.id'.format(prop, n), str(genreid))
            home.setProperty('{}.{}.label'.format(prop, n), label)
        if top and not home.getProperty(prop + '.id'):
            _set_genre(home, *top[0], kind=kind)


def genre_pick(kind='movie'):
    """Offer every genre of movies or shows; the chosen one fills the genre row."""
    import xbmc
    import xbmcgui
    home = _home()
    ranked = sorted(_genres(kind).items(), key=lambda kv: kv[0].lower())
    current = home.getProperty(GENRE_KINDS[kind][2] + '.id')
    preselect = index_of([{'id': str(genreid)} for _, (genreid, _) in ranked], 'id', current)
    labels = ['{}  ({})'.format(label, n) for label, (_, n) in ranked]
    chosen = xbmcgui.Dialog().select(xbmc.getInfoLabel('$LOCALIZE[31105]'), labels, preselect=preselect)
    if chosen >= 0:
        label, (genreid, _) = ranked[chosen]
        _set_genre(home, genreid, label, kind)


def section_pick(page, n):
    """Section dialog of slot n in the skin settings (SkinSettings.xml): empty, the catalogue
    (a section shown on another slot says so and swaps) and move, which grabs the slot."""
    import xbmc
    import xbmcgui
    n = int(n)
    raw = [(xbmc.getInfoLabel('Skin.String(nc.{}.slot{})'.format(page, i)),
            xbmc.getInfoLabel('Skin.String(nc.{}.slot{}.opt)'.format(page, i))) for i in range(1, SLOTS + 1)]
    slots = slot_values(page, raw)
    rows = section_rows(page, slots, n)

    def text(string_id):
        return xbmc.getInfoLabel('$LOCALIZE[{}]'.format(string_id))
    names = dict({key: ids[0] for key, ids in SECTIONS.items()}, none=504, move=116)
    items = []
    for key, used in rows:
        item = xbmcgui.ListItem(text(names[key]))
        if used:
            item.setLabel2('{} {}, {}'.format(text(31229), used, text(31263)))
        items.append(item)
    current = [key for key, _ in rows].index(slots[n - 1][0])
    chosen = xbmcgui.Dialog().select('{} {}'.format(text(31231), n), items, preselect=current, useDetails=True)
    if chosen < 0:
        return
    value = rows[chosen][0]
    if value == 'move':
        # the skin settings, back on top once the dialog closed
        xbmcgui.Window(xbmcgui.getCurrentWindowId()).setProperty('nc.hp.grab', '{}.{}'.format(page, n))
        return
    for slot, (key, opt) in apply_pick(slots, n, value).items():
        xbmc.executebuiltin('Skin.SetString(nc.{}.slot{},{})'.format(page, slot, key))
        xbmc.executebuiltin('Skin.SetString(nc.{}.slot{}.opt,{})'.format(page, slot, opt))


# set when Kodi announces its quit (System.OnQuit, heard by the service): Kodi sends no abort to a
# script started by its path, and on quit waits 5 s for each of its threads before it kills it
QUIT = threading.Event()


def _monitor(base=None):
    """An xbmc.Monitor (or subclass BASE) whose waits also end on QUIT."""
    import xbmc

    class Monitor(base or xbmc.Monitor):
        def waitForAbort(self, *timeout):
            return super().waitForAbort(*timeout) or QUIT.is_set()

        def abortRequested(self):
            return super().abortRequested() or QUIT.is_set()

    return Monitor()


def _wait(condition, timeout=5.0):
    import xbmc
    monitor = _monitor()
    end = timeout
    while end > 0:
        if xbmc.getCondVisibility(condition):
            return True
        if monitor.waitForAbort(0.1):
            return False
        end -= 0.1
    return False




def _labels(container, info):
    import xbmc
    count = int(xbmc.getInfoLabel('Container({}).NumItems'.format(container)) or 0)
    return [xbmc.getInfoLabel('Container({}).ListItemAbsolute({}).{}'.format(container, i, info))
            for i in range(count)]


def info_select():
    """On the info page of an episode, select its season tab and the episode itself, then
    give focus back to the play button. nc.info.ready (Home) is set once that is done."""
    import xbmc
    home = _home()
    home.clearProperty('nc.info.ready')
    try:
        _info_show()
        _select_episode()
    finally:
        home.setProperty('nc.info.ready', '1')


def _info_show():
    """The show of the episode on the info page, for its season tabs, when Kodi left it out:
    TMDb Helper reopens a library episode of a chain without it, and the tabs listed every show
    (nc.info.show, InfoShowDBID in Variables.xml)."""
    import xbmc
    dbid = xbmc.getInfoLabel('ListItem.DBID')
    if xbmc.getInfoLabel('ListItem.TvShowDBID') or not dbid.isdigit():
        return
    details = _rpc('VideoLibrary.GetEpisodeDetails', episodeid=int(dbid), properties=['tvshowid'])
    _home().setProperty('nc.info.show', str(details['episodedetails']['tvshowid']))


# the episode row (5100) lists the episodes of the season (format: its number). Its first path
# lacks the season, before the season tabs (5200) chose one: it then lists the season folder,
# whose Season matches and whose Episode is the count of its episodes. Right after Kodi started the
# lists load slowly enough to catch it there, and the episode stayed unselected.
EPISODES_IN = ('String.IsEqual(Container(5100).ListItemAbsolute(0).DBType,episode) + '
               'String.IsEqual(Container(5100).ListItemAbsolute(0).Season,{})')


def _select_episode():
    import xbmc
    season = xbmc.getInfoLabel('ListItem.Season')
    episode = xbmc.getInfoLabel('ListItem.Episode')
    if not _wait('Integer.IsGreater(Container(5200).NumItems,0)'):
        return
    index = find_index(_labels(5200, 'Season'), season)
    if index is not None:
        _focus('SetFocus(5200,{},absolute)'.format(index))
    if _wait(EPISODES_IN.format(season)):
        index = find_index(_labels(5100, 'Episode'), episode)
        if index is not None:
            _focus('SetFocus(5100,{},absolute)'.format(index))
    # on the way back in a chain the focus waits out of sight for the list (info_back)
    if xbmc.getCondVisibility('!String.IsEmpty(Window(Home).Property(nc.info.back))'):
        _focus('SetFocus({})'.format(INFO_STAND_IN))
    else:
        _focus('SetFocus(9001)')


# --- the way back into a page of a TMDb chain ------------------------------------------------
# A chain page that TMDb Helper reopens on the way back is a new page: the focus would start on
# its buttons. A click into the chain keeps where it left (info_leave, Home property nc.ret.<chain
# position>); the reopened page goes back there (info_back): the tab and the item. An episode
# page reopens on the episode whose cast was clicked (ChainOriginDBID in Variables.xml).

RETURN_FIELDS = ('list', 'index', 'tab', 'tmdb_id', 'dbid')
INFO_STAND_IN = '9098'  # DialogVideoInfo.xml: the focus out of sight
# the TMDb lists of a page have stopped loading: a tab may change what one of them shows (two
# plugin lists at once crash Kodi; TmdbBusy in Includes_Tmdb.xml)
INFO_LISTS_REST = {'5500': '!Container(5500).IsUpdating + !Container(5300).IsUpdating',
                   '5510': '!Container(5510).IsUpdating',
                   '5300': '!Container(5500).IsUpdating + !Container(5300).IsUpdating'}


def return_key(position):
    """Home property of the way back into the chain page at POSITION; the page a chain starts
    from has none yet, it becomes the first."""
    return 'nc.ret.' + (position or '1')


def return_point(list_id, item, tab, tmdb_id, dbid):
    """The way back as text: the list, its item (CurrentItem counts from 1), the tab, the page
    (TMDb id or library id). None without an item."""
    if not list_id or not item.isdigit() or int(item) < 1:
        return None
    return '|'.join([list_id, str(int(item) - 1), tab, tmdb_id, dbid])


def parse_return(text):
    parts = text.split('|') if text else []
    if len(parts) != len(RETURN_FIELDS) or not parts[1].isdigit():
        return None
    point = dict(zip(RETURN_FIELDS, parts))
    point['index'] = int(point['index'])
    return point


def return_matches(point, tmdb_id, dbid):
    """The way back belongs to the page: same TMDb id, or same library id."""
    return bool((point['tmdb_id'] and point['tmdb_id'] == tmdb_id) or (point['dbid'] and point['dbid'] == dbid))


def info_leave(list_id, item, tab, position, tmdb_id, dbid):
    point = return_point(list_id, item, tab, tmdb_id, dbid)
    if point:
        home = _home()
        home.setProperty(return_key(position), point)
        # the page parks its focus at once when it opens again (DialogVideoInfo.xml onload)
        home.setProperty('nc.ret.top', return_key(position)[len('nc.ret.'):])


def info_back():
    """On a page reopened in a chain: back to the tab and item it was left from. The list may
    still load: nc_info_enter (Timers.xml) enters it once it is in, then the item. Meanwhile the
    focus waits out of sight (stand-in 9098), not on the buttons; nc.info.back tells
    info_select. Without the list it ends on the buttons."""
    import xbmc
    home = _home()
    position = return_key(xbmc.getInfoLabel('Window(Home).Property(TMDbHelper.Position)'))[len('nc.ret.'):]
    key = return_key(position)
    point = parse_return(home.getProperty(key))
    # the page before parks at once next, if it has a way back
    before = str(int(position) - 1) if position.isdigit() else ''
    if before and home.getProperty(return_key(before)):
        home.setProperty('nc.ret.top', before)
    else:
        home.clearProperty('nc.ret.top')
    if not point or not return_matches(point, xbmc.getInfoLabel('ListItem.Property(tmdb_id)'),
                                       xbmc.getInfoLabel('ListItem.DBID')):
        # parked by the onload for a way back that belongs to another page
        if xbmc.getCondVisibility('Control.HasFocus({})'.format(INFO_STAND_IN)):
            _focus('SetFocus(9000)')
        return
    home.clearProperty(key)
    home.setProperty('nc.info.back', '1')
    try:
        _focus('SetFocus({})'.format(INFO_STAND_IN))
        _info_back(home, point)
    finally:
        home.clearProperty('nc.info.back')
        if xbmc.getCondVisibility('Control.HasFocus({})'.format(INFO_STAND_IN)):
            _focus('SetFocus(9000)')


def _info_back(home, point):
    import xbmc
    if xbmc.getCondVisibility('String.IsEqual(ListItem.DBType,episode)'):
        # info_select picks the episode first
        if not _wait('!String.IsEmpty(Window(Home).Property(nc.info.ready))', 10.0):
            return
    if point['tab']:
        if not _wait(INFO_LISTS_REST.get(point['list'], 'true'), 30.0):
            return
        home.setProperty('nc.info.tab', point['tab'])
    if not xbmc.getCondVisibility('Window.IsActive(movieinformation)'):
        return
    home.setProperty('nc.info.enter.from', INFO_STAND_IN)
    home.setProperty('nc.info.enter', point['list'])
    if _wait('Control.HasFocus({})'.format(point['list']), 20.0):
        _focus('SetFocus({},{},absolute)'.format(point['list'], point['index']))


def osd_back(item, tab):
    """The OSD cast row reopened after a chain: the person it was left from (ITEM counts from 1)."""
    import xbmc
    if not item.isdigit() or int(item) < 1:
        return
    index = int(item) - 1
    if _wait('Window.IsActive(1141) + !Container(6501).IsUpdating + Integer.IsGreater(Container(6501).NumItems,{})'
             ' + String.IsEqual(Container(6501).ListItem(0).Property(param.info),{})'.format(index, tab or 'cast'), 20.0):
        if xbmc.getCondVisibility('Window.IsActive(1141)'):
            xbmc.executebuiltin('SetFocus(6501,{},absolute)'.format(index))


def _focus(command):
    """Run a SetFocus only while the info page is still open: the waits above take up to
    seconds, and the same ids on the window below would take the focus off-screen."""
    import xbmc
    if xbmc.getCondVisibility('Window.IsActive(movieinformation)'):
        xbmc.executebuiltin(command)


LOAD_TIMEOUT = 600.0  # s an info page waits for the video it started


def video_start(fullscreen, info_open, seconds):
    """'up' once the video is in front, 'wait' while the info page is open (Kodi can take a
    minute before the player even has media: a busy box, a slow server, a 2160p file over
    HTTPS and the jump to the resume point), 'failed' once the user closed the info page or
    after LOAD_TIMEOUT."""
    if fullscreen:
        return 'up'
    if not info_open or seconds >= LOAD_TIMEOUT:
        return 'failed'
    return 'wait'


def _wait_for_video():
    """Wait for the video started from an info page (video_start); True once it is up."""
    import xbmc
    monitor, seconds, step = _monitor(), 0.0, 0.1
    while True:
        state = video_start(xbmc.getCondVisibility('Window.IsActive(fullscreenvideo)'),
                            xbmc.getCondVisibility('Window.IsActive(movieinformation)'), seconds)
        if state != 'wait':
            return state == 'up'
        if monitor.waitForAbort(step):
            return False
        seconds += step


def play(mediatype, dbid, mode='resume'):
    """Play a library item from its info page. PlayMedia(path,resume) cannot resume a plugin
    path, Player.Open with the database id uses the library's resume point. The info page stays
    until the video is up (closing it first shows Home while the box starts playback) and closes
    then, as Kodi would draw it over the video. For an episode it comes back after playback."""
    import xbmc
    params = player_open_params(mediatype, dbid, mode)
    if params is None:
        return
    home = _home()
    if chain_running(home):
        # the manager would take the closing info dialog for Back and reopen the page below
        _chain_exit(home)
    _rpc('Player.Open', **params)
    if not _wait_for_video():
        _log('play: {} {} did not start, or the info page was closed'.format(mediatype, dbid))
        return
    xbmc.executebuiltin('Dialog.Close(movieinformation,true)')
    if mediatype == 'episode':
        _return_to_episode(int(dbid))


STOP_GRACE = 0.1  # s without media after a stop before the playback counts as over
END_GRACE = 15.0  # s after a file ended for the next one to start (NAS, plugin, refresh rate)
OTHER_GRACE = 10.0  # s of non-episode video after an episode before following gives up


def playback_over(idle, stopped):
    """Whether `idle` seconds without media end the playback: soon after a stop, only after
    END_GRACE when a file ended and the next may still be starting."""
    return idle >= (STOP_GRACE if stopped else END_GRACE)


class EpisodeFollower:
    """Follows a playback started from an episode's info page, one tick per poll. tick returns
    'follow', 'done' (playback over, `last` is the episode that played last) or 'abort' (other
    video took over). Intros or a plugin's placeholder before the episode do not end it, and
    while media is loaded (a stopped placeholder, the next file loading) it keeps following."""

    def __init__(self, dbid):
        self.last = int(dbid)
        self.idle = 0.0
        self.other = 0.0
        self.seen_episode = False

    def tick(self, has_media, has_video, is_episode, playing_dbid, stopped, seconds):
        if has_media:
            self.idle = 0.0
        else:
            self.idle += seconds
            return 'done' if playback_over(self.idle, stopped) else 'follow'
        if has_video and is_episode:
            self.other = 0.0
            self.seen_episode = True
            if str(playing_dbid).isdigit():
                self.last = int(playing_dbid)
        elif has_video and self.seen_episode:
            self.other += seconds
            if self.other >= OTHER_GRACE:
                return 'abort'
        return 'follow'


def _log(message):
    import xbmc
    xbmc.log('nightcity: ' + message, xbmc.LOGINFO)


def _return_to_episode(dbid):
    """Follow the playback started from an episode's info page (EpisodeFollower) and, once it
    is over, open the info page again on the episode that played last. Waits for dialogs that
    come up after the stop (delete, up next) to close; gives up when other video took over or
    something else than Home or the library is in front. While it follows, Home shows only the
    backdrop once no video plays (nc.returning; set before the stop, as the stop callback comes
    after Kodi left the player; the info page clears it on load). Every decision goes to kodi.log."""
    import xbmc
    home = _home()

    class Player(xbmc.Player):
        stopped = False

        def onPlayBackStopped(self):
            Player.stopped = True

        def onAVStarted(self):
            Player.stopped = False

    import time
    # only the newest follower acts: an older one (another episode started meanwhile) stops
    token = '{}:{}'.format(dbid, time.time())
    home.setProperty('nc.follow', token)
    monitor, player = _monitor(), Player()
    try:
        if _follow(dbid, monitor, player, home, token=token) is False:
            home.clearProperty('nc.returning')
    except Exception:
        home.clearProperty('nc.returning')
        raise


def _follow(dbid, monitor, player, home, token=None):
    """The body of _return_to_episode; True once the info page is being opened, None when a
    newer playback took over (its follower owns nc.returning then), False otherwise."""
    import xbmc
    if not _wait('Player.HasMedia', timeout=30):
        _log('return: playback of episode {} did not start'.format(dbid))
        return False
    home.setProperty('nc.returning', '1')
    # polls fast once stopped: Jellyfin add-ons keep every script waiting for seconds a moment
    # after the stop, the info page has to be on its way before that
    follower, result, step = EpisodeFollower(dbid), 'follow', 0.5
    while result == 'follow':
        if monitor.waitForAbort(step):
            return False
        if token and home.getProperty('nc.follow') != token:
            _log('return: a newer playback follows, episode {} steps aside'.format(dbid))
            return None
        has_media = xbmc.getCondVisibility('Player.HasMedia')
        result = follower.tick(has_media, xbmc.getCondVisibility('Player.HasVideo'),
                               xbmc.getCondVisibility('VideoPlayer.Content(episodes)'),
                               xbmc.getInfoLabel('VideoPlayer.DBID'), player.stopped, step)
        step = 0.1 if player.stopped or not has_media else 0.5
        fanart = xbmc.getInfoLabel('Player.Art(tvshow.fanart)') or xbmc.getInfoLabel('Player.Art(fanart)')
        if fanart:
            home.setProperty('nc.returning.fanart', fanart)
    _log('return: playback {} (stopped {}), last episode {}'.format(result, player.stopped, follower.last))
    if result != 'done':
        return False
    # a dialog after the stop (delete, up next, a plugin's question): wait until it closed; an
    # info page is one the user opened meanwhile, keep it
    if not _wait('[!System.HasActiveModalDialog | Window.IsActive(movieinformation)] + !Window.IsActive(fullscreenvideo)',
                 timeout=30):
        _log('return: a dialog or the player stayed in front, not opening the info page')
        return False
    if xbmc.getCondVisibility('Window.IsActive(movieinformation)'):
        _log('return: an info page is open already')
        return False
    if token and home.getProperty('nc.follow') != token:
        _log('return: a newer playback follows, episode {} steps aside'.format(dbid))
        return None
    import time
    if info_claimed(home.getProperty('nc.info.opening'), time.time()):
        _log('return: another script is opening an info page')
        return False
    if chain_running(home):
        _log('return: TMDb Helper runs a chain of info pages')
        return False
    if xbmc.getCondVisibility('Player.HasMedia'):
        _log('return: something plays again, not opening the info page')
        return False
    if not xbmc.getCondVisibility('Window.IsActive(home) | Window.IsActive(videos)'):
        _log('return: window {} is in front, not opening the info page'.format(xbmc.getInfoLabel('System.CurrentWindow')))
        return False
    _log('return: opening the info page of episode {}'.format(follower.last))
    _claim_info()
    _episode_info(follower.last)
    return True


def _episode_info(episodeid):
    import xbmcgui
    episode = _rpc('VideoLibrary.GetEpisodeDetails', episodeid=episodeid,
                   properties=['file', 'title'])['episodedetails']
    item = xbmcgui.ListItem(episode['title'], path=episode['file'])
    tag = item.getVideoInfoTag()
    tag.setDbId(episode['episodeid'])
    tag.setMediaType('episode')
    xbmcgui.Dialog().info(item)


def info(mediatype, dbid):
    """Replace the open info page with the one of a library movie. Action(Info) on the info page
    closes it instead of opening the focused item. In a running chain the movie goes onto the
    manager's stack."""
    import xbmc
    import xbmcgui
    if mediatype != 'movie' or not dbid:
        return
    home = _home()
    if chain_running(home):
        _chain_push(home, chain_path('movie', dbid))
        return
    _claim_info()
    movie = _rpc('VideoLibrary.GetMovieDetails', movieid=int(dbid), properties=['file', 'title'])['moviedetails']
    item = xbmcgui.ListItem(movie['title'], path=movie['file'])
    tag = item.getVideoInfoTag()
    tag.setDbId(movie['movieid'])
    tag.setMediaType('movie')
    xbmc.executebuiltin('Dialog.Close(movieinformation,true)', True)
    xbmcgui.Dialog().info(item)


def _language_name(code):
    import xbmc
    return xbmc.convertLanguage(code, xbmc.ENGLISH_NAME) if code else ''


def _player_streams():
    return _rpc('Player.GetProperties', playerid=1, properties=[
        'audiostreams', 'currentaudiostream', 'subtitles', 'currentsubtitle', 'subtitleenabled'])


def _panel(kind):
    import xbmc
    words = {'off': xbmc.getInfoLabel('$LOCALIZE[31138]'), 'more': xbmc.getInfoLabel('$LOCALIZE[31139]')}
    return panel(kind, _player_streams(), _language_name, words)


def _set_rows(home, kind, rows):
    old = int(home.getProperty('nc.{}.count'.format(kind)) or 0)
    for n, row in enumerate(rows, 1):
        for key in ('label', 'tag', 'current'):
            home.setProperty('nc.{}.{}.{}'.format(kind, n, key), row[key])
    for n in range(len(rows) + 1, old + 1):
        for key in ('label', 'tag', 'current'):
            home.clearProperty('nc.{}.{}.{}'.format(kind, n, key))
    home.setProperty('nc.{}.count'.format(kind), str(len(rows)))
    home.setProperty('nc.{}.rows'.format(kind), str(min(len(rows), PANEL_ROWS)))
    home.setProperty('nc.{}.pos'.format(kind), str(current_position(rows)))


def streams():
    """Fill the track panels of the OSD: nc.audio.* and nc.sub.* (Home), one entry per row."""
    home = _home()
    for kind in ('audio', 'sub'):
        _set_rows(home, kind, _panel(kind))


CHAPTER_THUMBS = 64  # chapters the skin maps to nc.chapter.N (ChapterServerThumb, Variables.xml)
JELLYFIN_STREAM = re.compile(r'^(https?://.+?)/Videos/([0-9a-fA-F-]{32,36})/')


def chapter_source(path):
    """(server address, item id) of a stream from a Jellyfin server, else None."""
    match = JELLYFIN_STREAM.match(path or '')
    return match.groups() if match else None


def chapter_thumbs(source, count):
    """The server's chapter images of chapters 1..count; the server counts from 0."""
    return ['{}/Items/{}/Images/Chapter/{}'.format(source[0], source[1], n) for n in range(count)]


def set_chapter_thumbs(home, path, count, probe):
    """Kodi cuts no chapter thumbnails from http streams. For a Jellyfin stream the server's
    images go into nc.chapter.N, if it has any (probe: one image request); nc.chapters.remote
    marks a stream, whose chapters without images show as compact cards."""
    thumbs = []
    if path.startswith(('http://', 'https://')):
        home.setProperty('nc.chapters.remote', '1')
        source = chapter_source(path)
        if source and count:
            thumbs = chapter_thumbs(source, min(count, CHAPTER_THUMBS))
            if not probe(thumbs[0]):
                thumbs = []
    else:
        home.clearProperty('nc.chapters.remote')
    for n in range(1, CHAPTER_THUMBS + 1):
        if n <= len(thumbs):
            home.setProperty('nc.chapter.{}'.format(n), thumbs[n - 1])
        else:
            home.clearProperty('nc.chapter.{}'.format(n))


def _image_exists(url):
    """Whether the server has the image: chapter images are only there when the library
    extracts them. Image requests need no login."""
    import urllib.request
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def chapter_images(home):
    """Server chapter images of the playing stream (set_chapter_thumbs), once per stream: the
    path of a Jellyfin stream carries its playback session."""
    import xbmc
    try:
        # what Kodi plays and cuts thumbnails from: the stream a plugin path resolved to
        path = xbmc.Player().getPlayingFile()
    except RuntimeError:
        return
    if not path or home.getProperty('nc.chapters.file') == path:
        return
    count = int(xbmc.getInfoLabel('Player.ChapterCount') or 0)
    set_chapter_thumbs(home, path, count, _image_exists)
    home.setProperty('nc.chapters.file', path)


def streams_watch():
    """Fill the track panels and keep them current while the OSD is open, so a track switched
    by a remote key moves the marker. One run per OSD: a newer run ends an older one."""
    import time
    import xbmc
    home, monitor = _home(), _monitor()
    token = str(time.time())
    home.setProperty('nc.osd.watch', token)
    shown = {}
    # the chapter row (VideoOSDBookmarks.xml) opens from the OSD: its server images load beside
    # the panels, in this interpreter, not in one of their own
    import threading
    chapters = threading.Thread(target=chapter_images, args=(home,))
    chapters.start()
    while home.getProperty('nc.osd.watch') == token and not monitor.abortRequested():
        if not xbmc.getCondVisibility('Window.IsActive(videoosd) + Player.HasVideo'):
            break
        for kind in ('audio', 'sub'):
            rows = _panel(kind)
            if rows != shown.get(kind):
                _set_rows(home, kind, rows)
                shown[kind] = rows
        if monitor.waitForAbort(0.5):
            break
    chapters.join()


def row(kind, n):
    """Run row n (1 = first) of the track panel `kind`, then refresh the panels."""
    import xbmc
    rows = _panel(kind)
    if not 1 <= int(n) <= len(rows):
        return
    what, value = rows[int(n) - 1]['action']
    if what == 'audio':
        _rpc('Player.SetAudioStream', playerid=1, stream=value)
    elif what == 'subtitle' and value == 'off':
        _rpc('Player.SetSubtitle', playerid=1, subtitle='off')
    elif what == 'subtitle':
        _rpc('Player.SetSubtitle', playerid=1, subtitle=value, enable=True)
    else:
        xbmc.executebuiltin('ActivateWindow({})'.format(value))
        return
    # the player applies a switch a moment later; refresh once the clicked row is current
    monitor = _monitor()
    for _ in range(20):
        if row_is_current(_panel(kind), int(n)) or monitor.waitForAbort(0.1):
            break
    streams()


def _search_file():
    import xbmcvfs
    folder = xbmcvfs.translatePath('special://profile/addon_data/skin.nightcity/')
    xbmcvfs.mkdirs(folder)
    return folder + 'search.json'


def _search_history():
    try:
        with open(_search_file(), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def _show_search(home, term, history, stagger=False):
    """Fill the search page. With stagger (a new search on the open page) the TMDb tv search
    follows TMDB_STAGGER later; entering the page, its timer staggers them."""
    import xbmc
    first, second = search_batches(term) if stagger else (search_paths(term), {})
    home.setProperty('nc.search', term)
    for kind, path in first.items():
        home.setProperty('nc.search.{}'.format(kind), path)
    for n in range(1, RECENT + 1):
        home.setProperty('nc.search.recent.{}'.format(n), history[n - 1] if n <= len(history) else '')
    if second and not _monitor().waitForAbort(TMDB_STAGGER):
        for kind, path in second.items():
            home.setProperty('nc.search.{}'.format(kind), path)


def search(term=None):
    """Search the library and TMDb for `term`, or for what the keyboard returns without one, and
    remember the term. Fills nc.search (the term), nc.search.<row> (content paths) and
    nc.search.recent.1-5 on Home."""
    import xbmc
    home = _home()
    if term is None:
        import xbmcgui
        term = xbmcgui.Dialog().input(xbmc.getInfoLabel('$LOCALIZE[31032]'), home.getProperty('nc.search'))
    term = (term or '').strip()
    if not term:
        return
    if xbmc.getCondVisibility('Skin.HasSetting(nc.search.forget)'):
        history = []
    else:
        history = remember(_search_history(), term)
        with open(_search_file(), 'w', encoding='utf-8') as f:
            json.dump(history, f)
    _show_search(home, term, history, stagger=True)


def search_clear():
    """Forget the remembered terms (skin settings, main menu)."""
    import os
    try:
        os.remove(_search_file())
    except OSError:
        pass
    home = _home()
    for n in range(1, RECENT + 1):
        home.setProperty('nc.search.recent.{}'.format(n), '')


def search_forget():
    """After the remember switch: switched off, the remembered terms go too."""
    import xbmc
    if xbmc.getCondVisibility('Skin.HasSetting(nc.search.forget)'):
        search_clear()


OSD_HIDE_MIN, OSD_HIDE_MAX, OSD_HIDE_DEFAULT = 3, 30, 8
OSD_HIDE_NIB = 8  # width of the slider's nib in percent of its bar


def osd_hide_values(current, step):
    """(seconds, wait, nib from, nib to) after moving the delay slider of the player controls
    by STEP from CURRENT (default 8 s), within 3 to 30 s. The timer nc_osd_hide counts from a
    second after the last key, so it waits a second less. The slider is a progress bar whose
    fill from..to (percent) is the nib."""
    try:
        secs = int(current)
    except ValueError:
        secs = OSD_HIDE_DEFAULT
    secs = max(OSD_HIDE_MIN, min(OSD_HIDE_MAX, secs + int(step)))
    start = int((secs - OSD_HIDE_MIN) * (100 - OSD_HIDE_NIB) / (OSD_HIDE_MAX - OSD_HIDE_MIN) + 0.5)
    return secs, secs - 1, start, start + OSD_HIDE_NIB


def osd_hide(current, step):
    """The delay slider in the skin settings (Player): move it by STEP seconds."""
    import xbmc
    for name, value in zip(('secs', 'wait', 'from', 'to'), osd_hide_values(current, step)):
        xbmc.executebuiltin('Skin.SetString(nc.osd.hide.{},{})'.format(name, value))


def colour_choices(files, current):
    """(values, labels, index of current) of the colour schemes in the skin's colors folder, as
    Kodi's lookandfeel.skincolors names them: SKINDEFAULT for defaults.xml, else the file name."""
    names = sorted(f[:-4] for f in files if f.endswith('.xml') and f != 'defaults.xml')
    values = ['SKINDEFAULT'] + names
    labels = ['Default'] + [n.capitalize() for n in names]
    return values, labels, values.index(current) if current in values else 0


def colours():
    """Pick the colour scheme from the skin settings: Kodi keeps the choice under Interface."""
    import os
    import xbmc
    import xbmcgui
    import xbmcvfs
    files = os.listdir(xbmcvfs.translatePath('special://skin/colors'))
    current = _rpc('Settings.GetSettingValue', setting='lookandfeel.skincolors')['value']
    values, labels, index = colour_choices(files, current)
    chosen = xbmcgui.Dialog().select(xbmc.getLocalizedString(14078), labels, preselect=index)
    if chosen >= 0 and values[chosen] != current:
        _rpc('Settings.SetSettingValue', setting='lookandfeel.skincolors', value=values[chosen])


def search_recent(n):
    """Search again for remembered term n (1 = latest)."""
    history = _search_history()
    if 1 <= int(n) <= len(history):
        search(history[int(n) - 1])


def search_init():
    """Show the remembered terms on the search page (Home onload); keeps a running search."""
    home = _home()
    _show_search(home, home.getProperty('nc.search'), _search_history())



def home():
    """Everything Home needs when it loads, in one script run: genre tabs and search history."""
    genres()
    search_init()


# Kodi restarts itself only on Windows and Linux (CoreELEC, LibreELEC, Android count as Linux)
# Kodi settings the skin sets once (skin bool that marks it done, setting, value): select opens
# the info page; chapters get thumbnails for the OSD's chapter row
ONE_OFF = (('nc.selectaction.done', 'myvideos.selectaction', 3),
           ('nc.chapterthumbs.done', 'myvideos.extractchapterthumbs', True))


# The Home key opens Custom_1160_HomeKey (closes every dialog, then the home page). Kodi's own
# Home keys: homepage on keyboards, IR and Bluetooth remotes, rootmenu on CEC and MCE remotes.
# Global only, window sections keep theirs (the player's rootmenu opens the OSD). Kodi loads
# userdata keymaps in name order and later ones win, so the user's own come after this one.
# Home held opens Kodi's power menu, which the skin turns into its quick menu (DialogButtonMenu.xml,
# Custom_1170_QuickMenu.xml). Kodi knows long presses only in the keyboard section; with one
# mapped, a short press acts when the key is released.
HOME_KEYMAP_NAME = '0_skin.nightcity.xml'
HOME_KEYMAP = """<?xml version="1.0" encoding="UTF-8"?>
<!-- Written by the Nightcity skin (skin settings: Home key). -->
<keymap>
  <global>
    <keyboard>
      <homepage>ActivateWindow(1160)</homepage>
      <homepage mod="longpress">ActivateWindow(shutdownmenu)</homepage>
      <browser_home>ActivateWindow(1160)</browser_home>
      <browser_home mod="longpress">ActivateWindow(shutdownmenu)</browser_home>
      <!-- home alone stays FirstPage in lists (Kodi's keyboard.xml); some IR remotes send it -->
      <home mod="longpress">ActivateWindow(shutdownmenu)</home>
    </keyboard>
    <remote>
      <rootmenu>ActivateWindow(1160)</rootmenu>
    </remote>
  </global>
</keymap>
"""


# Esc on keyboards, a gamepad's back button and a right click send PreviousMenu, not Back, and
# <onback> sees only Back. On an info page in a TMDb chain the page must not close in its first
# second (ChainBackGuard, Includes_Tmdb.xml), so on info pages these keys are Back too: for Kodi
# both close the page. Written whatever the Home key setting.
BACK_KEYMAP_NAME = '0_skin.nightcity.back.xml'
BACK_KEYMAP = """<?xml version="1.0" encoding="UTF-8"?>
<!-- Written by the Nightcity skin: on info pages the keys of PreviousMenu are Back. -->
<keymap>
  <movieinformation>
    <keyboard>
      <escape>Back</escape>
    </keyboard>
    <gamepad>
      <back>Back</back>
    </gamepad>
    <mouse>
      <rightclick>Back</rightclick>
    </mouse>
  </movieinformation>
</keymap>
"""


# The keymaps of skin.retrowave, the skin's name before 0.4.45
OLD_KEYMAP_NAMES = ('0_skin.retrowave.xml', '0_skin.retrowave.back.xml')


def write_keymap(path, text):
    """Write `text` to the keymap file `path`, or remove it when `text` is None; True when the
    file changed."""
    import os
    current = None
    if os.path.exists(path):
        with open(path) as f:
            current = f.read()
    if text is None:
        if current is None:
            return False
        os.remove(path)
        return True
    if current == text:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(text)
    return True


def write_home_keymap(path, off):
    """Write the Home key keymap to `path`, or remove it when `off`; True when the file changed."""
    return write_keymap(path, None if off else HOME_KEYMAP)


def home_keymap():
    """Apply the skin setting nc.homekey.off to the keymap, write the back keymap and remove the
    keymaps of skin.retrowave; Kodi reloads its keymaps on a change."""
    import os
    import xbmc
    import xbmcvfs
    folder = xbmcvfs.translatePath('special://profile/keymaps/')
    off = xbmc.getCondVisibility('Skin.HasSetting(nc.homekey.off)')
    changed = write_home_keymap(os.path.join(folder, HOME_KEYMAP_NAME), off)
    changed = write_keymap(os.path.join(folder, BACK_KEYMAP_NAME), BACK_KEYMAP) or changed
    for name in OLD_KEYMAP_NAMES:
        changed = write_keymap(os.path.join(folder, name), None) or changed
    if changed:
        xbmc.executebuiltin('Action(reloadkeymaps)')


# The skin was skin.retrowave before 0.4.45: Kodi keeps skin settings per add-on id
OLD_SETTINGS = 'special://profile/addon_data/skin.retrowave/settings.xml'


def old_settings_builtins(text):
    """Builtins that set the skin.retrowave settings in TEXT (its settings.xml) on this skin:
    rw.* become nc.*, unset ones stay at their default."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    builtins = []
    for setting in root.iter('setting'):
        name, value = setting.get('id', ''), setting.text or ''
        if name.startswith('rw.'):
            name = 'nc.' + name[3:]
        if setting.get('type') == 'bool' and value == 'true':
            builtins.append('Skin.SetBool({})'.format(name))
        elif setting.get('type') == 'string' and value:
            builtins.append('Skin.SetString({},"{}")'.format(
                name, value.replace('\\', '\\\\').replace('"', '\\"')))
    return builtins


def take_old_settings():
    """Once: the settings of skin.retrowave, if it ran in this profile."""
    import xbmc
    import xbmcvfs
    if xbmc.getCondVisibility('Skin.HasSetting(nc.migrated)'):
        return
    try:
        with open(xbmcvfs.translatePath(OLD_SETTINGS), encoding='utf-8') as f:
            text = f.read()
    except OSError:
        text = ''
    for builtin in old_settings_builtins(text):
        xbmc.executebuiltin(builtin)
    xbmc.executebuiltin('Skin.SetBool(nc.migrated)')


def startup():
    """One-off settings, then nc.startup.ready: the Startup screen hands over to Home once it is
    set (nc_startup timer). The service runs this first, then listens for the skin."""
    import xbmc
    try:
        take_old_settings()
        for done, setting, value in ONE_OFF:
            if xbmc.getCondVisibility('Skin.HasSetting({})'.format(done)):
                continue
            _rpc('Settings.SetSettingValue', setting=setting, value=value)
            xbmc.executebuiltin('Skin.SetBool({})'.format(done))
        home_keymap()
    finally:
        _home().setProperty('nc.startup.ready', '1')


# --- music ------------------------------------------------------------------------------------

MUSIC_ITEMS = {'album': 'albumid', 'artist': 'artistid', 'song': 'songid'}
MUSIC_INFO_PATHS = {'album': 'musicdb://albums/{}/', 'artist': 'musicdb://artists/{}/'}


def _music_id(dbid):
    try:
        number = int(dbid)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def music_queue_item(kind, dbid):
    """The Playlist.Add item of a library album, artist (all its songs) or song, else None."""
    number = _music_id(dbid)
    return {MUSIC_ITEMS[kind]: number} if kind in MUSIC_ITEMS and number else None


def music_start_position(position):
    """Playlist position (from 0) of the list position the skin sends (Container.CurrentItem,
    from 1); the first track when it is missing."""
    try:
        return max(int(position) - 1, 0)
    except ValueError:
        return 0


def music_info_path(kind, dbid):
    """The musicdb path Kodi's music info dialog takes the album or artist from, else None."""
    number = _music_id(dbid)
    return MUSIC_INFO_PATHS[kind].format(number) if kind in MUSIC_INFO_PATHS and number else None


def music_play(kind, dbid, position='1'):
    """Play an album (an artist: all its songs) from the track at POSITION of the info page's
    list and show the player screen. Kodi's play button (8) only plays from the first track.
    Started on an album or artist page, Back on the player screen opens that page again
    (music_back); started elsewhere (the Music page) it lands where Kodi was."""
    import xbmc
    item = music_queue_item(kind, dbid)
    if item is None:
        return
    home = _home()
    if xbmc.getCondVisibility('Window.IsActive(musicinformation)'):
        home.setProperty(MUSIC_BACK, '{}:{}'.format(kind, dbid))
    else:
        home.clearProperty(MUSIC_BACK)
    xbmc.executebuiltin('Dialog.Close(musicinformation,true)')
    _rpc('Playlist.Clear', playlistid=0)
    _rpc('Playlist.Add', playlistid=0, item=item)
    _rpc('Player.Open', item={'playlistid': 0, 'position': music_start_position(position)})
    xbmc.executebuiltin('ActivateWindow(visualisation)')


MUSIC_BACK = 'nc.music.back'  # the album or artist page music was started on: kind:dbid
MUSIC_START = 3.0  # s from a cleared music queue to the playback that counts as started anew


class MusicStart:
    """Tells a new music playback from the next track of the queue: Kodi fills the music queue
    anew before it plays something new (the library, Kodi's own play buttons, music_play): it
    clears it (no notice when it was empty) and adds from position 0. Not before the next
    track."""

    def __init__(self):
        self.cleared = None

    def notice(self, method, data, now):
        """True when METHOD (a Kodi notification with DATA, a dict) starts music anew."""
        if data.get('playlistid') == 0 and (method == 'Playlist.OnClear' or (
                method == 'Playlist.OnAdd' and data.get('position') == 0)):
            self.cleared = now
            return False
        if method == 'Player.OnPlay' and (data.get('player') or {}).get('playerid') == 0:
            started = self.cleared is not None and now - self.cleared <= MUSIC_START
            self.cleared = None
            return started
        return False


def now_playing():
    """Show the player screen for music that just started (the library, Kodi's play button on a
    song page). Started from the library, Back on it goes back there (Kodi's window before)."""
    import xbmc
    # Kodi tells of the playback before the player has it
    if not _wait('Player.HasAudio', 5.0) or xbmc.getCondVisibility(
            'Window.IsActive(visualisation) | Player.HasVideo'):
        return
    if xbmc.getCondVisibility('Window.IsActive(musicinformation)'):
        xbmc.executebuiltin('Dialog.Close(musicinformation,true)')
    _home().clearProperty(MUSIC_BACK)
    # Kodi ignores the window while its busy dialog is up (a stream starting)
    _wait('!Window.IsActive(busydialog) + !Window.IsActive(busydialognocancel)', 10.0)
    xbmc.executebuiltin('ActivateWindow(visualisation)')


class Debounce:
    """Runs ACTION once a burst of changes is over (DELAY s without a new one): Kodi tells of
    every item it adds to a queue on its own."""

    def __init__(self, action, delay=0.5):
        self.action, self.delay, self.count = action, delay, 0

    def changed(self):
        import threading
        self.count += 1
        timer = threading.Timer(self.delay, self._fire, args=(self.count,))
        timer.daemon = True
        timer.start()

    def _fire(self, count):
        if count == self.count:
            self.action()


MUSIC_QUEUE_ALBUM = 'nc.music.queue.album'  # set while the music queue holds one album
MUSIC_QUEUE_LISTS = ('700', '701')  # the music OSD's queue: cards, lines


def queue_one_album(items):
    """True when the queue ITEMS (Playlist.GetItems with albumid) all come from one album."""
    albums = {item.get('albumid') for item in items}
    return len(albums) == 1 and bool(albums.pop())


def music_queue():
    """Note whether the music queue holds one album (MUSIC_QUEUE_ALBUM): the OSD shows its
    tracks as lines then, else cards with covers. On every change of the queue (the service)."""
    try:
        items = _rpc('Playlist.GetItems', playlistid=0, properties=['albumid']).get('items') or []
    except RuntimeError:
        items = []
    home = _home()
    if queue_one_album(items):
        home.setProperty(MUSIC_QUEUE_ALBUM, '1')
    else:
        home.clearProperty(MUSIC_QUEUE_ALBUM)


def queue_move(playing, current):
    """The Control.Move step that takes a list from item CURRENT (from 1) to the PLAYING
    position (from 0), or 0."""
    try:
        return int(playing) + 1 - int(current)
    except (TypeError, ValueError):
        return 0


def music_queue_select():
    """The music OSD opened (MusicOSD.xml onload): put the queue's cursor on the playing track,
    without the focus (the buttons keep it), once the shown list is in."""
    import xbmc
    music_queue()
    if not _wait('Integer.IsGreater(Container(700).NumItems,0) | Integer.IsGreater(Container(701).NumItems,0)', 3.0):
        return
    try:
        playing = _rpc('Player.GetProperties', playerid=0, properties=['position'])['position']
    except (RuntimeError, KeyError):
        return
    for list_id in MUSIC_QUEUE_LISTS:
        current = xbmc.getInfoLabel('Container({}).CurrentItem'.format(list_id))
        step = queue_move(playing, current) if current else 0
        if step:
            xbmc.executebuiltin('Control.Move({},{})'.format(list_id, step))


def music_back():
    """The player screen closed (MusicVisualisation.xml onunload): when its music was started on
    an album or artist page, open that page again over the window below."""
    home = _home()
    point = home.getProperty(MUSIC_BACK)
    home.clearProperty(MUSIC_BACK)
    kind, _, dbid = point.partition(':')
    if music_info_path(kind, dbid) is None:
        return
    if not _wait('!Window.IsActive(visualisation) + [Window.IsActive(home) | Window.IsActive(music)]'
                 ' + !System.HasActiveModalDialog', 3.0):
        _log('music_back: no way back to the {} page {}'.format(kind, dbid))
        return
    music_info(kind, dbid)


def music_goto(position):
    """Jump to the track at POSITION (from 1) of the playing queue (the OSD's up next row)."""
    _rpc('Player.GoTo', playerid=0, to=music_start_position(position))


MUSIC_DETAILS = {'album': ('AudioLibrary.GetAlbumDetails', 'albumid'),
                 'artist': ('AudioLibrary.GetArtistDetails', 'artistid')}


def music_info(kind, dbid):
    """Replace the open music info page with the one of a library album or artist: Action(Info)
    on the info page closes it instead. Kodi takes the item from the musicdb path."""
    import xbmc
    import xbmcgui
    path = music_info_path(kind, dbid)
    if path is None:
        return
    item = xbmcgui.ListItem(path=path)
    item.setIsFolder(True)
    item.getMusicInfoTag()
    # Kodi loads the tags from the path but not the art (the backdrop: the artist's fanart)
    method, key = MUSIC_DETAILS[kind]
    try:
        item.setArt(_rpc(method, properties=['art'], **{key: int(dbid)})[kind + 'details'].get('art', {}))
    except (RuntimeError, KeyError):
        pass
    xbmc.executebuiltin('Dialog.Close(musicinformation,true)')
    _wait('!Window.IsActive(musicinformation)', 2.0)
    xbmcgui.Dialog().info(item)


# --- ratings kept per title -------------------------------------------------------------------
# TMDb Helper fetches ratings for the item of TMDbHelper.WidgetContainer and lets go of it when
# that goes. On Home the service points it at the hero's spotlight (9000 movies, 9001 shows)
# while a hero button has focus, or always with "load without focus" (nc.ratings.spotlight); an
# episode's info page points it at its episode list itself (DialogVideoInfo.xml, 5100). The
# service keeps what TMDb Helper fetched per title for the session and shows the kept ratings of
# the item on screen in nc.kept.<container>.*, which the ratings line reads: they stay once
# fetched, also when the spotlight or the list comes back to a title.

HERO_SOURCES = ('IMDb_Rating', 'Top250', 'TMDb_Rating', 'RottenTomatoes_Rating', 'RottenTomatoes_UserMeter',
                'MetaCritic_Rating', 'Trakt_Rating', 'Letterboxd_Rating', 'MDBList_Rating')
# for an episode TMDb Helper gives these for the episode itself, the others are the show's
EPISODE_SOURCES = ('IMDb_Rating', 'Trakt_Rating')
HERO_STABLE = 0.8  # s TMDb Helper's ratings stay before they count: they lag behind its title
HERO_POLL = 0.25  # s between two looks
HERO_PROPS = 'nc.kept.{}.{}'
# container of the spotlight, the group on screen with its hero, the group of its buttons
HEROES = (('9000', '9300', '9050'), ('9001', '9301', '9550'))
# what names a title: (property name, ListItem info); the last one guards the line
HERO_KEY = (('dbtype', 'DBType'), ('dbid', 'DBID'))
EPISODE_KEY = (('label', 'Label'), ('season', 'Season'), ('episode', 'Episode'))
HERO_ON_HOME = 'Window.IsActive(home)'
HERO_DIALOG = 'System.HasActiveModalDialog'
HERO_SHOWN = 'Control.IsVisible({})'
HERO_FOCUS = 'ControlGroup({}).HasFocus()'
HERO_WITHOUT_FOCUS = 'Skin.HasSetting(nc.ratings.spotlight)'
INFO_EPISODES = ('Window.IsActive(movieinformation) + '
                 'String.IsEqual(Window(movieinformation).Property(TMDbHelper.WidgetContainer),5100)')


def hero_widget_container(container, focused, without_focus):
    """What TMDbHelper.WidgetContainer should be: the hero's spotlight CONTAINER ('' none) while
    a hero button has focus, or always WITHOUT_FOCUS."""
    return container if container and (focused or without_focus) else ''


def episode_ratings(props):
    """The ratings of an episode from TMDb Helper's properties PROPS ({name: value}): IMDb and
    Trakt as they are, TMDb from the episode's own vote (Rating, one decimal); the others are
    the show's and stay out."""
    ratings = {s: props.get(s, '') if s in EPISODE_SOURCES else '' for s in HERO_SOURCES}
    try:
        ratings['TMDb_Rating'] = '{:.1f}'.format(float(props.get('Rating') or ''))
    except ValueError:
        pass
    return ratings


class HeroRatings:
    """The ratings TMDb Helper fetched, kept per title: a key of (name, value) pairs."""

    def __init__(self):
        self.cache = {}
        self.pending = None  # (key, ratings, since)
        self.shown = {}  # container -> (key, what nc.kept.<container>.* hold now)

    def seen(self, key, ratings, now):
        """TMDb Helper is done with title KEY and has RATINGS ({source: value}); None: busy or on
        another title. True when they are kept: they stayed HERO_STABLE s, and the title had none
        kept yet (or only empty ones), so the line does not swap its content."""
        if key is None:
            self.pending = None
            return False
        if self.pending is None or self.pending[:2] != (key, ratings):
            self.pending = (key, ratings, now)
            return False
        if now - self.pending[2] < HERO_STABLE:
            return False
        old = self.cache.get(key)
        if old is not None and (any(old.values()) or not any(ratings.values())):
            return False
        self.cache[key] = dict(ratings)
        return True

    def changes(self, container, key):
        """[(property, value)] that make nc.kept.<CONTAINER>.* hold the kept ratings of title KEY
        (None: no title), '' clears. The key's last field goes first and comes back last: the
        line only shows while it names the item on screen."""
        want = dict(self.cache[key], **dict(key)) if key in self.cache else {}
        old_key, now = self.shown.get(container, (None, {}))
        out = []
        guard = old_key[-1][0] if old_key else None
        if guard and now.get(guard) and old_key != key:
            out.append((guard, ''))
            now = dict(now, **{guard: ''})
        names = [n for n, _ in key or ()]
        names = [n for n, _ in old_key or () if n not in names] + names
        for name in HERO_SOURCES + tuple(names):
            if want.get(name, '') != now.get(name, ''):
                out.append((name, want.get(name, '')))
        self.shown[container] = (key if want else None, {k: v for k, v in want.items() if v})
        return [(HERO_PROPS.format(container, name), value) for name, value in out]


def _hero_same_title(home, dbid, label):
    """TMDb Helper's item is the one on screen: by dbid (extras/tmdbhelper/baseitem.json), by
    label for items without one and a TMDb Helper that started before the skin brought that file."""
    base = home.getProperty('TMDbHelper.ListItem.base_dbid')
    return base == dbid if base and dbid else home.getProperty('TMDbHelper.ListItem.base_label') == label


def _keep(kept, home, container, fields, watched, now):
    """Keep TMDb Helper's ratings of the item of CONTAINER (named by FIELDS) when it WATCHED that
    item and is done with it; show the kept ratings of that item."""
    import xbmc
    item = 'Container({}).ListItem.'.format(container)
    values = tuple((name, xbmc.getInfoLabel(item + info)) for name, info in fields)
    key = values if all(v for _, v in values) else None
    dbtype = xbmc.getInfoLabel(item + 'DBType')
    if watched and key and not home.getProperty('TMDbHelper.IsUpdating') and \
            not home.getProperty('TMDbHelper.IsUpdatingRatings') and \
            home.getProperty('TMDbHelper.ListItem.base_dbtype') == dbtype and \
            _hero_same_title(home, xbmc.getInfoLabel(item + 'DBID'), xbmc.getInfoLabel(item + 'Label')):
        props = {s: home.getProperty('TMDbHelper.ListItem.' + s) for s in HERO_SOURCES + ('Rating',)}
        kept.seen(key, episode_ratings(props) if dbtype == 'episode' else
                  {s: props[s] for s in HERO_SOURCES}, now)
    else:
        kept.seen(None, None, now)
    for name, value in kept.changes(container, key):
        if value:
            home.setProperty(name, value)
        else:
            home.clearProperty(name)


def hero_tick(kept, now):
    """One look: on an episode's info page keep the ratings of the focused episode; on Home point
    TMDb Helper at the hero, keep its ratings, show the kept ones."""
    import xbmc
    home = _home()
    if xbmc.getCondVisibility(INFO_EPISODES):
        _keep(kept, home, '5100', EPISODE_KEY, True, now)
        return
    if not xbmc.getCondVisibility(HERO_ON_HOME):
        if home.getProperty('TMDbHelper.WidgetContainer'):
            home.clearProperty('TMDbHelper.WidgetContainer')
        return
    # the info page of a movie over Home watches its own item
    if xbmc.getCondVisibility(HERO_DIALOG):
        return
    container, buttons = next(((c, b) for c, group, b in HEROES if xbmc.getCondVisibility(HERO_SHOWN.format(group))),
                              ('', ''))
    widget = hero_widget_container(container, bool(buttons) and xbmc.getCondVisibility(HERO_FOCUS.format(buttons)),
                                   xbmc.getCondVisibility(HERO_WITHOUT_FOCUS))
    if home.getProperty('TMDbHelper.WidgetContainer') != widget:
        if widget:
            home.setProperty('TMDbHelper.WidgetContainer', widget)
        else:
            home.clearProperty('TMDbHelper.WidgetContainer')
    if container:
        _keep(kept, home, container, HERO_KEY, bool(widget), now)


def hero_watch(monitor, stop):
    """hero_tick every HERO_POLL s until STOP, Kodi ends or the service goes."""
    import time
    import xbmc
    kept = HeroRatings()
    while not stop.wait(HERO_POLL) and not QUIT.is_set() and not monitor.abortRequested():
        try:
            hero_tick(kept, time.monotonic())
        except Exception as e:  # a failing look must not end the watch
            xbmc.log('nightcity: hero ratings failed: {!r}'.format(e), xbmc.LOGERROR)
            stop.wait(5)


COMMANDS = {'next_episode': next_episode, 'startup': startup, 'genres': genres, 'genre_pick': genre_pick,
            'info_select': info_select, 'info_leave': info_leave, 'info_back': info_back,
            'osd_back': osd_back, 'play': play, 'info': info,
            'streams': streams, 'row': row, 'search': search, 'search_recent': search_recent,
            'search_init': search_init, 'search_clear': search_clear, 'search_forget': search_forget, 'colours': colours,
            'streams_watch': streams_watch, 'section_pick': section_pick,
            'home': home, 'home_keymap': home_keymap, 'osd_hide': osd_hide,
            'music_play': music_play, 'music_goto': music_goto, 'music_info': music_info,
            'music_back': music_back, 'now_playing': now_playing, 'music_queue': music_queue,
            'music_queue_select': music_queue_select}


# --- the skin service -------------------------------------------------------------------------
# Every Python script Kodi starts gets its own interpreter, and two interpreters starting at once
# can crash Kodi. So the skin starts this script once (the Startup screen, or Home when it finds
# no nc.service) and sends it its commands with NotifyAll(nightcity,command:arg:...): they run in
# threads of this one interpreter.

SENDER = 'nightcity'
ADDON_ID = 'skin.nightcity'
_threads = []


def parse_message(sender, method):
    """(command, args) of a NotifyAll(nightcity,command:arg:...) from the skin, else None."""
    if sender != SENDER or not method.startswith('Other.'):
        return None
    parts = method[len('Other.'):].split(':')
    if parts[0] not in COMMANDS or parts[0] == 'service':
        return None
    return parts[0], parts[1:]


def _run(command, args):
    import xbmc
    try:
        COMMANDS[command](*args)
    except Exception as e:  # one command failing must not end the service
        xbmc.log('nightcity: {} {} failed: {!r}'.format(command, args, e), xbmc.LOGERROR)


def run_command(command, args):
    import threading
    thread = threading.Thread(target=_run, args=(command, args), daemon=True)
    _threads.append(thread)
    thread.start()


def wait_for_commands():
    while _threads:
        _threads.pop().join()


def service(*first):
    """Listen for the skin's commands until Kodi ends or another skin takes over; FIRST is a
    command to run before (startup)."""
    import xbmc

    music_start = MusicStart()
    queue_watch = Debounce(lambda: run_command('music_queue', []))

    class Listener(xbmc.Monitor):
        def onNotification(self, sender, method, data):
            if sender == 'xbmc' and method == 'System.OnQuit':
                QUIT.set()
            if sender == 'xbmc' and method in ('Playlist.OnClear', 'Playlist.OnAdd', 'Playlist.OnRemove',
                                               'Player.OnPlay'):
                import time
                try:
                    details = json.loads(data) or {}
                except ValueError:
                    details = {}
                if isinstance(details, dict) and music_start.notice(method, details, time.time()):
                    run_command('now_playing', [])
                if isinstance(details, dict) and (method == 'Player.OnPlay' or details.get('playlistid') == 0):
                    queue_watch.changed()
            message = parse_message(sender, method)
            if message:
                run_command(*message)

    home = _home()
    if home.getProperty('nc.service'):
        # another service listens already: run the command, and leave the listening to it
        if first:
            _run(first[0], list(first[1:]))
        return
    monitor = _monitor(Listener)
    home.setProperty('nc.service', '1')
    if first:
        _run(first[0], list(first[1:]))
    stop = threading.Event()
    threading.Thread(target=hero_watch, args=(monitor, stop), daemon=True).start()
    while not monitor.waitForAbort(1):
        if xbmc.getSkinDir() != ADDON_ID:
            # back on this skin, Home starts a new one
            stop.set()
            home.clearProperty('nc.service')
            return
    stop.set()
    # Kodi ends: it holds the GUI while it waits for this script, so no window calls here


COMMANDS['service'] = service


def main(argv):
    if argv and argv[0] in COMMANDS:
        COMMANDS[argv[0]](*argv[1:])


if __name__ == '__main__':
    main(sys.argv[1:])
