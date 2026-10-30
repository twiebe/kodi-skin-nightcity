# Nightcity design rules

Rules every view follows. Tests in `tests/static` hold them where they can be checked.

## Navigation

The remote moves through levels, not through confirmations.

- **Up and Left go one level up, Down and Right one level down.** Up on the top row of a page
  leaves it (Back). Left on a settings page goes back to its categories, Right enters them.
- **No dead ends.** Every control a remote can reach has a way back to where the window started.
- **Back returns where you left.** Back (or Up at the top) from a page opened by OK lands on the
  element that opened it: the same item, the same tab. A TMDb chain reopens the page before as a
  new page, so the click keeps the way back (`info_leave`, `info_back`, `osd_back` in
  `scripts/nightcity.py`); a chain from the player's cast row ends on that row, on that person.

### Selectors are skipped from above

A selector is a row that chooses what the content below it shows: season tabs above the
episodes, cast and crew above the credits, movies and shows on a person page, the categories
of a page.

- Down from the element above a selector lands on the content, past the selector.
- Up from the content lands on the selector, up again on the element above.
- The selector is never the place the focus falls into by itself.

Example: on an episode, Play, Down: the episodes. Up: the season tabs. Up: Play.

### Focus applies, OK goes

- **Moving onto an element that changes the current view applies it at once.** A tab, a
  season, cast or crew, movies or shows: the cursor on it is the choice, no OK needed.
- **An element that leaves the view needs OK.** Opening an info page, playing, opening the
  episodes of a show from the spotlight, opening a dialog or another window.

Rule of thumb: if the screen around the focus stays and only its content changes, focus applies
it. If the screen changes, OK does.

The quick menu on Home follows it too: the cursor on the icon next to the clock shows the menu,
Down or OK go into it, Up from its top comes out onto the icon with the menu still shown, Left
or Right off the icon hide it. Back, in the menu or on the icon, closes it: the focus goes back
to where it came onto the icon from (a settings row, a row of a page, the top menu), or to the
shown page's own entry. The keys that open the quick menu (Home held, the S key, Kodi's power
menu) go to the icon on every page of Home, which shows the menu; the same key again closes it
like Back. Only over other windows (an info page, the player)
the quick menu is a dialog.

A choice that loads a TMDb list waits while another TMDb list loads (`TmdbBusy`,
`nc_credits_tab`): two plugin lists at once crash Kodi. The cursor still decides, the list
follows a moment later.

Not applied on focus, on purpose:

- **Toggles and cycles** (sort field and direction in the library, "more" in the OSD): on focus
  they would flip on every pass.
- **Recent search terms**: each one runs a new search and moves to the front of the list, so
  the terms would reorder under the cursor. OK runs it.

### Exceptions, for now

Kodi's own windows keep Kodi's way until it is settled how they should behave: the settings
(Settings, setting categories, skin settings, add-on settings), the file manager and the add-on
browser.

## What the colours say

| Colour | Role | Examples |
|---|---|---|
| White (`text`, graded `text_dim`/`text_mute`) | content, what you read | titles, plot, values, clock, tags, rating stars and labels |
| Cyan (`accent`) | the cursor, where you are | focus fill and line, latent cursor (next episode title), Play pill, mouse pointer |
| Dimmed blue (`state`/`state_text`) | state and hints, quiet | active tab, selected value, counters 3/25, separators, progress background, scroll chevron |
| Pink (`accent2`) | order and identity: names or numbers something, never changes with input | the kicker line over titles, dialog headings, the numbering in the settings (rail numbers) and on the system page (tile numbers) |
| Yellow (`accent3`/`warn`) | warnings only | notifications that warn about something |

- Pink never shows state or cursor; that is the dimmed blue. At most one pink element per area.
- Yellow only for warnings: the heading of a warning or error notification. `accent3` is not
  used. The skin tells such a notification by Kodi's icon for it (`media/DefaultIconWarning.png`,
  `DefaultIconError.png`, drawn by `tools/make_textures.py`); every other one has a pink heading.
- The keys in a hint line (OK open, Back close) are hints: dimmed blue.
- `state` is border_dim made opaque over the page, so a thin line looks the same on any
  background; text and small marks take `state_text`, the same hue just light enough to read
  (4.5:1).
- Cyan also marks a few things that are where you go or act: the primary button (Play), the
  search field's outline, the quick menu's icon while the focus is in that menu (Up and Back
  lead there), slider nibs, the fill of a progress bar and the playing time.
- The static test `tests/static/test_colors.py` holds the skin to this table.
- **A progress line says where you are** in something that plays or was watched: under an
  episode or a card. It stays on its item when the cursor moves away. The music queue has none:
  Kodi redraws a list item only while the cursor is on it, so a live line elsewhere stood still.
  Its playing track has a dark blue mark instead, wherever the cursor is: the bar of a current
  value before a track's number, a line under a card's title.
