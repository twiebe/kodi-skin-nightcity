#!/usr/bin/env python3
"""Make kodi-dev (/workspaces/kodi-dev) run this skin. Idempotent.

- mounts this checkout as skin.nightcity and the assembled _build/confuse as skin.confuse via
  compose.override.yaml (the add-on in .env stays untouched)
- installs the TMDb Helper fork and its dependencies (kodi-dev/perf/setup_skin.py)
- selects the skin of --skin (default nightcity) in guisettings.xml while Kodi is stopped, then
  starts kodi-dev
- adds the titles the TMDb tests open (The Matrix, Breaking Bad) to Jellyfin's media

A kdev pool copies data/ as its template, so run this before the first `kdev pool up`.
"""
import argparse
import pathlib
import re
import shutil
import subprocess

from build import assemble

ROOT = pathlib.Path(__file__).resolve().parents[1]
KODI_DEV = pathlib.Path('/workspaces/kodi-dev')
TMDB_HELPER = pathlib.Path('/workspaces/plugin-video-themoviedb-helper')
CONFUSE = ROOT / '_build' / 'confuse'
MOUNTS = ('{}:/home/kodi/.kodi/addons/skin.nightcity'.format(ROOT),
          '{}:/home/kodi/.kodi/addons/skin.confuse'.format(CONFUSE))
GUISETTINGS = KODI_DEV / 'data' / 'kodi' / 'userdata' / 'guisettings.xml'


# Titles TMDb Helper knows, so cast, crew and similar rows fill: name, year, folder, uniqueids
MATRIX = ('The Matrix', 1999, 'A hacker learns what the Matrix is.',
          '<uniqueid type="imdb" default="true">tt0133093</uniqueid><uniqueid type="tmdb">603</uniqueid>')
BREAKING_BAD = ('Breaking Bad', 2008, 'A chemistry teacher turns to making meth.',
                '<uniqueid type="tmdb" default="true">1396</uniqueid><uniqueid type="imdb">tt0903747</uniqueid>'
                '<uniqueid type="tvdb">81189</uniqueid>')
NFO = '<?xml version="1.0" encoding="UTF-8"?>\n<{0}>{1}</{0}>\n'


def _write(path, text=None, clip=None):
    """Write PATH unless it exists (text, or a hard link to / copy of CLIP); True if written."""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    if clip is None:
        path.write_text(text)
    else:
        try:
            path.hardlink_to(clip)
        except OSError:
            shutil.copy(clip, path)
    return True


def add_tmdb_titles(media):
    """The Matrix and three episodes of Breaking Bad in MEDIA (a kodi-dev media folder), made
    from the clip of Kdev Alpha; True if something was added."""
    clip = media / 'movies' / 'Kdev Alpha (2001)' / 'Kdev Alpha (2001).mkv'
    added = False
    title, year, plot, ids = MATRIX
    movie = media / 'movies' / '{} ({})'.format(title, year) / '{} ({})'.format(title, year)
    added |= _write(movie.with_suffix('.mkv'), clip=clip)
    added |= _write(movie.with_suffix('.nfo'), NFO.format(
        'movie', '<title>{}</title><year>{}</year><plot>{}</plot>{}'.format(title, year, plot, ids)))
    title, year, plot, ids = BREAKING_BAD
    show = media / 'shows' / title
    added |= _write(show / 'tvshow.nfo', NFO.format(
        'tvshow', '<title>{}</title><year>{}</year><plot>{}</plot>{}'.format(title, year, plot, ids)))
    for n, name in enumerate(('Pilot', "Cat's in the Bag...", "...And the Bag's in the River"), 1):
        episode = show / 'Season 01' / '{} S01E{:02d}'.format(title, n)
        added |= _write(episode.with_suffix('.mkv'), clip=clip)
        added |= _write(episode.with_suffix('.nfo'), NFO.format(
            'episodedetails', '<title>{}</title><season>1</season><episode>{}</episode>'
            '<plot>Episode {} of {}.</plot>'.format(name.replace("'", '&apos;'), n, n, title)))
    return added


def run(*args, check=True):
    subprocess.run(args, cwd=KODI_DEV, check=check)


def ensure_mounts():
    path = KODI_DEV / 'compose.override.yaml'
    text = path.read_text() if path.exists() else 'services:\n  kodi:\n    volumes:\n'
    for mount in MOUNTS:
        if mount in text:
            continue
        if 'volumes:' not in text:
            raise SystemExit('unexpected compose.override.yaml, add this volume by hand: ' + mount)
        text = text.rstrip('\n') + '\n      - {}\n'.format(mount)
        path.write_text(text)
        print('mounted', mount)


def select_skin(guisettings, skin):
    text = guisettings.read_text()
    new, found = re.subn(r'<setting id="lookandfeel.skin"[^>]*>[^<]*</setting>',
                         '<setting id="lookandfeel.skin">skin.{}</setting>'.format(skin), text)
    if not found:
        raise SystemExit('no setting lookandfeel.skin in {}'.format(guisettings))
    if new != text:
        guisettings.write_text(new)
        print('selected skin.{}'.format(skin))


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--skin', choices=('nightcity', 'confuse'), default='nightcity',
                        help='the skin kodi-dev starts with; both are mounted either way')
    return parser.parse_args(argv)


def main():
    args = parse_args()
    assemble('confuse', CONFUSE)
    ensure_mounts()
    run('docker', 'compose', 'stop', 'kodi')
    run('python3', str(KODI_DEV / 'perf' / 'setup_skin.py'), '--local', str(TMDB_HELPER))
    select_skin(GUISETTINGS, args.skin)
    run('./kdev', 'up')
    if add_tmdb_titles(KODI_DEV / 'data' / 'media'):
        # Jellyfin for Kodi syncs them into Kodi's library when the scan reports them
        run('./kdev', 'jf', 'POST', '/Library/Refresh')
    # A freshly mounted add-on is only enabled by kdev after Kodi has already tried (and failed) to
    # load it as skin, so restart once with the skin enabled.
    # jellyfin-kodi plays the synced library items (plugin://plugin.video.jellyfin/...)
    for addon_id in ('skin.nightcity', 'skin.confuse', 'plugin.video.jellyfin'):
        run('./kdev', 'rpc', 'Addons.SetAddonEnabled', '{"addonid": "%s", "enabled": true}' % addon_id,
            check=False)  # fails when it is already enabled
    run('./kdev', 'restart')


if __name__ == '__main__':
    main()
