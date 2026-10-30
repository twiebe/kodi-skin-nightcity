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
   need a settings page Nightcity does not have. With every source (an MDbList key gives all
   eight) the line needs about 1400 px. On Home it has them; on the info page it stops before
   the details or cast column (1000 px for a movie, 1300 for an episode), so a movie shows
   IMDb to Trakt and Letterboxd and MDbList stay out (a grouplist leaves out what does not fit
   whole). Cost: the last sources missing on the info page for users with every key; shorter
   names, fewer sources or a skin setting to pick them would fix it.
3. **Ends at in the tags row, like the runtime.** It sits right after the runtime ("136 MIN
   ENDS AT 23:42"), so it reads with it, in the same grey tag. It was pink at first (state: it
   moves with the clock, the resume point and the player); the user chose the runtime's look,
   pink stays for titles. Cost: it does not stand out from the facts around it.
4. **Ratings only for the item they belong to.** On the episode head the TMDb Helper values
   show only while the selected episode (list 5100) is the dialog's own episode (same season
   and episode), since TMDb Helper watches the dialog's item, not the list. Other episodes
   fall back to Kodi's ratings. On Home the hero takes TMDb Helper's values only while
   `TMDbHelper.WidgetContainer` names its spotlight (9000 movies, 9001 shows): a row clears it,
   and TMDb Helper then describes the focused card, not the hero. The online ratings hide
   while `TMDbHelper.IsUpdatingRatings` is set, so a new page does not show the previous
   title's IMDb or Rotten Tomatoes values while the new ones load. The TMDb value is not
   gated on `TMDbHelper.IsUpdating`: that flag also blinks while the info page loads its
   lists, the line would flicker. Cost: for the fraction of a second before TMDb Helper sees a
   new item, the TMDb value can still be the previous title's (as in AF3); on Home the
   hero shows Kodi's rating while a row has the focus.
5. **Same block on home and on the info page.** The home movie hero gets ends at and the
   full ratings line too, since it is the same include. Cost: the hero line gets longer; it
   has the full width there.
6. **The player OSD stays as it is.** It already shows resolution, HDR, audio and
   `Player.FinishTime`; ratings in the OSD (AF3 uses `TMDbHelper.Player.*`) are left for
   later, the OSD has no free line for them.

## Ratings source

The spotlight used to look restless: rotating without focus, the hero showed the library
rating (Jellyfin for Kodi syncs the community rating as Kodi's "default" rating, no source
name); on focus TMDb Helper's ratings joined; when focus went to a row they vanished again,
because the row cleared `TMDbHelper.WidgetContainer` and TMDb Helper let go of the hero. On an
episode's info page only the episode the page opened with got ratings.

### Settings: Skin settings > Ratings

A category of its own before Player (all eight sources no longer fit on the info page, and the
main menu category had no room):

- **Ratings only from TMDb Helper** (on by default; the skin bool `nc.ratings.library` stores
  off). "Show only the ratings TMDb Helper fetched for exactly this title. Off: the library's
  own rating (from Jellyfin) fills in while TMDb Helper has none." On, the ratings line never
  shows `ListItem.Rating`, `Rating(imdb)`, `Rating(themoviedb)` or `Rating(tmdb)`; with no
  TMDb Helper data it hides. On the info page and the heroes alike. Off is the behaviour
  before, with the fallbacks.
- **Load spotlight ratings without focus** (off by default; `nc.ratings.spotlight`). "Fetch
  the ratings of each spotlight title as it rotates, also without focus. Off saves online
  requests: the ratings load once the title has focus and then stay."
- **Sources**, one toggle each in the line's order: IMDb (with the Top 250 rank), TMDb, Rotten
  Tomatoes critics, Rotten Tomatoes audience, Metacritic, Trakt, Letterboxd, MDbList. IMDb and
  Rotten Tomatoes critics are on by default (`nc.ratings.hide.imdb`, `nc.ratings.hide.rt` store
  off), the others off (`nc.ratings.show.tmdb`, `.rtu`, `.mc`, `.trakt`, `.lb`, `.mdb`). A
  source shows only while its toggle is on and the item has a value; Kodi's own IMDb and TMDb
  ratings (with "only TMDb Helper" off) follow the IMDb and TMDb toggles. Each toggle says
  where TMDb Helper gets it: IMDb, Rotten Tomatoes and Metacritic need an OMDb or MDbList key,
  Letterboxd and MDbList an MDbList key, Trakt a connected Trakt account (fetched from Trakt,
  not MDbList), TMDb nothing. Metacritic is a weighted average of critic reviews, mostly for
  theatrical films and big series; MDbList is an average of the other sources.

### How the ratings get to the line

`scripts/nightcity.py` `hero_tick`, a thread of the skin service that looks every 0.25 s and
does nothing off Home and the episode info page:

- **TMDb Helper's hook.** TMDb Helper watches `Container(<id>).ListItem` of the container
  named in `TMDbHelper.WidgetContainer`, whether it has focus or not (`monitor/utils.py
  widget_id`). The skin sets `TMDbHelper.UseLocalWidgetContainer`: TMDb Helper then reads the
  property of the window on top (`poller.py is_on_localwidgetcontainer`), on Home
  `Window(Home)`'s as before, on the info page the page's own. Without it an info dialog
  always uses its own `ListItem` (`CV_USE_LISTITEM`), so the episode list could not be
  watched. `Skin.String(TMDbHelper.MonitorContainer)` was the other hook; it is global and
  makes TMDb Helper do nothing in windows without that control.
- **Home.** The service sets `Window(Home).Property(TMDbHelper.WidgetContainer)`, not the
  skin: the hero's spotlight (9000 on home and movies, 9001 on shows; `Control.IsVisible(9300)`
  / `(9301)`) while a hero button has focus (`ControlGroup(9050)` / `(9550)`), or always with
  "load without focus"; empty on rows, the main menu and off Home. The rows cleared the
  property before, so TMDb Helper never watched a row card on Home: pointing it at the hero
  takes nothing away.
- **Episode info page.** `DialogVideoInfo.xml` sets its own `TMDbHelper.WidgetContainer` to
  the episode list (5100) when it opens for an episode and clears it on any other page (the
  property stays on the window from one page to the next). TMDb Helper then fetches the
  focused episode; the head follows the same episode.
- **Keeping.** When TMDb Helper is done (`IsUpdating` and `IsUpdatingRatings` empty) and its
  item is the one on screen (`base_dbtype`, and `base_dbid` from
  `extras/tmdbhelper/baseitem.json`, or `base_label` for items without a library id), the
  service takes a snapshot of the rating properties. It keeps it once it stayed 0.8 s (after
  a title change TMDb Helper's properties hold the title before for about 0.3 s with both
  flags empty), for the session: heroes by `dbtype`/`dbid`, episodes by label, season and
  episode (a TMDb Helper chain lists episodes without a library id). The first snapshot of a
  title stays; only an empty one gets replaced by one with ratings.
- **Episodes.** For an episode TMDb Helper's TMDb, Rotten Tomatoes, Metacritic, Letterboxd and
  MDbList ratings are the show's (`get_all_ratings`: the show's ratings, then season and
  episode ratings from MDbList and Trakt on top). The service keeps IMDb and Trakt as they are
  and TMDb's vote of the episode itself (TMDb Helper's `Rating`, one decimal); the others stay
  out. So with the default toggles (IMDb, Rotten Tomatoes critics) an episode shows its IMDb
  rating when TMDb Helper has an MDbList key (or an OMDb key, which gives the show's IMDb
  rating), else nothing; with TMDb on, TMDb's vote of the episode.
- **Showing.** The service writes the kept ratings of the item on screen to
  `nc.kept.<container>.<Source>` plus the key (`.dbtype`/`.dbid`, or `.label`/`.season`/
  `.episode`); the `RatingsLine` reads that prefix and shows only while the key matches the
  item on screen. On a change the last key field is cleared first and set last, so the line
  never shows one title's ratings on another. The line fades in (200 ms) and goes at once.

### Design calls

1. **A service thread, not skin conditions.** Kodi cannot use an info label inside a property
   name, so per-title properties cannot be read straight from the skin; one published set per
   container plus a key match can. Cost: a poll on Home and the episode page (about a dozen
   info calls every 0.25 s, none elsewhere), and the line shows about 1 s after TMDb Helper
   has the ratings (0.8 s stability plus the poll).
2. **The service owns Home's `TMDbHelper.WidgetContainer`.** One place decides it (focus,
   page, setting) instead of onfocus actions on every row and button. Cost: up to 0.25 s
   later than an onfocus action before TMDb Helper starts on a focused hero.
3. **Keep first, no updates.** A title's line never changes once shown in a session. Cost:
   ratings TMDb Helper updates later in the session (a new IMDb value) show after a restart.
4. **Library ratings off by default.** Cost: titles TMDb Helper cannot match (no TMDb id)
   show no rating at all; the setting brings the library's back. With it off, the hero's
   library rating is replaced once by TMDb Helper's when they arrive (one swap per title).
5. **Session cache only.** Kept in the service's memory; a Kodi restart starts empty.
   TMDb Helper's own cache (7 days, ItemDetails.db) makes a refetch a database read.
6. **Episodes show only their own ratings.** Cost: an episode shows fewer ratings than before
   (no Rotten Tomatoes or Metacritic of the show); the show's ratings are on the show's page.
7. **TMDb off by default** (as asked: IMDb and Rotten Tomatoes critics only). Cost: without an
   OMDb or MDbList key a user sees no ratings at all until they switch TMDb on.
8. **A Ratings category instead of the main menu category.** Ten rows do not fit under the
   main menu rows and the look. Cost: one more category on the left.
