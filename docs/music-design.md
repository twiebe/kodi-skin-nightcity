# Music in Nightcity: prototype design

Status: prototype on `feature/music`. Goal: the user's own music library (Kodi's music database,
filled by Jellyfin for Kodi or a library scan) usable from the remote, with the same rules as the
video side (DESIGN.md).

## What Arctic Fuse 3 does, and what we take

AF3 has no music hub and no default music widgets. Music goes through Kodi's own music windows,
plus a widget picker with music paths, an info dialog, an OSD track picker and the visualisation.

Taken:

- The library paths: `musicdb://recentlyaddedalbums/`, `musicdb://recentlyplayedalbums/`, random
  albums as a smart playlist, `musicdb://artists/`, `musicdb://genres/`.
- DialogMusicInfo: Kodi fills list 50 (an album's tracks, an artist's discography). The Kodi
  buttons keep their ids: 8 plays the album, 12 opens the artist.
- Album and artist text: `ListItem.Property(Album_Description)`, `Property(Artist_Description)`,
  `Property(Album_Label)`, `Property(Artist_Genre)`.
- The OSD track list from `playlistmusic://`, playing a track at a chosen position.
- Now playing: `MusicPlayer.*` / `Player.Art(...)` labels, next track from `MusicPlayer.offset(1)`.

Not taken: the look, script.skinvariables (encoded xsp strings), script.playalbum (Kodi's button
8 and a JSON-RPC call in our script do the same), ArtistSlideshow and lyrics add-ons, the settings
dialog of the visualisation.

## Screens and flows

### Music page on Home

- A top menu entry **Music** between Shows and Search (tab 9107). Hidden when the library has no
  music (`Library.HasContent(music)`) and by the switch in the skin settings, menu category
  (`nc.menu.hide.music`), like movies, shows and search.
- Focus on the tab switches the page (focus applies). Down goes into the page.
- Spotlight (list 9002): random albums, rotating with the home spotlight interval; a switch to
  the page moves it on by one, like the other spotlights. Hero: square cover, kicker artist,
  title, year and genre tags, the album description.
- Spotlight buttons: **Play** (the album), **Info** (album page), **Albums »** (the music library).
  Left on Play: previous album, right on the last button: next album (same as the movie spotlight).
  While music plays, **Now playing** comes first and opens the player screen.
- Rows below (one at a time, like every page): recently added albums, recently played albums,
  random albums, artists, genres. Square cards, title and artist under the card.
  OK on an album or artist opens its info page; OK on a genre opens the library on that genre.
- Up from the first row: the spotlight buttons; Up from there: the menu tab.

### Library (MyMusicNav)

Kodi's own music browsing (artists, albums, songs, genres) in the look of the video library:
list 50 with a detail pane (square art, artist, year, description), a square card wall (51),
view and sort on the right (9060). Kodi's select action: folders open, songs play.

### Album and artist page (DialogMusicInfo)

Walks top down like the video info page:

- Head: square cover (artist: photo), kicker (artist; artist page: genre), title, tags (year,
  genre, label, length), rating, description.
- Buttons (9000): Play (Kodi 8), the artist (Kodi 12, album only). Up from the buttons leaves the
  page (Back), as on the video info page.
- Down: the tracks (list 50, a vertical list with number, title, length). OK plays the album from
  that track.
- Artist page: Down from the buttons, the albums (Kodi's list 50 as cover cards); OK opens the
  album page (Kodi switches the dialog over).
- Album page: Down from the tracks, **More by the artist** (5300, the artist's other albums); OK
  opens that album's page (script: closes this one and opens the next).

### Now playing (MusicVisualisation + MusicOSD)

- The player screen: the artist's fanart behind, Kodi's visualisation if one is set, the cover,
  artist, title, album and year, the next track, a progress line with times.
- OK opens the OSD (Kodi's keymap): playback buttons left (previous, play/pause, next, stop),
  shuffle and repeat right. Down: **Up next**, the play queue as a row of cards with the playing
  track selected; OK plays that track. Up from the row: the buttons. Up from the buttons: nothing
  (as in the video OSD); Back closes the OSD.
- Auto-hide: the same switch and delay as the video OSD (`nc.osd.autohide.off`,
  `nc.osd.hide.wait`), own timer `nc_musicosd_hide`.

### Now playing on Home

While music plays, the top line shows a small "▶ title · artist" left of the quick menu icon.
Not focusable; the Music page's Now playing button opens the player.

## DESIGN.md mapping

- Up/Left one level up, Down/Right down: page tab, spotlight buttons, rows; info head, buttons,
  tracks, more by; OSD buttons, queue row.
- No dead ends: every new window is in the static navigation tests (`test_navigation.py`).
- Back returns where you left: info pages open from Home and close back onto the card. Switching
  album to album inside the info page does not chain back (open question).
- Selectors skipped from above: none in the prototype (no tabs).
- Focus applies, OK goes: the menu tab switches the page on focus; everything that leaves the view
  (play, info, library, queue item) needs OK.
- Staggered fades: the Music page builds up with PageFade like the others (hero head, hero rest,
  rows).

## Open for later

- Configurable music rows (slot catalogue like home/movies/shows).
- Back chain between album and artist pages (like the TMDb chain).
- Song info (DialogSongInfo shares DialogMusicInfo.xml), playlists, music videos, lyrics.
- Party mode / shuffle all from the Music page.
