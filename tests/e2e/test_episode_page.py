"""The page of an episode opens on that episode. The page keeps the lists of the page before while
its own load, and the library holds its rows in no set order. The show here has them as a library
gets them when seasons or episodes are added again later: season 2 before season 1, in season 2
episode 14 before episode 1. When info_select found the season missing in the tabs of the show
before, or gave up on tabs that took too long, the page stayed where the new lists came up: the
tabs on the place the page before left them (or the first), the row on its first card. So S02E14,
1 of 23, also in a library with its seasons in order, after a page on its second tab."""
import sqlite3
import time

import pytest

from conftest import _data, _wait_for_service, builtin, info, kdev, rpc, wait_for

pytestmark = pytest.mark.e2e

FROM = 500000  # ids of the rows added here
SEASONS = [2, 1] + list(range(3, 11))
SHOW_LIKE = 'Kdev Show'  # the show and the path to copy
SLOW_FOR = 9.0  # s the seasons take to list
ORIGINAL = 'nc_test_season_view'


def _database():
    database = sorted((_data() / 'kodi' / 'userdata' / 'Database').glob('MyVideos*.db'))[-1]
    return sqlite3.connect(str(database), timeout=30)


def _change(change):
    connection = _database()
    with connection:
        change(connection)
    connection.close()


def _columns(connection, table):
    return [row[1] for row in connection.execute('PRAGMA table_info({})'.format(table))]


def _remove(connection):
    for table, key in (('episode', 'idEpisode'), ('seasons', 'idSeason'), ('tvshow', 'idShow'),
                       ('tvshowlinkpath', 'idShow'), ('bookmark', 'idFile'), ('files', 'idFile')):
        connection.execute('DELETE FROM {} WHERE {} >= ?'.format(table, key), (FROM,))


def _show_like():
    connection = _database()
    show = connection.execute('SELECT idShow FROM tvshow WHERE c00 = ?', (SHOW_LIKE,)).fetchone()[0]
    connection.close()
    return show


def _add(connection):
    like = connection.execute('SELECT idShow FROM tvshow WHERE c00 = ?', (SHOW_LIKE,)).fetchone()[0]
    columns = _columns(connection, 'tvshow')
    picked = {'idShow': str(FROM), 'c00': "'Nc Season Order'"}
    connection.execute('INSERT INTO tvshow ({}) SELECT {} FROM tvshow WHERE idShow = ?'.format(
        ','.join(columns), ','.join(picked.get(c, c) for c in columns)), (like,))
    path = connection.execute('SELECT idPath FROM tvshowlinkpath WHERE idShow = ?', (like,)).fetchone()[0]
    connection.execute('INSERT INTO tvshowlinkpath VALUES (?, ?)', (FROM, path))
    file_path = connection.execute('SELECT strPath FROM path WHERE idPath = ?', (path,)).fetchone()[0]
    columns = _columns(connection, 'episode')
    row = FROM
    for position, season in enumerate(SEASONS):
        connection.execute('INSERT INTO seasons (idSeason, idShow, season, name) VALUES (?, ?, ?, ?)',
                           (FROM + position, FROM, season, 'Season {}'.format(season)))
        numbers = list(range(14, 24)) + list(range(1, 14)) if season == 2 else range(1, 6)
        for number in numbers:
            name = '{}?filename=nc{}x{}.mkv&id=nc{}&dbid={}&mode=play'.format(file_path, season, number, row, row)
            connection.execute('INSERT INTO files (idFile, idPath, strFilename) VALUES (?, ?, ?)', (row, path, name))
            values = {'idEpisode': row, 'idFile': row, 'c00': 'S{}E{}'.format(season, number), 'c12': str(season),
                      'c13': str(number), 'c18': name, 'idShow': FROM, 'idSeason': FROM + position}
            connection.execute('INSERT INTO episode ({}) VALUES ({})'.format(','.join(columns), ','.join('?' * len(columns))),
                               [values.get(c) for c in columns])
            if (season, number) == (10, 3):
                connection.execute("INSERT INTO bookmark (idFile, timeInSeconds, totalTimeInSeconds, player, type) "
                                   "VALUES (?, 600, 1800, 'VideoPlayer', 1)", (row,))
            row += 1
    # the row Kodi keeps for all seasons of a show, the last one Jellyfin for Kodi adds
    connection.execute('INSERT INTO seasons (idSeason, idShow, season) VALUES (?, ?, -1)', (FROM + len(SEASONS), FROM))


def _restore_seasons(connection):
    saved = connection.execute("SELECT sql FROM sqlite_master WHERE name = ?", (ORIGINAL,)).fetchone()
    if saved:
        connection.execute('DROP VIEW season_view')
        connection.execute(saved[0].replace(ORIGINAL, 'season_view', 1))
        connection.execute('DROP VIEW {}'.format(ORIGINAL))


COUNTER = '(WITH RECURSIVE c(x) AS (VALUES(1) UNION ALL SELECT x + 1 FROM c WHERE x < {}) SELECT count(*) AS n FROM c)'


def _count_in_seasons(rows):
    def change(connection):
        _restore_seasons(connection)
        create = connection.execute("SELECT sql FROM sqlite_master WHERE name = 'season_view'").fetchone()[0]
        connection.execute(create.replace('season_view', ORIGINAL, 1))
        connection.execute('DROP VIEW season_view')
        connection.execute('CREATE VIEW season_view AS SELECT v.* FROM {} v JOIN {} t ON t.n > 0'.format(
            ORIGINAL, COUNTER.format(rows)))
    _change(change)


def _slow_seasons(show):
    """Make the query behind the season tabs take SLOW_FOR seconds, as a first read of a big
    library or a Kodi with all its jobs busy does, which this box does not get to on its own.
    The view counts as far as this Kodi gets in that time."""
    sample = 20000000
    _count_in_seasons(sample)
    started = time.time()
    rpc('VideoLibrary.GetSeasons', {'tvshowid': show})
    _count_in_seasons(int(sample * SLOW_FOR / max(time.time() - started, 0.01)))


@pytest.fixture
def season_order(home):
    _change(_restore_seasons)  # a run stopped halfway leaves them behind
    _change(_remove)
    _change(_add)
    yield FROM
    builtin('Dialog.Close(all,true)')
    _change(_restore_seasons)
    _change(_remove)


def _open(show):
    builtin('ClearProperty(nc.info.ready,home)')
    builtin('NotifyAll(nightcity,next_episode:{})'.format(show))
    wait_for('Window.IsActive(movieinformation)', timeout=15)


def _ready():
    wait_for('!String.IsEmpty(Window(Home).Property(nc.info.ready))', timeout=60)


def _page():
    keys = ('Container(5200).ListItem.Season', 'Container(5100).ListItem.Season',
            'Container(5100).ListItem.Episode', 'Container(5100).CurrentItem', 'Container(5100).NumItems')
    got = info(*keys)
    return tuple(got[key] for key in keys)


def _absolute(container, field, count):
    keys = ['Container({}).ListItemAbsolute({}).{}'.format(container, i, field) for i in range(count)]
    got = info(*keys)
    return [got[key] for key in keys]


def test_the_page_opens_on_the_episode(season_order):
    _open(season_order)
    _ready()
    wait_for('Integer.IsGreater(Container(5100).NumItems,0)', timeout=60)
    time.sleep(1)
    assert _page() == ('10', '10', '3', '3', '5')


def test_season_tabs_and_episodes_are_in_order(season_order):
    _open(season_order)
    _ready()
    assert info('Container(5200).NumItems')['Container(5200).NumItems'] == '10'
    assert _absolute(5200, 'Season', 10) == [str(n) for n in range(1, 11)]
    builtin('SetFocus(5200,1,absolute)')
    wait_for('String.IsEqual(Container(5100).ListItem.Season,2) + Integer.IsEqual(Container(5100).NumItems,23)')
    assert _absolute(5100, 'Episode', 23) == [str(n) for n in range(1, 24)]


def test_the_page_after_another_show_opens_on_the_episode(season_order):
    """Kdev Show has one season: season 10 is not in the tabs the page still holds."""
    _open(_show_like())
    _ready()
    builtin('Dialog.Close(all,true)')
    wait_for('!Window.IsActive(movieinformation)')
    _open(season_order)
    _ready()
    wait_for('Integer.IsEqual(Container(5200).NumItems,10)')
    assert _page() == ('10', '10', '3', '3', '5')


def test_slow_seasons_still_open_on_the_episode(season_order):
    """In a new session: nothing is left of a page before."""
    _slow_seasons(season_order)
    kdev('restart')
    kdev('wait')
    _wait_for_service()
    wait_for('Window.IsActive(home)', timeout=60)
    _open(season_order)
    # the seasons are still on their way when the 5 s info_select used to wait have run out
    time.sleep(5.5)
    assert info('Container(5200).NumItems')['Container(5200).NumItems'] == '0'
    _ready()
    wait_for('Integer.IsGreater(Container(5100).NumItems,0)', timeout=60)
    time.sleep(1)
    assert _page() == ('10', '10', '3', '3', '5')
