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


def following_episodes(episodeid, episodes):
    """The ids of the show's episodes after `episodeid` in season and episode order: after a
    regular episode the regular ones, after a special (season 0) the specials."""
    current = next((e for e in episodes if e['episodeid'] == episodeid), None)
    if current is None:
        return []
    special = current['season'] == 0
    key = (current['season'], current['episode'])
    later = [e for e in episodes if (e['season'] == 0) == special and (e['season'], e['episode']) > key]
    return [e['episodeid'] for e in sorted(later, key=lambda e: (e['season'], e['episode']))]


AUTOPLAY_EPISODES = 2  # videoplayer.autoplaynextitem's value for episodes


def autoplay_episodes(value):
    """Whether Kodi's "Play next video automatically" holds for episodes."""
    return AUTOPLAY_EPISODES in (value or [])


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


# The lists wait for the show of the page. The page keeps the lists of the page before while its
# own load (Kodi only swaps them once the new ones are there): an item count or a season number
# can come from another show. In the tabs of a show without this season info_select found nothing
# to select, and the page stayed on the first tab and the first card of the new lists.
SEASONS_OF = 'String.IsEqual(Container(5200).ListItemAbsolute(0).TvShowDBID,{})'
# the episode row (5100) lists the episodes of the season (format: its number). Its first path
# lacks the season, before the season tabs (5200) chose one: it then lists the season folder,
# whose Season matches and whose Episode is the count of its episodes. Right after Kodi started the
# lists load slowly enough to catch it there, and the episode stayed unselected.
EPISODES_IN = ('String.IsEqual(Container(5100).ListItemAbsolute(0).TvShowDBID,{}) + '
               'String.IsEqual(Container(5100).ListItemAbsolute(0).DBType,episode) + '
               'String.IsEqual(Container(5100).ListItemAbsolute(0).Season,{})')
PAGE_OF = 'Window.IsActive(movieinformation) + String.IsEqual(ListItem.DBID,{})'
# s the lists of an episode's page may take: its first read of a big library, with all of Kodi's
# job threads on the rows of Home, takes longer than a moment
LISTS_LOAD = 60.0


def _wait_on_page(condition, dbid):
    """_wait for CONDITION as long as the page of episode DBID is open; a page opened after it
    has a thread of its own."""
    import xbmc
    page = PAGE_OF.format(dbid)
    _wait('[{}] | ![{}]'.format(condition, page), timeout=LISTS_LOAD)
    return xbmc.getCondVisibility('[{}] + {}'.format(condition, page))


def _select_episode():
    import xbmc
    season = xbmc.getInfoLabel('ListItem.Season')
    episode = xbmc.getInfoLabel('ListItem.Episode')
    dbid = xbmc.getInfoLabel('ListItem.DBID')
    show = xbmc.getInfoLabel('ListItem.TvShowDBID') or _home().getProperty('nc.info.show')
    if not show or not dbid or not _wait_on_page(SEASONS_OF.format(show), dbid):
        xbmc.log('nightcity: info_select: no season tabs for show {!r}, episode {!r}'.format(show, dbid), xbmc.LOGWARNING)
        return
    index = find_index(_labels(5200, 'Season'), season)
    if index is not None:
        _focus('SetFocus(5200,{},absolute)'.format(index))
    if _wait_on_page(EPISODES_IN.format(show, season), dbid):
        index = find_index(_labels(5100, 'Episode'), episode)
        if index is not None:
            _focus('SetFocus(5100,{},absolute)'.format(index))
    if not _wait('String.IsEqual(Container(5100).ListItem.Season,{}) + '
                 'String.IsEqual(Container(5100).ListItem.Episode,{})'.format(season, episode), timeout=2.0):
        xbmc.log('nightcity: info_select: S{}E{} of show {} not selected, the row is on S{}E{}'.format(
            season, episode, show, xbmc.getInfoLabel('Container(5100).ListItem.Season'),
            xbmc.getInfoLabel('Container(5100).ListItem.Episode')), xbmc.LOGWARNING)
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
# plugin lists at once crash Kodi; TmdbBusy in Includes_Tmdb.xml). The recommendations only
# while shown: hidden (a show or person page) they keep the IsUpdating of the page before.
INFO_LISTS_REST = {'5500': '!Container(5500).IsUpdating + ![Control.IsVisible(5402) + Container(5300).IsUpdating]',
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


def _forget_ways_back(home, page):
    """Drop the ways back past chain position PAGE: they are from a chain that ended without
    coming back to them, and the next chain through such a page would take the focus there."""
    later = page + 1
    while home.getProperty(return_key(str(later))):
        home.clearProperty(return_key(str(later)))
        later += 1


def info_leave(list_id, item, tab, position, tmdb_id, dbid):
    home = _home()
    page = return_key(position)[len('nc.ret.'):]
    if page.isdigit():
        _forget_ways_back(home, int(page))
    point = return_point(list_id, item, tab, tmdb_id, dbid)
    if point:
        home.setProperty(return_key(position), point)
        # the page parks its focus at once when it opens again (DialogVideoInfo.xml onload)
        home.setProperty('nc.ret.top', page)


def info_forget():
    """A chain starts from the OSD cast row (Custom_1141_OSDCast.xml): no info page is left
    before its first one, every way back is from a chain before."""
    home = _home()
    _forget_ways_back(home, 0)
    home.clearProperty('nc.ret.top')


# the player's chapter row (VideoOSDBookmarks.xml) or cast row (Custom_1141_OSDCast.xml) has the
# keys, no info page over them
OSD_ROWS = '!Window.IsActive(movieinformation) + [Window.IsActive(videobookmarks) | Window.IsActive(1141)]'


def back_to_start():
    """Back held on an info page (BACK_KEYMAP): back to where the browsing started, however deep
    the TMDb chain is. A chain from a movie or episode page has that page first (TMDb Helper's
    origin): its manager goes back to it at once (TMDbHelper.Command first, a command of the
    twiebe fork), and the page takes the focus to the item the chain went on from (nc.ret.1,
    info_back). A chain from the OSD cast row (nc.osd.ret) has no page before its first: it
    ends, and the player's controls come back on their first button. In the player's chapter and
    cast rows (OSD_ROWS) it goes there too: the rows close, the controls take the focus on their
    first button. Outside a chain, and on the page it started from, it is a Back."""
    import xbmc
    home = _home()
    position = xbmc.getInfoLabel('Window(Home).Property(TMDbHelper.Position)')
    if xbmc.getCondVisibility(OSD_ROWS):
        # closed at once: the SetFocus goes to the topmost dialog, the OSD only once they are gone
        xbmc.executebuiltin('Dialog.Close(1141,true)')
        xbmc.executebuiltin('Dialog.Close(videobookmarks,true)')
        xbmc.executebuiltin('SetFocus(602)')
    elif not chain_running(home):
        xbmc.executebuiltin('Action(Back)')
    elif home.getProperty('nc.osd.ret'):
        info_forget()
        # the quick way back: the player's controls on their own first button (play or resume,
        # VideoFullScreen.xml), not on the cast row's person a plain Back walks back to
        home.clearProperty('nc.osd.ret')
        home.clearProperty('nc.osd.ret.tab')
        home.setProperty('nc.chain.return', 'controls')
        home.setProperty('TMDbHelper.Command', 'exit')
    elif not position.isdigit() or int(position) < 2:
        xbmc.executebuiltin('Action(Back)')
    else:
        # the pages in between close: their ways back with them
        _forget_ways_back(home, 1)
        if home.getProperty(return_key('1')):
            # the first page parks its focus at once (DialogVideoInfo.xml onload)
            home.setProperty('nc.ret.top', '1')
        else:
            home.clearProperty('nc.ret.top')
        home.setProperty('TMDbHelper.Command', 'first')


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
    """The OSD cast row reopened after a chain: the person it was left from (ITEM counts from 1).
    Only while the focus is still on the row: an Up while it reloaded went on to the tabs."""
    import xbmc
    if not item.isdigit() or int(item) < 1:
        return
    index = int(item) - 1
    if _wait('Window.IsActive(1141) + !Container(6501).IsUpdating + Integer.IsGreater(Container(6501).NumItems,{})'
             ' + String.IsEqual(Container(6501).ListItem(0).Property(param.info),{})'.format(index, tab or 'cast'), 20.0):
        if xbmc.getCondVisibility('Window.IsActive(1141) + Control.HasFocus(6501)'):
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
    started = _wait_for_video()
    if started:
        xbmc.executebuiltin('Dialog.Close(movieinformation,true)')
    if mediatype == 'episode':
        _queue_following(int(dbid))
    if not started:
        _log('play: {} {} did not start, or the info page was closed'.format(mediatype, dbid))
        return
    if mediatype == 'episode':
        _return_to_episode(int(dbid))


def _queue_following(episodeid):
    """Put the show's following episodes behind the one Player.Open started: Kodi put that one
    alone into the video playlist and plays the next item when a file ends, if its "Play next
    video automatically" holds for episodes. Resume stays with the first one. Kodi empties the
    playlist when that one starts, after Player.Open returned: added before, they are gone."""
    import xbmc
    monitor, seconds = _monitor(), 0.0
    while not (xbmc.getCondVisibility('Player.HasVideo')
               and xbmc.getInfoLabel('VideoPlayer.DBID') == str(episodeid)):
        if seconds >= LOAD_TIMEOUT or monitor.waitForAbort(0.2):
            return
        seconds += 0.2
    try:
        setting = _rpc('Settings.GetSettingValue', setting='videoplayer.autoplaynextitem')['value']
        if not autoplay_episodes(setting):
            return
        details = _rpc('VideoLibrary.GetEpisodeDetails', episodeid=episodeid, properties=['tvshowid'])
        episodes = _rpc('VideoLibrary.GetEpisodes', tvshowid=details['episodedetails']['tvshowid'],
                        properties=['season', 'episode']).get('episodes', [])
        ids = following_episodes(episodeid, episodes)
        if ids:
            _rpc('Playlist.Add', playlistid=1, item=[{'episodeid': i} for i in ids])
        _log('play: queued {} episodes after {}'.format(len(ids), episodeid))
    except Exception as error:  # the episode plays anyway
        _log('play: queueing after {} failed: {}'.format(episodeid, error))


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


CHAIN_FREE = ('String.IsEmpty(Window(Home).Property(TMDbHelper.Instance)) + '
              'String.IsEmpty(Window(Home).Property(nc.chain.claim))')


def player_info():
    """The player's info button (VideoOSD.xml 612): the page of what plays. A library movie or
    episode opens its own page; anything else the page TMDb Helper recognised it as, a chain over
    the player as from the cast row (ChainClick: never while one starts, two interpreters
    starting at once crash Kodi)."""
    import xbmc
    dbid = xbmc.getInfoLabel('VideoPlayer.DBID')
    if dbid.isdigit() and int(dbid) > 0:
        if xbmc.getCondVisibility('VideoPlayer.Content(movies)'):
            info('movie', dbid)
            return
        if xbmc.getCondVisibility('VideoPlayer.Content(episodes)'):
            _claim_info()
            _episode_info(int(dbid))
            return
    if xbmc.getCondVisibility('VideoPlayer.Content(episodes)'):
        kind, tmdb_id = 'tv', xbmc.getInfoLabel('Window(Home).Property(TMDbHelper.Player.TVShow.TMDb_ID)')
    else:
        kind, tmdb_id = 'movie', xbmc.getInfoLabel('Window(Home).Property(TMDbHelper.Player.TMDb_ID)')
    if not tmdb_id or not xbmc.getCondVisibility(CHAIN_FREE):
        return
    xbmc.executebuiltin('RunScript(plugin.video.themoviedb.helper,add_tmdb={},tmdb_type={},call_auto=1190)'.format(tmdb_id, kind))
    xbmc.executebuiltin('SetProperty(nc.chain.claim,1,home)')


def plot(item='ListItem'):
    """The whole plot of the info page in Kodi's text viewer (button 9063, DialogVideoInfo.xml), under
    the title, a person's name. ITEM is the info prefix: Container(5100).ListItem on an episode's
    page, whose head follows its episode list."""
    import xbmc
    import xbmcgui
    heading = xbmc.getInfoLabel(item + '.Title') or xbmc.getInfoLabel(item + '.Label')
    xbmcgui.Dialog().textviewer(heading, xbmc.getInfoLabel(item + '.Plot'))


# --- trailer: plays over its info page --------------------------------------------------------

TRAILER_START = 30.0  # s a trailer has to start: a plugin (YouTube) resolves it first
TRAILER_OURS = 'Player.HasVideo + String.IsEmpty(VideoPlayer.DBID)'  # a library title has an id
YOUTUBE = 'plugin.video.youtube'


def trailer_addon_builtin(path, installed, enabled):
    """The builtin that offers the add-on a trailer needs, None when it can play: YouTube links
    (Jellyfin for Kodi and TMDb Helper store trailers so) need the YouTube add-on. Kodi asks
    before it installs or enables one."""
    if not path.startswith('plugin://{}/'.format(YOUTUBE)) or (installed and enabled):
        return None
    return '{}({})'.format('EnableAddon' if installed else 'InstallAddon', YOUTUBE)


def trailer_state(wanted, has_video, info_open, started, seconds):
    """What the trailer over its info page does next: 'wait' for it to start, 'play', or 'over'
    once it ended, Back cleared nc.trailer (`wanted`), the page closed, or it did not start
    within TRAILER_START."""
    if not wanted or not info_open:
        return 'over'
    if has_video:
        return 'play'
    if started or seconds >= TRAILER_START:
        return 'over'
    return 'wait'


def play_windowed(path):
    """PlayMedia without the switch to the player (,1), from the start."""
    return 'PlayMedia("{}",1,noresume)'.format(path.replace('\\', '\\\\').replace('"', '\\"'))


def trailer():
    """The trailer of the movie on the info page (button 9008), in full screen over the page: it
    plays without the player window, the page shows it (9095 in DialogVideoInfo.xml) and keeps
    the keys (9099), so the page and a TMDb chain under it stay. The button has set nc.trailer
    and moved the focus to 9099 already. Once the trailer is over the focus goes back to the
    button. Never over a video that plays: it would end it. Without the add-on the trailer
    needs it offers that instead (trailer_addon_builtin)."""
    import xbmc
    home = _home()
    path = xbmc.getInfoLabel('ListItem.Trailer')
    offer = trailer_addon_builtin(path, xbmc.getCondVisibility('System.HasAddon({})'.format(YOUTUBE)),
                                  xbmc.getCondVisibility('System.AddonIsEnabled({})'.format(YOUTUBE)))
    played = bool(path) and not offer and not xbmc.getCondVisibility('Player.HasVideo')
    started, seconds = False, 0.0
    try:
        if offer:
            xbmc.executebuiltin(offer)
        if played:
            home.setProperty('nc.trailer', '1')
            xbmc.executebuiltin(play_windowed(path))
            started, seconds = _trailer_follow(home)
    finally:
        home.clearProperty('nc.trailer')
        if xbmc.getCondVisibility('Control.HasFocus(9099)'):
            _focus('SetFocus(9008)')
    try:
        if not played:
            return
        # the page closed under it, or Back came while the plugin still resolved it: a trailer
        # that plays (or starts late) without its page stops
        if _wait(TRAILER_OURS, 0.1 if started else max(TRAILER_START - seconds, 0.1)):
            xbmc.executebuiltin('PlayerControl(Stop)')
        _trailer_lists_rest()
    finally:
        home.clearProperty('nc.trailer.lists')


TRAILER_RELOAD = 0.5  # s for Kodi to start reloading the page's lists after the stop


def _trailer_lists_rest():
    """Wait until the player stopped and the cast list's reload is over. Kodi reloads every list
    without a sort order when playback starts or stops (CDirectoryProvider::Announce): the button
    held the recommendations (nc.trailer.lists, InfoSimilarPath) so the cast reloads alone, and
    they load after it as when the page opens; two plugins starting at once crash Kodi."""
    import time
    _wait('!Player.HasMedia', 5.0)
    time.sleep(TRAILER_RELOAD)
    _wait('!Container(5500).IsUpdating', 30.0)


def _trailer_follow(home):
    """Follow the trailer until it is over (trailer_state); (started, seconds)."""
    import xbmc
    monitor, seconds, started, step = _monitor(), 0.0, False, 0.2
    while True:
        state = trailer_state(bool(home.getProperty('nc.trailer')), xbmc.getCondVisibility('Player.HasVideo'),
                              xbmc.getCondVisibility('Window.IsActive(movieinformation)'), started, seconds)
        if state == 'over' or monitor.waitForAbort(step):
            return started, seconds
        started = started or state == 'play'
        seconds += step


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


def skin_id():
    """The id of the active skin: Nightcity and Confuse share this script."""
    import xbmc
    return xbmc.getSkinDir()


def _search_file():
    import xbmcvfs
    folder = xbmcvfs.translatePath('special://profile/addon_data/{}/'.format(skin_id()))
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
# both close the page. On the library grid likewise: Back on its position bar returns to the card
# it came from. Back held on an info page goes back to
# where the browsing started (back_to_start), in the player's chapter and cast rows to the
# player's controls: without sections of their own Kodi took the global long press there, one
# row up like a single Back. Kodi knows long presses only in the keyboard
# section (CEC and MCE remotes send theirs in the remote section). Written whatever the Home key
# setting.
BACK_KEYMAP_NAME = '0_skin.nightcity.back.xml'
BACK_KEYMAP = """<?xml version="1.0" encoding="UTF-8"?>
<!-- Written by the Nightcity skin: on info pages and the library grid the keys of PreviousMenu are Back, Back held on an info page goes back to where the browsing started, in the player's chapter and cast rows to the player's controls. -->
<keymap>
  <movieinformation>
    <keyboard>
      <escape>Back</escape>
      <!-- held: back to where the browsing started (back_to_start) -->
      <backspace mod="longpress">NotifyAll(nightcity,back_to_start)</backspace>
      <browser_back mod="longpress">NotifyAll(nightcity,back_to_start)</browser_back>
      <escape mod="longpress">NotifyAll(nightcity,back_to_start)</escape>
    </keyboard>
    <gamepad>
      <back>Back</back>
    </gamepad>
    <mouse>
      <rightclick>Back</rightclick>
    </mouse>
  </movieinformation>
  <!-- the player's chapter and cast rows: Back held goes to the player's controls (back_to_start) -->
  <videobookmarks>
    <keyboard>
      <backspace mod="longpress">NotifyAll(nightcity,back_to_start)</backspace>
      <browser_back mod="longpress">NotifyAll(nightcity,back_to_start)</browser_back>
      <escape mod="longpress">NotifyAll(nightcity,back_to_start)</escape>
    </keyboard>
  </videobookmarks>
  <window1141>
    <keyboard>
      <backspace mod="longpress">NotifyAll(nightcity,back_to_start)</backspace>
      <browser_back mod="longpress">NotifyAll(nightcity,back_to_start)</browser_back>
      <escape mod="longpress">NotifyAll(nightcity,back_to_start)</escape>
    </keyboard>
  </window1141>
  <window1110>
    <keyboard>
      <escape>Back</escape>
    </keyboard>
    <gamepad>
      <back>Back</back>
    </gamepad>
    <mouse>
      <rightclick>Back</rightclick>
    </mouse>
  </window1110>
  <music>
    <keyboard>
      <escape>NotifyAll(nightcity,music_bar:escape)</escape>
    </keyboard>
    <gamepad>
      <back>NotifyAll(nightcity,music_bar:escape)</back>
    </gamepad>
    <mouse>
      <rightclick>NotifyAll(nightcity,music_bar:escape)</rightclick>
    </mouse>
  </music>
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
_music_queue_lock = threading.Lock()  # music_queue runs in several threads


def queue_one_album(items):
    """True when the queue ITEMS (Playlist.GetItems with albumid) all come from one album."""
    albums = {item.get('albumid') for item in items}
    return len(albums) == 1 and bool(albums.pop())


def music_queue():
    """Note whether the music queue holds one album (MUSIC_QUEUE_ALBUM): the OSD shows its
    tracks as lines then, else cards with covers. On every change of the queue (the service)."""
    # one at a time: a thread that read the queue before a change must not write after one that
    # read it since
    with _music_queue_lock:
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
# that goes. On Home the service points it at the hero's spotlight (9000 movies, 9001 shows),
# wherever the cursor is, unless "Ratings only on title pages" (nc.ratings.titleonly) keeps it off
# spotlight and rows; an
# episode's info page points it at its episode list itself (DialogVideoInfo.xml, 5100). The
# service keeps what TMDb Helper fetched per title for the session and shows the kept ratings of
# the item on screen in nc.kept.<container>.*, which the ratings line reads: they stay once
# fetched, also when the spotlight or the list comes back to a title. While the hero follows a
# row title (FollowHero, group 9302) the kept ratings of the focused card go to nc.kept.follow.*:
# with an empty WidgetContainer TMDb Helper does not look at Home's items at all, so it is pointed
# at the row once the cursor stood still on the card for FOLLOW_SETTLE s and let go of it when
# the ratings are kept or the cursor moves on, so a move along the row costs no request. While a video plays it
# keeps TMDb Helper's player ratings (TMDbHelper.Player.*) the same way in nc.kept.player.*.

HERO_SOURCES = ('IMDb_Rating', 'Top250', 'TMDb_Rating', 'RottenTomatoes_Rating', 'RottenTomatoes_UserMeter',
                'MetaCritic_Rating', 'Trakt_Rating', 'Letterboxd_Rating', 'MDBList_Rating')
# for an episode TMDb Helper gives these for the episode itself, the others are the show's
EPISODE_SOURCES = ('IMDb_Rating', 'Trakt_Rating')
HERO_STABLE = 0.8  # s TMDb Helper's ratings stay before they count: they lag behind its title
HERO_POLL = 0.25  # s between two looks
HERO_PROPS = 'nc.kept.{}.{}'
# container of the spotlight, the group on screen with its hero
HEROES = (('9000', '9300'), ('9001', '9301'))
# the group of the hero while it follows a row title, where its ratings go
FOLLOW_GROUP = '9302'
# a page without spotlight previews the title of a row (Includes_Sections.xml PeekHeroes): the
# group of slot n is base + n, its row list is the page's row id; the same ratings as a card
PEEK_GROUPS = tuple((str(base + n), '{}0{}'.format(row, n)) for base, row in ((9360, 92), (9370, 94), (9380, 95))
                    for n in range(1, 9))
PEEK_SHOWN = ' | '.join('Control.IsVisible({})'.format(group) for group, _ in PEEK_GROUPS)
FOLLOW_KEPT = 'follow'
FOLLOW_SETTLE = 1.5  # s the cursor stands on a card before TMDb Helper looks it up
FOLLOW_EMPTY = 5.0  # s it stays pointed at a card without ratings: its poller may be in another lookup
FOLLOW_ROW = 'System.CurrentControlId'
# what names a title: (property name, ListItem info); the last one guards the line
HERO_KEY = (('dbtype', 'DBType'), ('dbid', 'DBID'))
EPISODE_KEY = (('label', 'Label'), ('season', 'Season'), ('episode', 'Episode'))
# a card without a library id (TMDb Helper's own lists, Trending)
CARD_KEY = (('dbtype', 'DBType'), ('year', 'Year'), ('label', 'Label'))
HERO_ON_HOME = 'Window.IsActive(home)'
HERO_DIALOG = 'System.HasActiveModalDialog'
HERO_SHOWN = 'Control.IsVisible({})'
HERO_TITLE_ONLY = 'Skin.HasSetting(nc.ratings.titleonly)'
INFO_EPISODES = ('Window.IsActive(movieinformation) + '
                 'String.IsEqual(Window(movieinformation).Property(TMDbHelper.WidgetContainer),5100)')
# the player: TMDb Helper sets TMDbHelper.Player.* for a movie or an episode once it has started;
# kept for what plays (title and file, the file guards the line) in nc.kept.player.*
PLAYER_VIDEO = 'Player.HasVideo'
PLAYER_KEY = (('title', 'VideoPlayer.Title'), ('file', 'Player.FilenameAndPath'))
PLAYER_INFO = ('DBType', 'Title', 'TVShowTitle', 'Season', 'Episode', 'imdb_id')
PLAYING_INFO = ('Title', 'TVShowTitle', 'Season', 'Episode', 'IMDBNumber')


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
        self.card = None  # the card the hero follows: (row, dbtype, dbid, label)
        self.card_since = 0.0
        self.card_asked = None  # when TMDb Helper was pointed at it during this stand
        self.reloads = 0

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


def _keep(kept, home, container, fields, watched, now, item=None):
    """Keep TMDb Helper's ratings of the item of CONTAINER (named by FIELDS; ITEM: the info prefix
    of another item, kept under the name CONTAINER) when it WATCHED that item and is done with it;
    show the kept ratings of that item."""
    import xbmc
    item = item or 'Container({}).ListItem.'.format(container)
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
    _publish(home, kept.changes(container, key))


def _publish(home, changes):
    for name, value in changes:
        if value:
            home.setProperty(name, value)
        else:
            home.clearProperty(name)


def _helper_busy(home):
    return bool(home.getProperty('TMDbHelper.IsUpdating') or home.getProperty('TMDbHelper.IsUpdatingRatings'))


def _drop_helper_ratings(home):
    """TMDb Helper changes base_* with the title, its ratings only when the new ones arrive, and
    never when the cursor left before that: what stands there then is the title before's."""
    for source in HERO_SOURCES:
        home.clearProperty('TMDbHelper.ListItem.' + source)


def _point_helper(kept, home, container):
    """Point TMDb Helper at CONTAINER and have it look up what it finds there anew. It checks
    whether a result still belongs to its item through the container it was last pointed at, also
    after WidgetContainer went: a lookup still running writes its ratings on whatever comes next,
    the spotlight's on a card. Service.Reload is part of the name of its item: that lookup no longer
    belongs, and a title it held from a lookup left in the middle is not taken for done."""
    _drop_helper_ratings(home)
    kept.reloads += 1
    home.setProperty('TMDbHelper.Service.Reload', 'nc{}'.format(kept.reloads))
    home.setProperty('TMDbHelper.WidgetContainer', container)


def follow_tick(kept, home, now, row=None):
    """The hero follows the focused card: point TMDb Helper at its row once the cursor stood
    still and the card has nothing kept, let go when the ratings are kept or at the next move;
    keep only what it found while it was pointed, and show that. ROW: the hero previews the
    current title of that row instead (a page without spotlight), as if it were the focused card."""
    import xbmc
    item = 'Container({}).ListItem.'.format(row) if row else 'ListItem.'
    row = row or xbmc.getInfoLabel(FOLLOW_ROW)
    dbtype, dbid, label = (xbmc.getInfoLabel(item + info) for info in ('DBType', 'DBID', 'Label'))
    fields = HERO_KEY if dbid else CARD_KEY
    key = tuple((name, xbmc.getInfoLabel(item + info)) for name, info in fields)
    card = (row, dbtype, dbid, label)
    pointed = home.getProperty('TMDbHelper.WidgetContainer')
    ratings = kept.cache.get(key, {})
    if card != kept.card:
        if _helper_busy(home):
            _drop_helper_ratings(home)
        kept.card, kept.card_since, kept.card_asked = card, now, None
        if pointed:
            home.clearProperty('TMDbHelper.WidgetContainer')
    elif pointed:
        # pointed, TMDb Helper would look up the next card by itself
        if any(ratings.values()) or (key in kept.cache and now - (kept.card_asked or now) >= FOLLOW_EMPTY):
            home.clearProperty('TMDbHelper.WidgetContainer')
    elif now - kept.card_since >= FOLLOW_SETTLE and row and kept.card_asked is None and not any(ratings.values()):
        _point_helper(kept, home, row)
        kept.card_asked = now
    _keep(kept, home, FOLLOW_KEPT, fields, kept.card_asked is not None, now, item=item)


def player_same_title(props, playing):
    """TMDb Helper's player properties PROPS ({name: value}) belong to what plays (PLAYING,
    VideoPlayer.* without the prefix): for a new item it sets them only once that has started,
    before that they are the last item's. An episode by season and episode and its title or
    show; a movie by IMDb number, by title without one."""
    if props.get('DBType') == 'episode':
        return (props.get('Season'), props.get('Episode')) == (playing.get('Season'), playing.get('Episode')) and (
            props.get('Title') == playing.get('Title') or props.get('TVShowTitle') == playing.get('TVShowTitle'))
    if props.get('DBType') == 'movie':
        if props.get('imdb_id') and playing.get('IMDBNumber'):
            return props['imdb_id'] == playing['IMDBNumber']
        return bool(props.get('Title')) and props.get('Title') == playing.get('Title')
    return False


def player_tick(kept, now):
    """One look while a video plays: keep TMDb Helper's ratings of what plays, show the kept ones."""
    import xbmc
    home = _home()
    key = None
    if xbmc.getCondVisibility(PLAYER_VIDEO):
        values = tuple((name, xbmc.getInfoLabel(info)) for name, info in PLAYER_KEY)
        key = values if all(v for _, v in values) else None
    if key and any(kept.cache.get(key, {}).values()):
        pass  # kept for good: no need to look at TMDb Helper's again while it plays
    elif key:
        props = {n: home.getProperty('TMDbHelper.Player.' + n) for n in PLAYER_INFO + HERO_SOURCES + ('Rating',)}
        playing = {n: xbmc.getInfoLabel('VideoPlayer.' + n) for n in PLAYING_INFO}
        if player_same_title(props, playing):
            kept.seen(key, episode_ratings(props) if props['DBType'] == 'episode' else
                      {s: props[s] for s in HERO_SOURCES}, now)
        else:
            kept.seen(None, None, now)
    else:
        kept.seen(None, None, now)
    _publish(home, kept.changes('player', key))


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
    # no lookups for spotlight and rows, what stands there goes; what is kept stays for the session
    if xbmc.getCondVisibility(HERO_TITLE_ONLY):
        if home.getProperty('TMDbHelper.WidgetContainer'):
            home.clearProperty('TMDbHelper.WidgetContainer')
        kept.card = None
        for container in (FOLLOW_KEPT,) + tuple(c for c, _ in HEROES):
            _publish(home, kept.changes(container, None))
        return
    if xbmc.getCondVisibility(HERO_SHOWN.format(FOLLOW_GROUP)):
        follow_tick(kept, home, now)
        return
    # one look at all of them, then which one (most pages have a spotlight)
    peek = xbmc.getCondVisibility(PEEK_SHOWN) and next(
        (row for group, row in PEEK_GROUPS if xbmc.getCondVisibility(HERO_SHOWN.format(group))), '')
    if peek:
        follow_tick(kept, home, now, row=peek)
        return
    if kept.card:
        if _helper_busy(home):
            _drop_helper_ratings(home)
        kept.card = None
    container = next((c for c, group in HEROES if xbmc.getCondVisibility(HERO_SHOWN.format(group))), '')
    if home.getProperty('TMDbHelper.WidgetContainer') != container:
        if container:
            _point_helper(kept, home, container)
        else:
            home.clearProperty('TMDbHelper.WidgetContainer')
    if container:
        _keep(kept, home, container, HERO_KEY, True, now)


def hero_watch(monitor, stop):
    """player_tick and hero_tick every HERO_POLL s until STOP, Kodi ends or the service goes."""
    import time
    import xbmc
    kept, playing = HeroRatings(), HeroRatings()
    while not stop.wait(HERO_POLL) and not QUIT.is_set() and not monitor.abortRequested():
        try:
            player_tick(playing, time.monotonic())
            hero_tick(kept, time.monotonic())
        except Exception as e:  # a failing look must not end the watch
            xbmc.log('nightcity: hero ratings failed: {!r}'.format(e), xbmc.LOGERROR)
            stop.wait(5)


# --- the position bar of the library grid (Custom_1110_Library.xml) ------------------------------
# Right from the grid's menu: a cursor on a rail at the far right that names where the grid stands,
# one press a group: a letter, a year, a month or a whole rating, whichever the grid is sorted by.

LIB_WINDOW = 1110
LIB_WINDOW_PYTHON = 11110  # Kodi files a skin's custom windows 10000 up
LIB_GRID = 5000
LIB_MENU_BUTTON = 'SetFocus(5100)'
MUSIC_WINDOW = 10502  # MyMusicNav.xml, one of Kodi's own: no offset
MUSIC_LIST, MUSIC_WALL = 50, 51
MUSIC_MENU_BUTTON = 'SetFocus(9060)'
BAR_BUTTON_ID = 5200
BAR_TOP = 98  # px, the rail
BAR_HEIGHT = 900
BAR_RIGHT = 1912  # px, right edge of the cursor, padded for its glow like every pill
BAR_BUTTON = 74  # px, height of a pill
BAR_MIN_GROUPS = 3  # fewer and a jump is no use: Right stays on the menu
BAR_FOLLOW = 0.15  # s after the last press the grid follows
BAR_MENU_BUTTONS = (5101, 5102, 5103, 5104)  # the library grid's menu: wide, narrow only while the bar has the focus
BAR_MENU_WIDE, BAR_MENU_NARROW = 459, 380
BAR_GLIDE_FRAME = 0.016  # s between the steps of the cursor on its way to the next group
BAR_NONE = 'none'
BAR_MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


def bar_letter(letter):
    """A to Z, an accented letter under its base letter, all else under #."""
    import unicodedata
    base = unicodedata.normalize('NFKD', letter)[:1].upper()
    return base if 'A' <= base <= 'Z' else '#'


def bar_year(value):
    return value if value and value != '0' else BAR_NONE


def bar_month(value):
    """Month of a database date (2026-11-04 21:50:00): Nov 26."""
    match = re.match(r'(\d{2})(\d{2})-(\d{2})-', value or '')
    if not match or not 1 <= int(match.group(3)) <= 12:
        return BAR_NONE
    return '{} {}'.format(BAR_MONTHS[int(match.group(3)) - 1], match.group(2))


def bar_rating(value):
    """Whole points; Kodi writes the decimal sign of the language. No rating is 0.0."""
    try:
        rating = float((value or '').replace(',', '.'))
    except ValueError:
        return BAR_NONE
    return str(int(rating)) if rating > 0 else BAR_NONE


# Container.SortMethod(id): (the item's info label, what makes its group of it). The letter follows
# the sort: Kodi labels the items by it. Any other sort (track, duration...) has no groups to name.
MUSIC_BAR_SORTS = {7: ('SortLetter', bar_letter), 10: ('SortLetter', bar_letter), 11: ('SortLetter', bar_letter),
                   12: ('SortLetter', bar_letter), 14: ('SortLetter', bar_letter), 16: ('Year', bar_year)}

# sort method: (the item's info label, what makes its group of it); added dates come from JSON-RPC,
# ListItem.DateAdded is written in the language's format
BAR_INFO = {'': ('SortLetter', bar_letter), 'sorttitle': ('SortLetter', bar_letter), 'year': ('Year', bar_year),
            'rating': ('Rating', bar_rating)}


def bar_groups(keys):
    """[(key, index of its first title)] in list order. A key is one group wherever it comes back:
    where Kodi sorts an umlaut is not ours to say."""
    first = {}
    for index, key in enumerate(keys):
        if key is not None:  # the parent folder and the like: no group's
            first.setdefault(key, index)
    return list(first.items())


def bar_step(index, delta, count):
    return max(0, min(count - 1, index + delta))


def bar_y(index, count):
    """Top of the cursor: the groups evenly over the rail, whatever their sizes."""
    offset = BAR_HEIGHT * index // (count - 1) if count > 1 else 0
    return BAR_TOP + offset - BAR_BUTTON // 2


def bar_width(label):
    return max(60, 34 + 15 * len(label))


def bar_glide_step(y, goal):
    """The cursor's next place on its way: quick at first, slowing down, never past the goal. By
    position alone: a new position and an animation from the old one are two calls, and Kodi can
    draw between them, so that the cursor flashes at its goal before it sets off."""
    distance = goal - y
    if abs(distance) <= 4:
        return goal
    return y + int(distance * 0.45)


class LibBar:
    """What the bar knows of the grid. Each press is a thread of its own, hence the lock.
    GRID and KEYS are functions: the music library has two views, whichever shows."""

    def __init__(self, window, window_python, menu, grid, keys, menu_buttons=()):
        self.window, self.window_python, self.menu, self.grid, self.keys_now = window, window_python, menu, grid, keys
        self.menu_buttons = menu_buttons
        self.lock = threading.Lock()
        self.glide_lock = threading.Lock()
        self.gliding = False
        self.x, self.y, self.goal = 0, 0, 0
        self.keys, self.groups = [], []
        self.index = 0
        self.origin = 0
        self.follow = Debounce(self._select, BAR_FOLLOW)

    def _window(self):
        import xbmcgui
        return xbmcgui.Window(self.window_python)

    def is_open(self):
        import xbmc
        return xbmc.getCondVisibility('Window.IsActive({})'.format(self.window))

    def _to_top_row(self, position):
        """Kodi puts an item of a later page on the page's last row and one of an earlier page on
        its first, so by way of the end of the list. There the last page cannot scroll further."""
        window = self._window()  # held: a window takes its controls with it when it goes
        grid = window.getControl(self.grid())
        grid.selectItem(len(self.keys) - 1)
        grid.selectItem(position)

    def _select(self):
        with self.lock:
            if self.groups and self.is_open():
                self._to_top_row(self.groups[self.index][1])

    def _show(self, glide=False):
        label = self.groups[self.index][0]
        _home().setProperty('nc.lib.label', label)
        window = self._window()  # held: a window takes its controls with it when it goes
        button = window.getControl(BAR_BUTTON_ID)
        width = bar_width(label)
        button.setWidth(width)
        self.x = BAR_RIGHT - width
        self.goal = bar_y(self.index, len(self.groups))
        if not glide:
            self.y = self.goal
        button.setPosition(self.x, self.y)
        if glide:
            with self.glide_lock:
                if self.gliding:
                    return  # on its way: it takes the new goal along
                self.gliding = True
            threading.Thread(target=self._glide, daemon=True).start()

    def _glide(self):
        """One at a time, whatever the number of presses: each step goes for the latest goal."""
        window = self._window()  # held: a window takes its controls with it when it goes
        button = window.getControl(BAR_BUTTON_ID)
        monitor = _monitor()
        while True:
            with self.glide_lock:
                if self.y == self.goal or not self.is_open():
                    self.y = self.goal
                    self.gliding = False
                    return
                self.y = bar_glide_step(self.y, self.goal)
            button.setPosition(self.x, self.y)
            if monitor.waitForAbort(BAR_GLIDE_FRAME):
                self.gliding = False
                return

    def _menu_width(self, width):
        window = self._window()  # held: a window takes its controls with it when it goes
        for cid in self.menu_buttons:
            window.getControl(cid).setWidth(width)

    def leave(self):
        self._menu_width(BAR_MENU_WIDE)

    def prepare(self):
        """The table of the grid as it stands: titles change while their number stays, and reading
        them takes 39 ms for 5000 titles (kodi-dev), and each new line stays in Kodi's table of info
        strings until it ends."""
        self.keys = self.keys_now()
        self.groups = bar_groups(self.keys)
        if len(self.groups) >= BAR_MIN_GROUPS:
            _home().setProperty('nc.lib.bar', '1')
        else:
            _home().clearProperty('nc.lib.bar')

    def enter(self):
        import xbmc
        self.prepare()
        if len(self.groups) < BAR_MIN_GROUPS:
            xbmc.executebuiltin(self.menu)
            return
        self._menu_width(BAR_MENU_NARROW)
        grid = 'Container({})'.format(self.grid())
        # CurrentItem does not count a parent folder, ListItemAbsolute and SetFocus do
        parent = 1 if xbmc.getCondVisibility(grid + '.ListItemAbsolute(0).IsParentFolder') else 0
        self.origin = int(xbmc.getInfoLabel(grid + '.CurrentItem') or 1) - 1 + parent
        key = self.keys[self.origin] if 0 <= self.origin < len(self.keys) else None
        self.index = next((i for i, group in enumerate(self.groups) if group[0] == key), 0)
        self._show()

    def step(self, delta):
        if self.groups:
            self.index = bar_step(self.index, delta, len(self.groups))
            self._show(glide=True)
            self.follow.changed()

    def go(self, position):
        import xbmc
        self.follow.count += 1  # a press still on its way does not move the grid any more
        xbmc.executebuiltin('SetFocus({},{},absolute)'.format(self.grid(), position))

    def ok(self):
        if self.groups:
            position = self.groups[self.index][1]
            self._to_top_row(position)
            self.go(position)

    def cancel(self):
        self.go(self.origin)


def _library_added():
    """Date added of every title of the grid's kind, by its database id."""
    if _home().getProperty('nc.library') == 'tvshows':
        method, result, key = 'VideoLibrary.GetTVShows', 'tvshows', 'tvshowid'
    else:
        method, result, key = 'VideoLibrary.GetMovies', 'movies', 'movieid'
    return {str(item[key]): item.get('dateadded', '') for item in _rpc(method, properties=['dateadded']).get(result, [])}


def _library_keys():
    """The group of every title of the grid, in the grid's order."""
    import xbmc
    grid = 'Container({})'.format(LIB_GRID)
    count = int(xbmc.getInfoLabel(grid + '.NumItems') or 0)
    item = grid + '.ListItemAbsolute({}).'
    sort = xbmc.getInfoLabel('Skin.String(nc.sort)')
    if sort == 'dateadded':
        added = _library_added()
        return [bar_month(added.get(xbmc.getInfoLabel(item.format(i) + 'DBID'), '')) for i in range(count)]
    label, group = BAR_INFO.get(sort, BAR_INFO[''])
    return [group(xbmc.getInfoLabel(item.format(i) + label)) for i in range(count)]


def _music_grid():
    import xbmc
    return MUSIC_WALL if xbmc.getCondVisibility('Control.IsVisible({})'.format(MUSIC_WALL)) else MUSIC_LIST


def _music_keys():
    """The group of every line of the view; None for what is no title (the parent folder, "all
    albums"), and for all of them in a sort without groups and in a list of songs: every line read
    is one more string in Kodi's table of info strings for good, and nobody jumps through songs."""
    import xbmc
    grid = 'Container({})'.format(_music_grid())
    count = int(xbmc.getInfoLabel(grid + '.NumAllItems') or 0)  # NumItems leaves out the parent folder
    if xbmc.getCondVisibility('Container.Content(songs)'):
        return [None] * count
    method = next((m for m in MUSIC_BAR_SORTS if xbmc.getCondVisibility('Container.SortMethod({})'.format(m))), None)
    if method is None:
        return [None] * count
    label, group = MUSIC_BAR_SORTS[method]
    item = grid + '.ListItemAbsolute({}).'
    return [group(xbmc.getInfoLabel(item.format(i) + label)) if xbmc.getInfoLabel(item.format(i) + 'DBType') else None
            for i in range(count)]


_lib_bar = LibBar(LIB_WINDOW, LIB_WINDOW_PYTHON, LIB_MENU_BUTTON, lambda: LIB_GRID, _library_keys, BAR_MENU_BUTTONS)
_music_bar = LibBar(MUSIC_WINDOW, MUSIC_WINDOW, MUSIC_MENU_BUTTON, _music_grid, _music_keys)


# --- the filter of the library grid ---------------------------------------------------------------
# OK on the filter button of window 1110 opens a list of groups, each a multi-select. Kodi does the
# filtering: a smart playlist in the grid's path (videodb://movies/titles/?xsp=...), its rules as in
# SmartPlayList.cpp. The values of a group or, the groups and. The choice holds for the session, per
# library, in Home's nc.libfilter.<library> (the choice), .path (what the grid shows) and .label
# (the header). Shows have no stream details in Kodi, only the studio.

LIB_FILTER_HDR = ['hdr10', 'hdr10plus', 'dolbyvision', 'hlg']  # Kodi 21 names three; hdr10plus from an NFO
LIB_FILTER_OPTIONS = {
    # group: (key, label, the values Kodi files it under)
    'res': [('2160', '4K', ['2160']), ('1080', '1080p', ['1080']), ('720', '720p', ['720']), ('480', 'SD', ['480'])],
    'hdr': [('sdr', 'SDR', []), ('hdr', 'HDR', LIB_FILTER_HDR), ('hdr10', 'HDR10', ['hdr10']),
            ('hdr10plus', 'HDR10+', ['hdr10plus']), ('dolbyvision', 'Dolby Vision', ['dolbyvision']),
            ('hlg', 'HLG', ['hlg'])],
    'audio': [('truehd', 'TrueHD', ['truehd']), ('dtshd', 'DTS-HD', ['dtshd_ma', 'dtshd_hra']),
              ('dts', 'DTS', ['dca', 'dts']), ('eac3', 'DD+', ['eac3']), ('ac3', 'DD', ['ac3']),
              ('aac', 'AAC', ['aac']), ('flac', 'FLAC', ['flac']), ('opus', 'Opus', ['opus']),
              ('mp3', 'MP3', ['mp3']),
              ('pcm', 'PCM', ['pcm', 'pcm_s16le', 'pcm_s24le', 'pcm_s32le', 'pcm_bluray', 'pcm_dvd'])],
    'channels': [('8', '7.1', ['8']), ('6', '5.1', ['6']), ('2', '2.0', ['2'])],
}
LIB_FILTER_FIELDS = {'res': 'videoresolution', 'hdr': 'hdrtype', 'audio': 'audiocodec',
                     'channels': 'audiochannels', 'studio': 'studio'}
LIB_FILTER_NAMES = {'res': 31504, 'hdr': 31505, 'audio': 31506, 'channels': 31507, 'studio': 31128}
LIB_FILTER_GROUPS = {'movies': ['res', 'hdr', 'audio', 'channels', 'studio'], 'tvshows': ['studio']}


def lib_filter_groups(library):
    return list(LIB_FILTER_GROUPS.get(library, LIB_FILTER_GROUPS['movies']))


def _lib_filter_chosen(library, choice):
    """(group, [(key, label, values)]) of the choice, in the order of the dialog."""
    chosen = []
    for group in lib_filter_groups(library):
        keys = choice.get(group) or []
        if group == 'studio':
            options = [(k, k, [k]) for k in keys]
        else:
            options = [o for o in LIB_FILTER_OPTIONS[group] if o[0] in keys]
        if options:
            chosen.append((group, options))
    return chosen


def _lib_filter_rule(group, options):
    field = LIB_FILTER_FIELDS[group]
    values = []
    for _, _, vals in options:
        values += [v for v in vals if v not in values]
    if group != 'hdr' or not any(key == 'sdr' for key, _, _ in options):
        return {'field': field, 'operator': 'is', 'value': values}
    # Kodi drops an empty value: SDR is none of the HDR types
    sdr = {'field': field, 'operator': 'isnot', 'value': list(LIB_FILTER_HDR)}
    return {'or': [sdr, {'field': field, 'operator': 'is', 'value': values}]} if values else sdr


def lib_filter_path(library, choice):
    """The grid's path for CHOICE ({group: [key]}), '' for none."""
    rules = [_lib_filter_rule(group, options) for group, options in _lib_filter_chosen(library, choice)]
    if not rules:
        return ''
    xsp = json.dumps({'rules': {'and': rules}, 'type': library}, separators=(',', ':'))
    return 'videodb://{}/titles/?xsp={}'.format(library, urllib.parse.quote(xsp, safe=''))


def lib_filter_label(library, choice):
    return '  ·  '.join(', '.join(label for _, label, _ in options)
                        for _, options in _lib_filter_chosen(library, choice))


def lib_filter_dump(choice):
    return json.dumps({g: list(keys) for g, keys in choice.items() if keys}, separators=(',', ':'))


def lib_filter_load(text):
    try:
        choice = json.loads(text) if text else {}
    except ValueError:
        return {}
    if not isinstance(choice, dict):
        return {}
    return {g: [k for k in keys if isinstance(k, str)] for g, keys in choice.items() if isinstance(keys, list)}


def _lib_studios(library):
    """The studios of the library's titles, from Kodi's own studio node."""
    found = _rpc('Files.GetDirectory', directory='videodb://{}/studios/'.format(library), media='video')
    return sorted({f['label'] for f in found.get('files') or [] if f.get('label')}, key=str.lower)


def _capital(label):
    return label[:1].upper() + label[1:]


def _lib_filter_apply(library, choice):
    home = _home()
    prop = 'nc.libfilter.' + library
    home.setProperty(prop, lib_filter_dump(choice))
    home.setProperty(prop + '.path', lib_filter_path(library, choice))
    home.setProperty(prop + '.label', lib_filter_label(library, choice))
    run_command('lib_bar', ['changed'])  # the grid reloads: the bar's groups anew


LIB_LAYOUT_WAIT = 0.1  # s: the window draws once without a layout that holds


def lib_layout():
    """The library window is up: its layouts may hold (LibraryLayoutReady). A panel keeps its items
    over closing the window, each with the layout it drew it with, and picks its layout on the way
    back without telling them; only a condition that changes on screen makes Kodi let them go
    (GUIBaseContainer::UpdateVisibility). So the rows drew as posters after a change of the view
    while the window was closed: another library, or a skin string set from outside."""
    if not _monitor().waitForAbort(LIB_LAYOUT_WAIT):
        _home().setProperty('nc.lib.layout', '1')


def lib_filter():
    """The filter dialog of the library grid: a list of the groups with what is chosen in each,
    OK on one its multi-select; every change applies at once, the grid follows behind the
    dialog. Back closes it."""
    import xbmc
    import xbmcgui
    library = 'tvshows' if _home().getProperty('nc.library') == 'tvshows' else 'movies'
    choice = lib_filter_load(_home().getProperty('nc.libfilter.' + library))
    groups = lib_filter_groups(library)
    studios = None
    text = lambda string_id: _capital(xbmc.getLocalizedString(string_id))  # noqa: E731
    current = 0
    while True:
        items = []
        for group in groups:
            item = xbmcgui.ListItem(text(LIB_FILTER_NAMES[group]))
            chosen = dict(_lib_filter_chosen(library, {group: choice.get(group)}))
            item.setLabel2(', '.join(label for _, label, _ in chosen.get(group, [])) or text(31503))
            items.append(item)
        if lib_filter_path(library, choice):
            items.append(xbmcgui.ListItem(text(31508)))
        picked = xbmcgui.Dialog().select(text(31502), items, preselect=current, useDetails=True)
        if picked < 0:
            return
        current = picked
        if picked >= len(groups):  # clear filter
            choice, current = {}, 0
            _lib_filter_apply(library, choice)
            continue
        group = groups[picked]
        if group == 'studio':
            if studios is None:
                studios = _lib_studios(library)
            options = [(s, s) for s in studios]
        else:
            options = [(key, label) for key, label, _ in LIB_FILTER_OPTIONS[group]]
        if not options:
            continue
        keys = choice.get(group) or []
        preselect = [i for i, (key, _) in enumerate(options) if key in keys]
        selected = xbmcgui.Dialog().multiselect(text(LIB_FILTER_NAMES[group]), [label for _, label in options],
                                                preselect=preselect)
        if selected is None:  # cancelled: the choice stays
            continue
        choice = dict(choice)
        choice[group] = [options[i][0] for i in selected]
        _lib_filter_apply(library, choice)


def _bar_command(bar, action, args):
    """The bar's keys: changed (the window opened or the sort changed, the grid reloads), prepare
    (the menu has the focus: at once, Right may come right after), enter, step:N, ok, cancel, leave."""
    import xbmc
    if action == 'changed':
        _home().clearProperty('nc.lib.bar')
        monitor = _monitor()
        if monitor.waitForAbort(0.4):  # the grid starts to reload
            return
        while xbmc.getCondVisibility('Container({}).IsUpdating'.format(bar.grid())):
            if monitor.waitForAbort(0.1):
                return
    with bar.lock:
        if not bar.is_open():
            return
        if action == 'step':
            bar.step(int(args[0]))
        else:
            {'changed': bar.prepare, 'prepare': bar.prepare, 'enter': bar.enter, 'ok': bar.ok,
             'cancel': bar.cancel, 'leave': bar.leave}[action]()


def lib_bar(action, *args):
    _bar_command(_lib_bar, action, args)


def music_bar(action, *args):
    """escape: the keys of PreviousMenu (BACK_KEYMAP), which stay what they were off the bar."""
    import xbmc
    if action != 'escape':
        _bar_command(_music_bar, action, args)
    elif xbmc.getCondVisibility('Control.HasFocus({})'.format(BAR_BUTTON_ID)):
        _bar_command(_music_bar, 'cancel', ())
    else:
        xbmc.executebuiltin('Action(PreviousMenu)')


COMMANDS = {'lib_bar': lib_bar, 'music_bar': music_bar, 'next_episode': next_episode, 'startup': startup, 'genres': genres, 'genre_pick': genre_pick,
            'info_select': info_select, 'info_leave': info_leave, 'info_back': info_back, 'info_forget': info_forget,
            'back_to_start': back_to_start, 'trailer': trailer,
            'osd_back': osd_back, 'play': play, 'info': info, 'plot': plot, 'player_info': player_info,
            'streams': streams, 'row': row, 'search': search, 'search_recent': search_recent,
            'search_init': search_init, 'search_clear': search_clear, 'search_forget': search_forget, 'colours': colours,
            'streams_watch': streams_watch, 'section_pick': section_pick,
            'home': home, 'home_keymap': home_keymap, 'osd_hide': osd_hide,
            'music_play': music_play, 'music_goto': music_goto, 'music_info': music_info,
            'music_back': music_back, 'now_playing': now_playing, 'music_queue': music_queue,
            'music_queue_select': music_queue_select, 'lib_filter': lib_filter,
            'lib_layout': lib_layout}


# --- the skin service -------------------------------------------------------------------------
# Every Python script Kodi starts gets its own interpreter, and two interpreters starting at once
# can crash Kodi. So the skin starts this script once (the Startup screen, or Home when it finds
# no nc.service) and sends it its commands with NotifyAll(nightcity,command:arg:...): they run in
# threads of this one interpreter.

SENDER = 'nightcity'
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


def _skin_script_exists():
    import os
    import xbmcvfs
    return os.path.exists(xbmcvfs.translatePath('special://skin/scripts/nightcity.py'))


def _start_next(monitor, home):
    """After a skin switch: wait a second so that Home of the new skin has had its chance (two
    interpreters starting at once can crash Kodi), then start the service if nobody did and the
    new skin has the script."""
    import xbmc
    if monitor.waitForAbort(1) or home.getProperty('nc.service') or not _skin_script_exists():
        return
    xbmc.executebuiltin('RunScript(special://skin/scripts/nightcity.py,service,home)')


def service(*first):
    """Listen for the skin's commands until Kodi ends or another skin takes over; FIRST is a
    command to run before (startup)."""
    import xbmc

    music_start = MusicStart()
    queue_watch = Debounce(lambda: run_command('music_queue', []))
    stop = threading.Event()

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
            if message and not stop.is_set():
                run_command(*message)

    home = _home()
    if home.getProperty('nc.service'):
        # another service listens already: run the command, and leave the listening to it
        if first:
            _run(first[0], list(first[1:]))
        return
    started = skin_id()
    monitor = _monitor(Listener)
    home.setProperty('nc.service', '1')
    if first:
        _run(first[0], list(first[1:]))
    # after a skin switch nothing runs startup, and each skin has its own Home key setting
    _run('home_keymap', [])
    threading.Thread(target=hero_watch, args=(monitor, stop), daemon=True).start()
    while not monitor.waitForAbort(1):
        if skin_id() != started:
            # another skin is active: leave, and start the service of the new skin (Home of the new
            # skin looked at nc.service too early to start it)
            stop.set()
            home.clearProperty('nc.service')
            _start_next(monitor, home)
            return
    stop.set()
    # Kodi ends: it holds the GUI while it waits for this script, so no window calls here


COMMANDS['service'] = service


def main(argv):
    if argv and argv[0] in COMMANDS:
        COMMANDS[argv[0]](*argv[1:])


if __name__ == '__main__':
    main(sys.argv[1:])
