#!/usr/bin/env python3
"""Write 1080i/Includes_Sections.xml: the rows of the home pages and the slot rows of the home
pages settings window, built from the catalogue in scripts/nightcity.py.

    python tools/make_sections.py [--check]

Home shows on each page (home, movies, shows) the 8 slots Skin.String(nc.<page>.slot<n>) with
their option nc.<page>.slot<n>.opt. Every slot holds one conditional include per catalogue
section and option; Kodi builds only the one whose condition holds and reloads Home when one of
the conditions changes. An empty Skin.String stands for the slot's default (the rows the page
had before), `none` for an empty slot, which leaves a hidden group that passes moves on.

Ids per page base B (home 92, movies 94, shows 95), slot n: list B0n, group B1n, loader B2n,
split loader of a combo row B7n, genre tabs B30 (tabs B31-B34, gaps B41-B45). Skin settings (SkinSettings.xml), page base S (home
200, movies 300, shows 400): rows grouplist S, spotlight S+11, interval S+12, slots S+21 to S+28;
category button C (home 9002, movies 9003, shows 9004).
"""
import importlib.util
import pathlib
import sys
from xml.sax.saxutils import escape

ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGET = ROOT / '1080i' / 'Includes_Sections.xml'

_spec = importlib.util.spec_from_file_location('nightcity', ROOT / 'scripts' / 'nightcity.py')
nightcity = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nightcity)

PAGES = ('home', 'movies', 'shows')
BASE = {'home': '92', 'movies': '94', 'shows': '95'}
SETTINGS = {'home': 200, 'movies': 300, 'shows': 400}
CATEGORY = {'home': 9002, 'movies': 9003, 'shows': 9004}
# what a section without options shows on the movies and shows pages
IMPLICIT = {'home': '', 'movies': 'movies', 'shows': 'shows'}
PAGE_SHOWN = {
    'home': '[String.IsEmpty(Window(Home).Property(nc.page)) | String.IsEqual(Window(Home).Property(nc.page),home)]',
    'movies': 'String.IsEqual(Window(Home).Property(nc.page),movies)',
    'shows': 'String.IsEqual(Window(Home).Property(nc.page),shows)',
}
TMDB = 'plugin://plugin.video.themoviedb.helper/?info=trending_week&amp;tmdb_type={}'
# a genre row's tabs start after its number, where a row's title starts after its number: a constant
# of the look, since a look without numbers starts them over the cards
GENRE_TABS_LEFT = 'LookGenreTabsLeft'
GENRES = {'movies': ('movies', 'genre', 'GenrePickLabel', 'genre_pick'),
          'shows': ('tvshows', 'tvgenre', 'ShowGenrePickLabel', 'genre_pick:tvshow')}


def pl(name):
    return 'special://skin/playlists/{}.xsp'.format(name)


IN_PROGRESS = {'movies': [pl('WidgetInProgressMovies')], 'shows': [pl('WidgetInProgressEpisodes')]}
RECENT = {'movies': [pl('WidgetRecentMovies')], 'shows': [pl('WidgetRecentEpisodes')]}


def both(table):
    return dict(table, both=table['movies'] + table['shows'])


def section(page, key, kind):
    """Row parameters of a section; kind is its option value or the page's implicit one."""
    loader = {'wait': 'true'}
    if key == 'continue':
        return dict(loader, content=both(IN_PROGRESS)[kind])
    if key == 'nextup':
        return dict(loader, content=[pl('WidgetContinueShows')])
    if key == 'combo':
        # what was started, then next up without the shows a started episode stands for
        return dict(loader, content=both(IN_PROGRESS)[kind] + ['$VAR[ComboNextUp]'], split=len(both(IN_PROGRESS)[kind]))
    if key == 'inprogress':
        return dict(loader, content=IN_PROGRESS['shows'])
    if key == 'recent':
        return dict(loader, content=both(RECENT)[kind])
    if key == 'trending':
        return dict(loader, content=['$VAR[TmdbTrending{}{}]'.format(page.capitalize(), kind.capitalize())])
    if key == 'newmovies':
        return {'content': [pl('WidgetNewMovies' + ('Unwatched' if kind == 'unwatched' else ''))]}
    if key == 'newepisodes':
        return {'content': [pl('WidgetNewShows' + ('Unwatched' if kind == 'unwatched' else ''))]}
    if key == 'random':
        return {'content': [pl('WidgetRandomMovies' + ('Unwatched' if kind == 'unwatched' else ''))]}
    if key == 'toprated':
        return {'content': [pl('WidgetTopRated' + kind.capitalize())]}
    if key == 'favourites':
        return {'content': ['favourites://'], 'click': 'ProviderClick', 'art': '$VAR[FavouriteArt]'}
    if key == 'sets':
        return {'content': ['videodb://movies/sets/'], 'click': 'ProviderClick'}
    if key == 'genres':
        db, prop, _, _ = GENRES[kind]
        return {'content': ['videodb://{}/genres/$INFO[Window(Home).Property(nc.{}.id)]/'.format(db, prop)],
                'genres': kind}
    raise KeyError(key)


def slot_string(page, n, opt=False):
    return 'Skin.String(nc.{}.slot{}{})'.format(page, n, '.opt' if opt else '')


def key_match(page, key, n='$PARAM[n]', default='$PARAM[def_{}]'):
    s = slot_string(page, n)
    return '[String.IsEqual({0},{1}) | [String.IsEmpty({0}) + {2}]]'.format(s, key, default.format(key))


def opt_match(page, values, value, n='$PARAM[n]'):
    s = slot_string(page, n, True)
    if value != values[0]:
        return 'String.IsEqual({},{})'.format(s, value)
    others = ['String.IsEqual({},{})'.format(s, v) for v in values[1:]]
    return '![{}]'.format(' | '.join(others)) if others else ''


def variants(page):
    """(key, option value, condition parts) of every row a slot of the page can hold."""
    for key, opts in nightcity.CATALOGUE[page]:
        values = [v for v, _ in opts]
        for value in values or ['']:
            yield key, value or IMPLICIT[page], values, value


# rows of what plays on: a look can show them wide (LookRowWideCard)
WIDE = ('continue', 'nextup', 'combo')


def param(name, value):
    return '<param name="{}" value="{}"/>'.format(name, value)


def slot_include(page):
    base = BASE[page]
    out = ['    <!-- One slot of the {} page: the row of its section (n, num, up and down from {}Slots) -->'.format(page, page.capitalize()),
           '    <include name="{}Slot">'.format(page.capitalize()),
           '        <param name="n"/>', '        <param name="num"/>', '        <param name="up"/>',
           '        <param name="down" default="noop"/>']
    out += ['        <param name="def_{}" default="false"/>'.format(key) for key, _ in nightcity.CATALOGUE[page]]
    out.append('        <definition>')
    for key, kind, values, value in variants(page):
        row = section(page, key, kind)
        cond = ' + '.join(c for c in (key_match(page, key), opt_match(page, values, value) if values else '') if c)
        loader = base + '2$PARAM[n]' if row.get('wait') else base + '0$PARAM[n]'
        params = [param('id', base + '0$PARAM[n]'), param('group', base + '1$PARAM[n]'),
                  param('up', base + '30' if row.get('genres') else '$PARAM[up]'), param('down', '$PARAM[down]'),
                  param('label', '$LOCALIZE[{}]'.format(nightcity.SECTIONS[key][0])),
                  param('header', 'RowNumber' if row.get('genres') else 'NumberedRowHeader'),
                  param('num', '$PARAM[num]'),
                  param('content1', row['content'][0])]
        for i, path in enumerate(row['content'][1:], 2):
            params.append(param('content{}'.format(i), path))
        params.append(param('loader', loader))
        # a page without spotlight previews the title of the row that had the focus last
        params.append(param('peek', 'SetProperty(nc.peek.{},{}0$PARAM[n],home)'.format(page, base)))
        if row.get('wait'):
            params.append(param('wait', 'true'))
        for extra in ('click', 'art'):
            if extra in row:
                params.append(param(extra, row[extra]))
        if row.get('split'):
            # the first card of next up draws the split (RowBox)
            params += [param('split', 'LookRowSplit'), param('splitloader', base + '7$PARAM[n]')]
        if key in WIDE:
            params += [param('card', 'LookRowWideCard'), param('itemwidth', 'LookRowWideItemWidth'),
                       param('art', '$VAR[LookRowWideArt]')]
        nested = []
        if row.get('genres'):
            db, prop, label, pick = GENRES[row['genres']]
            params += [param('sortby', 'dateadded'),
                       param('sortorder', 'descending'), param('limit', '25')]
            # the list, not the tabs: a selector is skipped from above (DESIGN.md)
            nested = ['<defaultcontrol always="true">{}0$PARAM[n]</defaultcontrol>'.format(base),
                      '<include content="GenreTabs">',
                      '    ' + param('base', base), '    ' + param('list', base + '0$PARAM[n]'),
                      '    ' + param('up', '$PARAM[up]'), '    ' + param('prop', prop),
                      '    ' + param('picklabel', '$VAR[{}]'.format(label)),
                      '    ' + param('pick', pick), '    ' + param('left', GENRE_TABS_LEFT),
                      '    ' + param('font', 'font_caps_small'), '</include>']
        out.append('            <include content="RowBox" condition="{}">'.format(cond))
        out += ['                ' + p for p in params + nested]
        out.append('            </include>')
    matches = ' | '.join(key_match(page, key) for key, _ in nightcity.CATALOGUE[page])
    out.append('            <include content="SlotPlaceholder" condition="![{}]">'.format(matches))
    out.append('                ' + param('id', base + '1$PARAM[n]'))
    out.append('            </include>')
    out += ['        </definition>', '    </include>']
    return out


def loader_include(page):
    base = BASE[page]
    out = ['    <!-- Off-screen loaders of the slots whose row can empty and fill again -->',
           '    <include name="{}SlotLoader">'.format(page.capitalize()), '        <param name="n"/>']
    out += ['        <param name="def_{}" default="false"/>'.format(key) for key, _ in nightcity.CATALOGUE[page]]
    out.append('        <definition>')
    for key, kind, values, value in variants(page):
        row = section(page, key, kind)
        if not row.get('wait'):
            continue
        cond = ' + '.join(c for c in (key_match(page, key), opt_match(page, values, value) if values else '') if c)
        out.append('            <include content="WidgetLoader" condition="{}">'.format(cond))
        out.append('                ' + param('id', base + '2$PARAM[n]'))
        for i, path in enumerate(row['content'], 1):
            out.append('                ' + param('content{}'.format(i), path))
        out.append('            </include>')
        if row.get('split'):
            out.append('            <include content="SplitLoader" condition="{}">'.format(cond))
            out.append('                ' + param('id', base + '7$PARAM[n]'))
            for i, path in enumerate(row['content'][:row['split']], 1):
                out.append('                ' + param('content{}'.format(i), path))
            out.append('            </include>')
    out += ['        </definition>', '    </include>']
    return out


def slots_include(page):
    base, cap = BASE[page], page.capitalize()
    defaults = nightcity.default_slots(page)
    out = ['    <!-- The 8 slots of the {} page; up: where the first row moves up to -->'.format(page),
           '    <include name="{}Slots">'.format(cap), '        <param name="up"/>', '        <definition>']
    for n in range(1, nightcity.SLOTS + 1):
        out.append('            <include content="{}Slot">'.format(cap))
        out.append('                ' + param('n', n))
        out.append('                ' + param('num', '$VAR[RowNumber_{}_{}]'.format(page, n)))
        out.append('                ' + param('up', '$PARAM[up]' if n == 1 else '{}1{}'.format(base, n - 1)))
        if n < nightcity.SLOTS:
            out.append('                ' + param('down', '{}1{}'.format(base, n + 1)))
        if defaults[n - 1] != 'none':
            out.append('                ' + param('def_' + defaults[n - 1], 'true'))
        out.append('            </include>')
    out += ['        </definition>', '    </include>', '    <include name="{}SlotLoaders">'.format(cap)]
    for n in range(1, nightcity.SLOTS + 1):
        out.append('        <include content="{}SlotLoader">'.format(cap))
        out.append('            ' + param('n', n))
        if defaults[n - 1] != 'none':
            out.append('            ' + param('def_' + defaults[n - 1], 'true'))
        out.append('        </include>')
    out.append('    </include>')
    return out


# the rows of the Music page (MusicRows in Includes_Music.xml): groups 9811 to 9815
MUSIC_ROWS = 5


def row_numbers():
    """Number of each row of the pages of Home: 1 + the rows above it that are shown. A shown row
    is a visible row group (an empty slot is a hidden group, a row without items hides itself).
    RowsShown_<page>_<n>_<k>: exactly k of the first n rows are shown."""
    out = ['    <!-- Row numbers (pink, in front of the headings): a row counts the shown rows above',
           '         it; the spotlight is 00 and has no heading, so the first shown row is 01 -->']
    groups = {page: ['{}1{}'.format(BASE[page], n) for n in range(1, nightcity.SLOTS + 1)] for page in PAGES}
    groups['music'] = ['981{}'.format(n) for n in range(1, MUSIC_ROWS + 1)]
    for page, ids in groups.items():
        for n, group in enumerate(ids[:-1], 1):
            for k in range(n + 1):
                shown, hidden = 'Control.IsVisible({})'.format(group), '!Control.IsVisible({})'.format(group)
                if n == 1:
                    cond = shown if k else hidden
                else:
                    prev = '$EXP[RowsShown_{}_{}_{{}}]'.format(page, n - 1)
                    parts = []
                    if k:
                        parts.append('[{} + {}]'.format(shown, prev.format(k - 1)))
                    if k < n:
                        parts.append('[{} + {}]'.format(hidden, prev.format(k)))
                    cond = ' | '.join(parts)
                out.append('    <expression name="RowsShown_{}_{}_{}">{}</expression>'.format(page, n, k, cond))
        for n in range(1, len(ids) + 1):
            out.append('    <variable name="RowNumber_{}_{}">'.format(page, n))
            for k in range(n - 1):
                out.append('        <value condition="$EXP[RowsShown_{}_{}_{}]">{:02d}</value>'.format(page, n - 1, k, k + 1))
            out.append('        <value>{:02d}</value>'.format(n))
            out.append('    </variable>')
    return out


def trending_variables():
    out = ['    <!-- TMDb rows run a plugin: only on their page, 2 s after it came up (Timers.xml), so a',
           '         plugin never starts next to Home\'s script or another page\'s TMDb row -->']
    for page in PAGES:
        kinds = {kind for key, kind, _, _ in variants(page) if key == 'trending'}
        for kind in sorted(kinds):
            out.append('    <variable name="TmdbTrending{}{}">'.format(page.capitalize(), kind.capitalize()))
            out.append('        <value condition="{} + Integer.IsGreaterOrEqual(Skin.TimerElapsedSecs(nc_{}_page),2)">{}</value>'.format(
                PAGE_SHOWN[page], page, TMDB.format('movie' if kind == 'movies' else 'tv')))
            out.append('    </variable>')
    return out


# --- skin settings ---------------------------------------------------------------------------

def settings_defaults():
    out = ['    <!-- Skin settings onload: every slot gets its effective value, so moving and swapping',
           '         copy real values (an empty Skin.String means the default only on Home) -->',
           '    <include name="HomePagesDefaults">']
    for page in PAGES:
        for n, key in enumerate(nightcity.default_slots(page), 1):
            out.append('        <onload condition="String.IsEmpty({0})">Skin.SetString(nc.{1}.slot{2},{3})</onload>'.format(
                slot_string(page, n), page, n, key))
    empty, unwatched = 'String.IsEmpty(Skin.String(nc.movies.spotlight))', 'String.IsEqual(Skin.String(SpotlightSource),unwatched)'
    out.append('        <onload condition="{} + {}">Skin.SetString(nc.movies.spotlight,unwatched)</onload>'.format(empty, unwatched))
    out.append('        <onload condition="{} + !{}">Skin.SetString(nc.movies.spotlight,all)</onload>'.format(empty, unwatched))
    # movies and shows took home's interval before they had their own: it goes on until changed
    for name in ('nc.movies.interval', 'nc.shows.interval'):
        empty, home = 'String.IsEmpty(Skin.String({}))'.format(name), 'String.IsEmpty(Skin.String(SpotlightInterval))'
        out.append('        <onload condition="{} + {}">Skin.SetString({},15)</onload>'.format(empty, home, name))
        out.append('        <onload condition="{} + !{}">Skin.SetString({},$INFO[Skin.String(SpotlightInterval)])</onload>'.format(empty, home, name))
    out.append('    </include>')
    return out


def swap(page, n, m):
    """Actions that swap slots n and m and move the grab to m."""
    a, b = 'nc.{}.slot{}'.format(page, m), 'nc.{}.slot{}'.format(page, n)
    return ['SetProperty(nc.hp.tmp,$INFO[Skin.String({})])'.format(a),
            'SetProperty(nc.hp.tmpopt,$INFO[Skin.String({}.opt)])'.format(a),
            'Skin.SetString({0},$INFO[Skin.String({1})])'.format(a, b),
            'Skin.SetString({0}.opt,$INFO[Skin.String({1}.opt)])'.format(a, b),
            'Skin.SetString({},$INFO[Window.Property(nc.hp.tmp)])'.format(b),
            'Skin.SetString({}.opt,$INFO[Window.Property(nc.hp.tmpopt)])'.format(b),
            'SetProperty(nc.hp.grab,{}.{})'.format(page, m)]


def cycle(page, n, direction):
    """Right actions: the next (direction 1) option of the slot's section."""
    out = []
    for key, opts in nightcity.CATALOGUE[page]:
        values = [v for v, _ in opts]
        if len(values) < 2:
            continue
        for i, value in enumerate(values):
            nxt = values[(i + direction) % len(values)]
            cond = 'String.IsEqual({},{}) + {}'.format(slot_string(page, n), key, opt_match(page, values, value, n))
            action = 'Skin.Reset(nc.{}.slot{}.opt)'.format(page, n) if nxt == values[0] else \
                'Skin.SetString(nc.{}.slot{}.opt,{})'.format(page, n, nxt)
            out.append((cond, action))
    return out


def action(tag, text, cond=''):
    attr = ' condition="{}"'.format(escape(cond, {'"': '&quot;'})) if cond else ''
    return '<{0}{1}>{2}</{0}>'.format(tag, attr, text)


def settings_slots(page):
    base = SETTINGS[page]
    out = ['    <!-- Rows heading and slot rows of the {} category: OK opens the section dialog (or'.format(page),
           '         drops a grabbed slot), right cycles the option, left goes back to the category, up/down',
           '         carry a grabbed slot (a group, not a grouplist: a grouplist replaces the up/down',
           '         actions of its rows). The rows are 10 px larger on each side for their glow',
           '         (HomePagesRow), so the group stands 10 px further out -->',
           '    <include name="HomePagesSlots{}">'.format(page.capitalize()),
           '        <control type="group">',
           '            <left>550</left>',
           '            <top>246</top>',
           '            <visible>String.IsEqual(Window.Property(nc.hp.tab),{})</visible>'.format(page),
           '            <!-- up into the place of the hidden interval row -->',
           '            <animation effect="slide" start="0,0" end="0,-52" time="0" condition="String.IsEqual(Skin.String({}),off)">Conditional</animation>'.format(SOURCE[page][0]),
           '            <include>HomePagesRowsHeading</include>']
    for n in range(1, nightcity.SLOTS + 1):
        cid = base + 20 + n
        grab = 'String.IsEqual(Window.Property(nc.hp.grab),{}.{})'.format(page, n)
        out.append('            <control type="button" id="{}">'.format(cid))
        out.append('                <include>HomePagesRow</include>')
        out.append('                <top>{}</top>'.format(1 + n * 52))
        out.append('                <label>{:02d}   $VAR[HomePagesName_{}_{}]</label>'.format(n, page, n))
        out.append('                <label2>$VAR[HomePagesOpt_{}_{}]</label2>'.format(page, n))
        out.append('                ' + action('onclick', 'ClearProperty(nc.hp.grab)', grab))
        out.append('                ' + action('onclick', 'NotifyAll(nightcity,section_pick:{}:{})'.format(page, n), '!' + grab))
        out.append('                ' + action('onleft', str(cid), grab))
        out.append('                ' + action('onleft', str(CATEGORY[page])))
        for cond, act in cycle(page, n, 1):
            out.append('                ' + action('onright', act, '!{} + {}'.format(grab, cond)))
        out.append('                ' + action('onright', 'noop'))
        for tag, m in (('onup', n - 1), ('ondown', n + 1)):
            if 1 <= m <= nightcity.SLOTS:
                for act in swap(page, n, m):
                    out.append('                ' + action(tag, act, grab))
                out.append('                ' + action(tag, str(base + 20 + m)))
            else:
                out.append('                ' + action(tag, str(cid), grab))
                out.append('                ' + action(tag, str(base + 12) if m == 0 else str(cid)))
        out.append('            </control>')
    out += ['        </control>', '    </include>']
    return out


# spotlight rows of the settings tabs: (skin string, values in order, label variable); the
# value '' is stored as an empty string. Each page has its own spotlight and interval.
SOURCE = {'home': ('SpotlightSource', ['', 'unwatched', 'off'], 'SpotlightSourceLabel'),
          'movies': ('nc.movies.spotlight', ['all', 'unwatched', 'off'], 'MoviesSpotlightLabel'),
          'shows': ('nc.shows.spotlight', ['', 'unwatched', 'off'], 'ShowsSpotlightLabel')}
INTERVAL = {'home': ('SpotlightInterval', ['10', '', '30', '60', 'off'], 'SpotlightIntervalLabel'),
            'movies': ('nc.movies.interval', ['10', '15', '30', '60', 'off'], 'MoviesIntervalLabel'),
            'shows': ('nc.shows.interval', ['10', '15', '30', '60', 'off'], 'ShowsIntervalLabel')}


def value_cycle(name, values, direction):
    """(condition, action) pairs stepping Skin.String(name) through values; anything unknown
    (also empty) counts as the default: '', else 15, else the first value."""
    fallback = '' if '' in values else '15' if '15' in values else values[0]
    out = []
    for i, value in enumerate(values):
        nxt = values[(i + direction) % len(values)]
        if value == fallback:
            others = ['String.IsEqual(Skin.String({}),{})'.format(name, v) for v in values if v != fallback]
            cond = '![{}]'.format(' | '.join(others))
        else:
            cond = 'String.IsEqual(Skin.String({}),{})'.format(name, value)
        act = 'Skin.Reset({})'.format(name) if nxt == '' else 'Skin.SetString({},{})'.format(name, nxt)
        out.append((cond, act))
    return out


def settings_header(page):
    base = SETTINGS[page]
    out = ['    <!-- Spotlight rows of the {} category: OK and right step forward, left goes back to the'.format(page),
           '         category -->',
           '    <include name="HomePagesHeader{}">'.format(page.capitalize())]
    for cid, (name, values, label), title in ((base + 11, SOURCE[page], 31002), (base + 12, INTERVAL[page], 31221)):
        out.append('        <control type="button" id="{}">'.format(cid))
        out.append('            <include>HomePagesRow</include>')
        out.append('            <label>$LOCALIZE[{}]</label>'.format(title))
        out.append('            <label2>$VAR[{}]  ›</label2>'.format(label))
        if cid == base + 12:
            out.append('            <visible>!String.IsEqual(Skin.String({}),off)</visible>'.format(SOURCE[page][0]))
        out.append('            ' + action('onleft', str(CATEGORY[page])))
        for tag in ('onclick', 'onright'):
            for cond, act in value_cycle(name, values, 1):
                out.append('            ' + action(tag, act, cond))
        out.append('        </control>')
    out.append('    </include>')
    return out


def settings_variables():
    out = ['    <!-- Names, options and descriptions of the slots in the skin settings -->']
    for page in PAGES:
        defaults = nightcity.default_slots(page)
        for n in range(1, nightcity.SLOTS + 1):
            s = slot_string(page, n)
            out.append('    <variable name="HomePagesName_{}_{}">'.format(page, n))
            for key, _ in nightcity.CATALOGUE[page]:
                out.append('        <value condition="{}">$LOCALIZE[{}]</value>'.format(
                    key_match(page, key, n, 'true' if defaults[n - 1] == key else 'false'), nightcity.SECTIONS[key][0]))
            out.append('        <value>[COLOR text_mute]$LOCALIZE[504][/COLOR]</value>')
            out.append('    </variable>')
            out.append('    <variable name="HomePagesOpt_{}_{}">'.format(page, n))
            for key, opts in nightcity.CATALOGUE[page]:
                values = [v for v, _ in opts]
                if len(values) < 2:
                    continue
                for value, label in opts:
                    out.append('        <value condition="String.IsEqual({},{}) + {}">$LOCALIZE[{}]  ›</value>'.format(
                        s, key, opt_match(page, values, value, n), label))
            out.append('    </variable>')
            out.append('    <variable name="HomePagesDesc_{}_{}">'.format(page, n))
            for key, _ in nightcity.CATALOGUE[page]:
                out.append('        <value condition="String.IsEqual({},{})">$LOCALIZE[{}]</value>'.format(
                    s, key, nightcity.SECTIONS[key][1]))
            out.append('        <value>$LOCALIZE[31254]</value>')
            out.append('    </variable>')
    out.append('    <variable name="HomePagesSlotDesc">')
    for page in PAGES:
        for n in range(1, nightcity.SLOTS + 1):
            out.append('        <value condition="Control.HasFocus({})">$VAR[HomePagesDesc_{}_{}]</value>'.format(
                SETTINGS[page] + 20 + n, page, n))
    out.append('    </variable>')
    return out


# --- the hero of a still spotlight -----------------------------------------------------------
# A page whose spotlight stands still (interval "still", Includes_Home.xml SpotlightStill<page>)
# keeps its hero and buttons and shows the title the cursor would land on: the current title of
# the row that had the focus last (nc.peek.<page>, set by the row), or of the first row with titles
# before any. Kodi has no list item without a focused list, so each row gets its own copy of the
# hero that follows a card (FollowHero, Includes_Home.xml): the same XML with Container(row).ListItem
# for ListItem, and copies of the variables and expressions it reads. The buttons act on that title
# (PeekPlay, PeekInfo, PeekItemPath, PeekPlayLabel) and Down lands on it (PeekDown).

PEEK_ID = {'home': 9360, 'movies': 9370, 'shows': 9380}  # + n: the hero group of slot n
TITLE_TYPES = ('movie', 'tvshow', 'episode', 'season')
# a card the play button plays: (type, action with {item} for Container(row).ListItem)
PLAYS = (('movie', 'NotifyAll(nightcity,play:movie:$INFO[{item}.DBID]:resume:home)'),
         ('episode', 'NotifyAll(nightcity,play:episode:$INFO[{item}.DBID]:resume:home)'),
         ('tvshow', 'NotifyAll(nightcity,next_episode:$INFO[{item}.DBID])'))
# the title alone as a one-item list, for the buttons' context menu and info key
ITEM_PATHS = (('movie', 'videodb://movies/titles/?videoversionid=0&mediaid=$INFO[{item}.DBID]'),
              ('episode', 'videodb://tvshows/titles/$INFO[{item}.TvShowDBID]/$INFO[{item}.Season]/?xsp='
                          '{{"rules":{{"and":[{{"field":"episode","operator":"is","value":["$INFO[{item}.Episode]"]}}]}},"type":"episodes"}}'),
              ('tvshow', 'videodb://tvshows/titles/?xsp={{"rules":{{"and":[{{"field":"path","operator":"is","value":'
                         '["$INFO[{item}.Path]"]}}]}},"type":"tvshows"}}'))


def titles(item):
    return '[' + ' | '.join('String.IsEqual({}.DBType,{})'.format(item, t) for t in TITLE_TYPES) + ']'


def rows(page):
    return [BASE[page] + '0{}'.format(n) for n in range(1, 9)]


def _definitions(tag):
    import xml.etree.ElementTree as ET
    out = {}
    for path in sorted((ROOT / '1080i').glob('*.xml')):
        if path.name in ('Includes_Sections.xml',) or not path.name.startswith(('Includes', 'Variables')):
            continue
        for el in ET.parse(path).getroot().iter(tag):
            if el.get('name'):
                out[el.get('name')] = el
    return out


def _item_bound(names, defs, text_of):
    """Of `names`, those whose definition reads ListItem, with what they read in turn."""
    import re
    found, todo = set(), list(names)
    while todo:
        name = todo.pop()
        if name in found or name not in defs:
            continue
        text = text_of(defs[name])
        refs = re.findall(r'\$VAR\[(\w+)', text)
        todo += refs
        if 'ListItem' in text or any(r in found for r in refs):
            found.add(name)
    # a variable that reads one of the found ones reads ListItem too
    changed = True
    while changed:
        changed = False
        for name in names:
            if name in defs and name not in found and any(r in found for r in re.findall(r'\$VAR\[(\w+)', text_of(defs[name]))):
                found.add(name)
                changed = True
    return found


def _for_row(text, row, variables, expressions):
    """`text` of the follow hero for the current title of list `row`."""
    import re
    text = re.sub(r'(?<![\w).])ListItem(?=[.")])', 'Container({}).ListItem'.format(row), text)
    text = re.sub(r'\$VAR\[(\w+)', lambda m: '$VAR[{}{}'.format(m.group(1), row) if m.group(1) in variables else m.group(0), text)
    text = re.sub(r'\$EXP\[(\w+)\]', lambda m: '$EXP[{}{}]'.format(m.group(1), row) if m.group(1) in expressions else m.group(0), text)
    return text


def peek_parts():
    import re
    import xml.etree.ElementTree as ET
    follow = next(i for i in ET.parse(ROOT / '1080i' / 'Includes_Home.xml').getroot().iter('include')
                  if i.get('name') == 'FollowHero').find('control')
    # what the copies take: the group's content, not its visible (SpotlightFollows)
    body = ''.join(ET.tostring(c, encoding='unicode') for c in follow if c.tag != 'visible')
    var_defs, exp_defs = _definitions('variable'), _definitions('expression')
    variables = _item_bound(set(re.findall(r'\$VAR\[(\w+)', body)), var_defs, lambda el: ET.tostring(el, encoding='unicode'))
    expressions = {n for n in re.findall(r'\$EXP\[(\w+)\]', body) if n in exp_defs and 'ListItem' in (exp_defs[n].text or '')}
    # the hero's own controls carry no ids in the copies: one id, one control
    for el in follow.iter():
        if el.tag == 'param' and el.get('name', '').endswith('id'):
            el.set('value', '0')
    # the copies swap at once (the same title from the menu onto its card, row to row); the group
    # of the page fades as FollowHero does
    swap = [c for c in follow if c.tag == 'animation' or (c.tag == 'include' and not c.get('content'))]
    inner = ''.join(ET.tostring(c, encoding='unicode') for c in follow if c.tag != 'visible' and c not in swap)
    fades = ''.join(ET.tostring(c, encoding='unicode') for c in swap)
    out = ['    <!-- The hero of a still spotlight (see tools/make_sections.py peek_parts) -->']
    for page in PAGES:
        cap = page.capitalize()
        # also on a card: its title is the current one of its row, which names itself on focus
        out.append('    <expression name="PeekOn{}">{} + $EXP[SpotlightStill{}]</expression>'.format(
            cap, escape(PAGE_SHOWN[page]), cap))
        for row in rows(page):
            out.append('    <expression name="PeekTitle{0}">Control.IsVisible({0}) + Integer.IsGreater(Container({0}).NumItems,0) + {1}</expression>'.format(
                row, titles('Container({}).ListItem'.format(row))))
        prop = 'Window(Home).Property(nc.peek.{})'.format(page)
        kept = ' | '.join('[String.IsEqual({},{}) + $EXP[PeekTitle{}]]'.format(prop, row, row) for row in rows(page))
        out.append('    <expression name="PeekKept{}">{}</expression>'.format(cap, kept))
        for i, row in enumerate(rows(page)):
            first = ' + '.join(['$EXP[PeekTitle{}]'.format(row)] + ['!$EXP[PeekTitle{}]'.format(r) for r in rows(page)[:i]])
            out.append('    <expression name="PeekRow{0}">$EXP[PeekOn{1}] + [[String.IsEqual({2},{0}) + $EXP[PeekTitle{0}]] | [!$EXP[PeekKept{1}] + {3}]]</expression>'.format(
                row, cap, prop, first))
        out.append('    <expression name="PeekAny{}">{}</expression>'.format(cap, ' | '.join('$EXP[PeekRow{}]'.format(r) for r in rows(page))))
        # the shown title is none the play button plays (a season, a card without library id): its page
        for row in rows(page):
            item = 'Container({}).ListItem'.format(row)
            plays = ' | '.join('String.IsEqual({}.DBType,{})'.format(item, kind) for kind, _ in PLAYS)
            out.append('    <expression name="PeekNoPlay{0}">$EXP[PeekRow{0}] + ![[{1}] + !String.IsEmpty({2}.DBID)]</expression>'.format(row, plays, item))
        out.append('    <expression name="PeekNoPlay{}">{}</expression>'.format(cap, ' | '.join('$EXP[PeekNoPlay{}]'.format(r) for r in rows(page))))
    out += peek_variables()
    # the variables and expressions of the follow hero, once per row
    for page in PAGES:
        for row in rows(page):
            for name in sorted(variables):
                el = var_defs[name]
                text = _for_row(ET.tostring(el, encoding='unicode'), row, variables, expressions)
                text = text.replace('name="{}"'.format(name), 'name="{}{}"'.format(name, row), 1)
                out.append('    ' + text.strip())
            for name in sorted(expressions):
                out.append('    <expression name="{}{}">{}</expression>'.format(
                    name, row, escape(_for_row(exp_defs[name].text, row, variables, expressions))))
    # per page, which Home builds only while that page stands still (Home.xml, Includes_Home.xml):
    # the heroes, one group per row (the service looks at them), their backdrops, Down onto the
    # title and what the buttons do with it
    for page in PAGES:
        cap = page.capitalize()
        out += ['    <include name="PeekHeroes{}">'.format(cap), '        <control type="group">',
                '            <visible>$EXP[PeekAny{}]</visible>'.format(cap), '            ' + fades]
        for n, row in enumerate(rows(page), 1):
            out.append('            <control type="group" id="{}">'.format(PEEK_ID[page] + n))
            out.append('                <visible>$EXP[PeekRow{}]</visible>'.format(row))
            out.append('                ' + _for_row(inner, row, variables, expressions))
            out.append('            </control>')
        out += ['        </control>', '    </include>']
        out.append('    <include name="PeekFanarts{}">'.format(cap))
        for row in rows(page):
            out += ['        <include content="LookHomeFanart">',
                    '            ' + param('art', 'Container({}).ListItem.Art(fanart)'.format(row)),
                    '            ' + param('shown', '$EXP[PeekRow{0}] + !String.IsEmpty(Container({0}).ListItem.Art(fanart))'.format(row)),
                    '        </include>']
        out.append('    </include>')
        out.append('    <include name="PeekDown{}">'.format(cap))
        out += ['        <ondown condition="$EXP[PeekRow{0}]">SetFocus({0})</ondown>'.format(row) for row in rows(page)]
        out.append('    </include>')
        # play: a movie or an episode plays (resuming), a show opens its next episode as on its
        # card; anything else opens its page from its card, as OK on it, and back returns to button
        out += ['    <include name="PeekPlay{}">'.format(cap), '        <param name="button"/>', '        <definition>']
        for row in rows(page):
            item = 'Container({}).ListItem'.format(row)
            for kind, act in PLAYS:
                cond = '$EXP[PeekRow{0}] + String.IsEqual({1}.DBType,{2}) + !String.IsEmpty({1}.DBID)'.format(row, item, kind)
                out.append('            ' + action('onclick', act.format(item=item), cond))
        for row in rows(page):
            out.append('            ' + action('onclick', 'SetProperty(nc.spot.back,$PARAM[button],home)', '$EXP[PeekNoPlay{}]'.format(row)))
            out.append('            ' + action('onclick', 'SetFocus({})'.format(row), '$EXP[PeekNoPlay{}]'.format(row)))
        out.append('            ' + action('onclick', 'Action(Info)', '$EXP[PeekNoPlay{}]'.format(cap)))
        out += ['        </definition>', '    </include>']
        # info: the page of the title, opened on its card; the button sets nc.spot.back and runs Action(Info)
        out.append('    <include name="PeekInfo{}">'.format(cap))
        out += ['        ' + action('onclick', 'SetFocus({})'.format(row), '$EXP[PeekRow{}]'.format(row)) for row in rows(page)]
        out.append('    </include>')
    return out


def peek_variables():
    """Play label and one-item path of the title a still hero shows, for its buttons."""
    out = ['    <variable name="PeekPlayLabel">']
    for page in PAGES:
        for row in rows(page):
            item = 'Container({}).ListItem'.format(row)
            out.append('        <value condition="$EXP[PeekRow{0}] + {1}.IsResumable">▶ $LOCALIZE[31043] $INFO[{1}.PercentPlayed]%</value>'.format(row, item))
            out.append('        <value condition="$EXP[PeekRow{0}] + String.IsEqual({1}.DBType,tvshow)">▶ $LOCALIZE[31106]</value>'.format(row, item))
    out += ['        <value>▶ $LOCALIZE[31010]</value>', '    </variable>']
    out.append('    <variable name="PeekItemPath">')
    for page in PAGES:
        for row in rows(page):
            item = 'Container({}).ListItem'.format(row)
            for kind, path in ITEM_PATHS:
                out.append('        <value condition="$EXP[PeekRow{0}] + String.IsEqual({1}.DBType,{2}) + !String.IsEmpty({1}.DBID)">{3}</value>'.format(
                    row, item, kind, escape(path.format(item=item))))
    out += ['        <value>videodb://movies/titles/?xsp={"type":"movies","limit":1}</value>', '    </variable>']
    return out


def render():
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<!-- Generated by tools/make_sections.py from the catalogue in scripts/nightcity.py: do not',
           '     edit, run the tool. Rows of the home pages and their rows in the skin settings. -->',
           '<includes>',
           '    <!-- An empty slot: hidden, so a move passes on to its neighbour -->',
           '    <include name="SlotPlaceholder">',
           '        <param name="id"/>',
           '        <definition>',
           '            <control type="group" id="$PARAM[id]">',
           '                <visible>false</visible>',
           '            </control>',
           '        </definition>',
           '    </include>']
    for page in PAGES:
        out += slot_include(page) + loader_include(page) + slots_include(page)
    out += row_numbers() + trending_variables() + settings_defaults()
    for page in PAGES:
        out += settings_header(page) + settings_slots(page)
    out += settings_variables()
    out += peek_parts()
    out.append('</includes>')
    return '\n'.join(out) + '\n'


def main(argv):
    text = render()
    if '--check' in argv:
        return 0 if TARGET.read_text(encoding='utf-8') == text else 1
    TARGET.write_text(text, encoding='utf-8')
    print('wrote', TARGET.relative_to(ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
