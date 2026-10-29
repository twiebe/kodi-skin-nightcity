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
Down or OK go into it, Up from its top and Back come out onto the icon with the menu still
shown, Left or Right off the icon hide it. The keys that open the quick menu (Home held, the S
key, Kodi's power menu) show the same menu on every page of Home, on power off; the same key
again takes the focus back to where it was. Only over other windows (an info page, the player)
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
