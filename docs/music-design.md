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
  What plays is reached from the top line (Now playing on Home), not from a button here.
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
- Down: the tracks (5050, two columns of number, title, length). OK plays the album from that
  track and opens the player screen (script `music_play`). Built in the prototype: Kodi's own
  list 50 runs no skin onclick on this page, so the tracks come from the library
  (`musicdb://albums/<id>/`) instead and list 50 is left out. Their group is never hidden by
  its own item count: Kodi fills no hidden list, it would stay empty.
- Artist page: Down from the buttons, the albums as cover cards (5301,
  `musicdb://albums/?artistid=<id>`; Kodi's discography in list 50 has no years or art). OK
  opens that album's page. Play on an artist queues all of its songs.
- Album page: Down from the tracks, **More by the artist** (5301, the artist's other albums); OK
  opens that album's page (script `music_info`: closes this one and opens the next, with the
  art from the library; such a page has no label, so the title comes from the album tag).

### Now playing (MusicVisualisation + MusicOSD)

- Starting music goes straight to the player screen: Play on the spotlight, on an album or
  artist page, OK on a track, playing from the library or Kodi's own play buttons. Back there
  goes to where it was started while the music plays on: Kodi's window before (Home, the
  library), or the album or artist page again (`music_back`, the screen's onunload; the page
  is noted in `nc.music.back` by `music_play`). The page also comes back when the music ends
  on the player screen.
- Music started by Kodi (the library, button 8 of a song page) is told from the next track of
  the queue by Kodi's notices: a new queue is cleared or filled from position 0 right before
  it plays (`MusicStart`, `now_playing`; it waits for Kodi's busy dialog, which drops windows).

- The player screen: the artist's fanart behind, Kodi's visualisation if one is set, the cover,
  artist, title, album and year, the next track, a progress line with times, the place in the
  queue. Kodi's keymap: OK opens the OSD, Up and Down skip tracks, Left and Right step.
- The OSD: playback buttons left (previous, play/pause, next, stop), shuffle and repeat right
  (a dot marks the mode that is on). While it is open, what plays moves up to make room.
  Down: **Up next**, the play queue as a row of cards, the cursor on the next track and the
  playing one marked ▶; OK plays the chosen track (script `music_goto`). Up from the row: the
  buttons. Up from the buttons: nothing (as in the video OSD); Back closes the OSD.
- Auto-hide: the same switch and delay as the video OSD (`nc.osd.autohide.off`,
  `nc.osd.hide.wait`), own timer `nc_musicosd_hide`.

### Now playing on Home

While music plays, the top line shows "▶ title · artist" left of the quick menu icon, on every
page of Home (9108). It takes the focus like the menu tabs and the icon: Right from the last
tab, Left from the icon, Right to the icon (Back in the quick menu comes back to it), Left to
the menu, Down into the shown page. OK opens the player screen; Back there comes back to it.
When the music stops with the focus on it, the focus goes to the shown page's own tab
(`nc_np_gone`): Kodi would put it on Home's default control, maybe of another page.

Kodi itself: Back on Home while anything plays goes to the player (CGUIWindowHome), before a
control's onback. So while music plays Back in the quick menu or on the icon opens the player
screen instead of closing the menu; as with video.

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
