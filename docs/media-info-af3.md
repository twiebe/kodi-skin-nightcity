# Media info: what Arctic Fuse 3 shows, what Nightcity takes over

Reference: Arctic Fuse 3 3.4.12 (`/workspaces/skin-arctic-fuse-3`, with the "Ends at" fix
99010ae), TMDb Helper 6.18.3, Kodi 21.3 sources.

## Arctic Fuse 3

AF3 builds every info panel from one include, `Info_Panel` (`1080i/Includes_Info.xml`). The
same panel stands on the hubs (home), in the library views, in search, in the info dialog
(`Includes_DialogInfo.xml`) and, with the player's labels, in the OSD (`Includes_OSD.xml`).
It has two lines under the title:

- `Info_Line`: pills and labels.
  - Resolution pill (8K, 4K, FHD, HD, SD) from `ListItem.VideoResolution`.
  - HDR pill (DV, HDR10, HLG) from `ListItem.HdrType` and audio channel pill (9.1 down to
    1.0) from `ListItem.AudioChannels`, both behind skin settings (`InfoTags.EnableHDR`,
    `InfoTags.EnableAudioChannels`).
  - Five stars from `ListItem.Rating` (or `UserRating`).
  - MPAA, premiered date, and the runtime as "2h 16m" from `ListItem.Duration(h)` and
    `Duration(m)`.
- `Info_Meta`: icon plus text.
  - Up to three ratings per media type (movies, shows), picked in the skin settings
    (`Skin.String(CustomRating.Movies.Item01..03)`, defaults Trakt and Metacritic). Each
    reads a window property of TMDb Helper's service:
    `Window(Home).Property(TMDbHelper.ListItem.<Source>_Rating)`, or `TMDbHelper.Player.*`
    in the OSD. Sources: IMDb (plus `Top250`), TMDb, Trakt, Rotten Tomatoes critics
    (`RottenTomatoes_Rating`, fresh/rotten logo from `RottenTomatoes_Image`) and audience
    (`RottenTomatoes_UserMeter`), Metacritic, MDbList, Letterboxd, MyAnimeList. The logos are
    PNGs in `extras/flags/<colour>/ratings/`.
  - "Ends at" (string 31600) with a clock icon.
  - Show status and Oscar wins.
- The file properties page of the info dialog lists the codecs as text: video codec,
  resolution, HDR type, aspect, audio codec, channels.

### Ends at

For a library item AF3 shows `ListItem.EndTimeResume`. Kodi computes it as now + (duration -
resume point) (`VideoGUIInfo.cpp`, `LISTITEM_ENDTIME_RESUME`); `ListItem.EndTime` is now +
duration. The duration is the stream's if that is at least 60% of the tag's, else the tag's.
Without a duration both labels give the current time.

Fix 99010ae: when the item on the panel is the one playing, AF3 shows `Player.FinishTime`
(now + remaining play time, divided by the tempo at speed 1) instead, since the stored resume
point is stale during playback and a TMDb Helper item has none. "Playing" means:

- an item with a file: the same `FileNameAndPath` as `Player.FileNameAndPath`, or the same
  DBID as `VideoPlayer.DBID` with the matching content type and the same file name
  (`ListItem.FileNameAndPath` drops `user:pass@`, `Player.FileNameAndPath` keeps it);
- a TMDb Helper item (path `plugin://plugin.video.themoviedb.helper/`): a movie by IMDb id or
  by TMDb id (`TMDbHelper.Player.TMDb_ID`), an episode by the show's TMDb id
  (`TMDbHelper.Player.TVShow.TMDb_ID`), season and episode.

Live TV is left out. The check must stand at window level: inside an item layout Kodi reads
`Player.FileNameAndPath` and `VideoPlayer.*` from the list item, so every item would match.

### Ratings and TMDb Helper

TMDb Helper's service watches the focused item (in an info dialog the dialog's `ListItem`, on
a page the container in `TMDbHelper.WidgetContainer`) and writes its details as
`TMDbHelper.ListItem.*` window properties on Home. `TMDb_Rating` comes with the TMDb details
at once and needs no key. The other ratings come from a second thread
(`TMDbHelper.IsUpdatingRatings` is set while it runs) and need TMDb Helper's "online ratings"
setting (on by default) plus an OMDb or MDbList API key in TMDb Helper; Trakt ratings come
from Trakt. A skin can switch the online ratings off with `Skin.HasSetting(TMDbHelper.DisableRatings)`;
AF3 clears it when a rating slot needs it. For an episode TMDb Helper asks for the episode's
ratings (MDbList returns IMDb episode ratings). Old ratings stay up until the new ones
arrive.

### What Kodi has without TMDb Helper

- `ListItem.Rating` (the default rating) and `ListItem.Rating(name)` per source a scraper
  stored (`imdb`, `themoviedb`, `tmdb`, `trakt` ...). Jellyfin for Kodi stores only Jellyfin's
  community rating, as "default", with no source name.
- `ListItem.VideoResolution` (480, 540, 576, 720, 1080, 4K, 8K), `HdrType` (dolbyvision,
  hdr10, hlg, empty), `VideoCodec`, `VideoAspect`, `AudioCodec`, `AudioChannels`,
  `Duration(mins)`.
- Atmos and DTS:X are not exposed. Kodi stores codec names only (Jellyfin for Kodi maps the
  DTS-HD profiles to `dtshd_ma` / `dtshd_hra`); the player names an E-AC-3 JOC track
  "DD+ ATMOS" only in the audio track list, not in an info label.

## Nightcity before this change

- Home movie hero (`HeroBody` in `Includes_Home.xml`, container 9000): year, runtime in
  minutes, resolution + HDR/SDR, audio codec + channel count; one rating line (TMDb via TMDb
  Helper, else `ListItem.Rating`).
- Info page, movie: year, runtime, genre; the rating line only with `ListItem.Rating` (the
  TMDb Helper value was switched off with `nc.none`), so library movies from Jellyfin showed
  no rating at all. No resolution, HDR or audio.
- Info page, episode: year, runtime, resolution + HDR, audio for the episode selected in list
  5100; the same rating line.
- Player OSD and the info key in fullscreen: resolution, HDR, audio, and "Ends at"
  `Player.FinishTime`.
- Runtime: already in the tags of the hero and the info page ("10 MIN") and in the library
  rows.

## What Nightcity takes over, and where

All of it goes into `HeroBody`, so the info page (movie and episode head) and the home heroes
show the same facts the same way.

- Tags row: year, runtime, **ends at** (new), resolution + HDR/SDR, audio. The movie head of
  the info page now shows resolution and audio too; its genre tag goes (the genre is already
  the kicker above the title).
- Audio as people know it: TrueHD, DD+, DD, DTS-HD MA, DTS, AAC ... and the channel layout
  5.1 / 7.1 instead of "6CH", as the OSD already did. Resolution gets 8K.
- **Ends at** for movies and episodes with a runtime: `EndTimeResume` (so from the resume
  point when there is one), and `Player.FinishTime` when the item is the one playing, with the
  matching of 99010ae. Live TV and items without a runtime show none.
- **Ratings line** with every rating there is, in a fixed order: IMDb (with Top 250 rank),
  TMDb, Rotten Tomatoes critics and audience, Metacritic, Trakt, Letterboxd, MDbList. Values
  come from TMDb Helper; IMDb and TMDb fall back to Kodi's own `Rating(imdb)`,
  `Rating(themoviedb)` / `Rating(tmdb)`; when there is no named rating at all, the plain
  `ListItem.Rating` (as before).

## Design calls

Each with what it costs if it turns out wrong.

1. **Text badges, no logos.** Ratings read "8.7 IMDB  92% RT" in the small caps of the tags,
   value in the text colour, source muted, one accent star in front, like the rating line was
   before. The rating logos are trademarks of their owners and AF3's PNGs are no licence to
   reuse them; text also keeps the calm look. Cost: less recognisable at a glance than logos;
   logos could be added later as small monochrome glyphs.
2. **All ratings, fixed order, no slots.** The user asked for all of them; AF3's three slots
   need a settings page Nightcity does not have. With every key set the line holds eight
   entries (about 900 px), which fits the 1016 px column; anything beyond is cut by the
   grouplist. Cost: a crowded line for users with every source; a skin setting can pick
   sources later.
3. **Ends at in the tags row, pink.** It sits right after the runtime ("136 MIN  ENDS AT
   23:42"), so it reads with it. Pink (accent2) because it is state: it moves with the clock,
   the resume point and the player. Cost: a third colour in the row (grey facts, pink state,
   cyan tech); if that is too busy it can go grey.
4. **Ratings only for the item they belong to.** On the episode head the TMDb Helper values
   show only while the selected episode (list 5100) is the dialog's own episode (same season
   and episode), since TMDb Helper watches the dialog's item, not the list. Other episodes
   fall back to Kodi's ratings. TMDb Helper values also hide while TMDb Helper updates
   (`IsUpdating`, `IsUpdatingRatings` for the online ones), so a new page never shows the
   previous title's ratings. Cost: on a slow connection the line comes a moment later.
5. **Same block on home and on the info page.** The home movie hero gets ends at and the
   full ratings line too, since it is the same include. Cost: the hero line gets longer; it
   has the full width there.
6. **The player OSD stays as it is.** It already shows resolution, HDR, audio and
   `Player.FinishTime`; ratings in the OSD (AF3 uses `TMDbHelper.Player.*`) are left for
   later, the OSD has no free line for them.
