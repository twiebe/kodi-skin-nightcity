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
genre tabs B30 (tabs B31-B34, gaps B41-B45). Skin settings (SkinSettings.xml), page base S (home
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
GENRES = {'movies': ('movies', 'genre', 'GenrePickLabel', 'genre_pick'),
          'shows': ('tvshows', 'tvgenre', 'ShowGenrePickLabel', 'genre_pick:tvshow')}


def pl(name):
    return 'special://skin/playlists/{}.xsp'.format(name)


IN_PROGRESS = {'movies': [pl('WidgetInProgressMovies')], 'shows': [pl('WidgetInProgressEpisodes')]}
UNWATCHED = {'movies': [pl('WidgetUnwatchedMovies')], 'shows': [pl('WidgetUnwatchedShows')]}
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
    if key == 'unwatched':
        return {'content': both(UNWATCHED)[kind]}
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


def param(name, value):
    return '<param name="{}" value="{}"/>'.format(name, value)


def slot_include(page):
    base = BASE[page]
    out = ['    <!-- One slot of the {} page: the row of its section (n, up and down from {}Slots) -->'.format(page, page.capitalize()),
           '    <include name="{}Slot">'.format(page.capitalize()),
           '        <param name="n"/>', '        <param name="up"/>', '        <param name="down" default="noop"/>']
    out += ['        <param name="def_{}" default="false"/>'.format(key) for key, _ in nightcity.CATALOGUE[page]]
    out.append('        <definition>')
    for key, kind, values, value in variants(page):
        row = section(page, key, kind)
        cond = ' + '.join(c for c in (key_match(page, key), opt_match(page, values, value) if values else '') if c)
        loader = base + '2$PARAM[n]' if row.get('wait') else base + '0$PARAM[n]'
        params = [param('id', base + '0$PARAM[n]'), param('group', base + '1$PARAM[n]'),
                  param('up', base + '30' if row.get('genres') else '$PARAM[up]'), param('down', '$PARAM[down]'),
                  param('label', '$LOCALIZE[{}]'.format(nightcity.SECTIONS[key][0])),
                  param('content1', row['content'][0])]
        if len(row['content']) > 1:
            params.append(param('content2', row['content'][1]))
        params.append(param('loader', loader))
        if row.get('wait'):
            params.append(param('wait', 'true'))
        for extra in ('click', 'art'):
            if extra in row:
                params.append(param(extra, row[extra]))
        nested = []
        if row.get('genres'):
            db, prop, label, pick = GENRES[row['genres']]
            params += [param('titlevisible', 'false'), param('sortby', 'dateadded'),
                       param('sortorder', 'descending'), param('limit', '25')]
            # the list, not the tabs: a selector is skipped from above (DESIGN.md)
            nested = ['<defaultcontrol always="true">{}0$PARAM[n]</defaultcontrol>'.format(base),
                      '<include content="GenreTabs">',
                      '    ' + param('base', base), '    ' + param('list', base + '0$PARAM[n]'),
                      '    ' + param('up', '$PARAM[up]'), '    ' + param('prop', prop),
                      '    ' + param('picklabel', '$VAR[{}]'.format(label)),
                      '    ' + param('pick', pick), '</include>']
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
    empty, home = 'String.IsEmpty(Skin.String(nc.shows.interval))', 'String.IsEmpty(Skin.String(SpotlightInterval))'
    out.append('        <onload condition="{} + {}">Skin.SetString(nc.shows.interval,15)</onload>'.format(empty, home))
    out.append('        <onload condition="{} + !{}">Skin.SetString(nc.shows.interval,$INFO[Skin.String(SpotlightInterval)])</onload>'.format(empty, home))
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
           '         actions of its rows) -->',
           '    <include name="HomePagesSlots{}">'.format(page.capitalize()),
           '        <control type="group">',
           '            <left>560</left>',
           '            <top>256</top>',
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
# value '' is stored as an empty string. Movies shares the interval with home (one spotlight).
SOURCE = {'home': ('SpotlightSource', ['', 'unwatched', 'off'], 'SpotlightSourceLabel'),
          'movies': ('nc.movies.spotlight', ['all', 'unwatched', 'off'], 'MoviesSpotlightLabel'),
          'shows': ('nc.shows.spotlight', ['', 'unwatched', 'off'], 'ShowsSpotlightLabel')}
HOME_INTERVAL = ('SpotlightInterval', ['10', '', '30', '60', 'off'], 'SpotlightIntervalLabel')
INTERVAL = {'home': HOME_INTERVAL, 'movies': HOME_INTERVAL,
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
    out += trending_variables() + settings_defaults()
    for page in PAGES:
        out += settings_header(page) + settings_slots(page)
    out += settings_variables()
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
