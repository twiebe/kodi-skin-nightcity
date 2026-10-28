# Nightcity

A Kodi 21 skin with a calm cyberpunk look ("Netrunner"): dark backgrounds, cyan with pink accents, cut corners instead of framed boxes, and the artwork of your movies and shows in front.

Video only: home with a spotlight and widget rows, video library, info page, playback and the dialogs Kodi needs. Ratings come from [TMDb Helper](https://github.com/jurialmunkey/plugin.video.themoviedb.helper), which is a required dependency.

## Features

- Netrunner look: cut-corner cards and buttons, small spaced headings above the rows, a glitch title for the focused item, a path line at the top
- Home pages: home, movies, shows, search, system, power. The page switches as you move along the menu, no click needed. The fanart of the focused item fills the background, the hero shows its poster, tags, rating and plot
- Spotlight with random movies or shows: left on the play button goes back, right on the info button goes forward
- Rows: 8 slots per page (home, movies, shows) from a fixed catalogue in the skin settings (categories home, movies, shows): continue watching, next up, new movies, new episodes, genres, random movies, unwatched, top rated, favourites, TMDb trending, recently watched, sets, in progress; OK picks a section, right its option, "Move" reorders; spotlight per page (source, interval or off) and main menu entries to hide
- "all movies" / "all shows": a full poster grid, sortable by title, year, date added or rating
- Search page: a field for the keyboard, the last five terms, rows of library movies, shows and episodes and of TMDb movies and shows
- Settings console: the system page has one tile per group (playback and media, look and profiles, add-ons and content, system and network, tools). OK opens a rail with all settings entries under their group headings; the focused entry shows its categories on the right, and OK on one opens Kodi's page right at that category. Live TV shows up with a PVR client. Event log page
- Power page: device name, uptime, memory, address and temperature, tiles for power off, reboot, suspend, exit and restart (all but suspend ask first)
- Info page instead of a play/resume prompt: episodes show season tabs and the episode list with the clicked episode selected, resume and from start; movies show details, cast with photos and similar movies (TMDb Helper)
- Player: thin seek bar with buffer, chapter ticks and a time bubble while seeking; OSD with play controls and stop, chapters, video settings, and track panels for subtitles and audio: move up from the button into the list, a click switches the track, the last row opens the full settings
- After an episode started from its info page stops, the info page comes back on the episode that played last
- Palettes: Netrunner (default), Tokyo Night, Catppuccin (Mocha)
- Fonts: Rajdhani for text, Share Tech Mono for numbers and times
- Optional focus glow (skin settings)

## Usage notes

- On first start the skin sets Kodi's "Settings > Media > Videos > Default select action" to "Show information" once, so a click in the library opens the info page too. Change it back there if you prefer; the skin does not set it again.
- A click on a show opens the info page of its next episode: the started one, else the first unwatched, else the first.

## Install

1. Install jurialmunkey's repository (`https://jurialmunkey.github.io/repository.jurialmunkey/`), which carries TMDb Helper 6.17.9 or newer; the official Kodi repository only has an older one. Kodi installs TMDb Helper with the skin.
2. Build the zip with `python tools/build.py` (writes `/dist/skin.nightcity-<version>.zip`) or take it from a release.
3. Kodi: Settings > Add-ons > Install from zip file, then switch the skin under Settings > Interface > Skin.

## Development

```
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest tests/static -q
.venv/bin/pytest tests/unit -q
.venv/bin/pytest tests/e2e -q -m e2e   # needs the kodi-dev environment, see tools/kodidev_setup.py
```

The e2e suite runs in parallel on a kodi-dev pool (several environments, each with its own Kodi and Jellyfin, see the kodi-dev README), one pytest-xdist worker per Kodi. The pool copies kodi-dev's `data/` as its template, so run `tools/kodidev_setup.py` before the first `pool up`: it also adds the titles the TMDb tests open. Each test run restarts the pool Kodis, so the skin's startup is the working tree's. `--dist loadfile` keeps each file on one Kodi, some files rely on their test order. `-m "e2e and not slow"` leaves out the tests that take more than 20 s.

```
/workspaces/kodi-dev/kdev pool up --skin "$PWD"   # this checkout in every worker
KDEV_POOL=1 .venv/bin/pytest tests/e2e -q -m e2e -n auto --dist loadfile
```

The player tests write a clip with two audio tracks, two subtitles and three chapters with `tools/make_tracks_clip.py` (needs ffmpeg).

## Credits

- [Arctic Fuse 3](https://github.com/jurialmunkey/skin.arctic.fuse.3) by jurialmunkey: the reference for the home layout and the TMDb Helper integration.
- [TMDb Helper](https://github.com/jurialmunkey/plugin.video.themoviedb.helper) by jurialmunkey: online movie and TV data.
- Cyberpunk 2077 by CD Projekt Red: the inspiration for the look; no assets are taken from it.
- [Rajdhani](https://fonts.google.com/specimen/Rajdhani) by Indian Type Foundry and [Share Tech Mono](https://fonts.google.com/specimen/Share+Tech+Mono) by Carrois Apostrophe, under the SIL Open Font License 1.1. `tools/make_fonts.py` builds the RetroUI fonts from Rajdhani plus symbols from [Noto Sans Symbols 2](https://fonts.google.com/noto/specimen/Noto+Sans+Symbols+2) and [JetBrains Mono](https://www.jetbrains.com/lp/mono/) (both OFL); RetroUI and RetroUIWide are renamed derivatives under the same license.
- Colour palettes after [Tokyo Night](https://github.com/folke/tokyonight.nvim) and [Catppuccin](https://catppuccin.com).
- Control ids follow Kodi's window code and Estuary; no Estuary layout is copied.

## License

[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/), see [LICENSE.txt](LICENSE.txt). Fonts are under the SIL Open Font License 1.1.
