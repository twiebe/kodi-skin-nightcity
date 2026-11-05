# E2E speed and stability notes (branch e2e-speed)

Working notes of the overnight task from 2026-11-05: a full e2e run in at most 5 minutes at the
default worker count (8 on this 16 core, 30 GB box), stable under load and varying worker counts,
named pools with a run guard, clean state after a stopped run, and the red and flaky tests cleared.
Nothing here is merged; the user decides after reading the report.

## Where things are

- Skin worktree: `/workspaces/kodi-dev/.e2e-worktrees/skin` (branch `e2e-speed`). New top-level
  directories under `/workspaces` do not survive a box restart; this one lives inside the
  kodi-dev checkout (excluded via `.git/info/exclude`) and does.
- kodi-dev worktree: `/workspaces/kodi-dev/.e2e-worktrees/kodi-dev` (branch `pool-name`):
  named pools (`KDEV_POOL=NAME`) and the run lock. Its `.env` and `compose.override.yaml` are
  copies of the main checkout's (git-ignored, copy them again after a restart).
- The pool used here: `KDEV_POOL=e2e`, 8 workers `e2e-0 .. e2e-7`, template copied from
  `/workspaces/kodi-dev/data` (3 movies incl. The Matrix, 2 shows, no genres).
- Run logs and junit files of this session: the scratchpad under
  `/tmp/claude-1000/-workspaces-kodi-repo/.../scratchpad/runs` (lost on restart; numbers below).

## Commands

```
# bring the pool up (once; again after a restart or to change the mounted skin)
cd /workspaces/kodi-dev/.e2e-worktrees/kodi-dev
KDEV_POOL=e2e ./kdev pool up 8 --skin /workspaces/kodi-dev/.e2e-worktrees/skin --from /workspaces/kodi-dev/data

# a full run from the skin worktree
cd /workspaces/kodi-dev/.e2e-worktrees/skin
KDEV_POOL=e2e KODI_DEV=/workspaces/kodi-dev/.e2e-worktrees/kodi-dev \
  /workspaces/kodi-skin-nightcity/.venv/bin/python -m pytest tests/e2e -m e2e -n auto --dist loadfile -q -p no:cacheprovider -rfEs

# fewer workers: -n 4 (the pool keeps 8 Kodis, only the first 4 are used)
# stop the pool before leaving
KDEV_POOL=e2e ./kdev pool down
```

## Measurements

All with 8 workers and `--dist loadfile` unless said otherwise. "sum" is the sum of all test
durations (setup + call + teardown) from the junit file, the wall time floor is sum / 8 plus
the session start (Kodi restart per worker).

| Run | Commit / change | Wall | Result | Notes |
|---|---|---|---|---|
| base1, base2 (predecessor) | 432bcf3, main | 441 s, 456 s | 11 failed, 278 passed, 5 skipped | sum 2195 s; test_tmdb_chain.py alone 441 s on one worker |
| r1..r6 (predecessor) | sender, scheduler, data fixtures, 640x360, delay 0.1 | 312, 300, 284, 263, 252, 246 s | 1 to 7 failed | the predecessor's worktree was lost; its runs are not reproducible, the changes were recovered from its transcript |

| r1 | f018995 + c5e36ef collected late (old back_held) | 280.6 s | 4 failed, 312 passed, 4 skipped, 1 error | sum 2043 s; load 44 at the end: all 8 Kodis in playback tests, each 1100 % CPU |
| r2 | + 3c8900e, LP_NUM_THREADS=2 (kodi-dev 9cf3d98) | 260.3 s | 1 failed, 315 passed, 4 skipped, 1 error | sum 1871 s; peak load 13.5, mean idle 49 %; back_held passes; the one failure is the Back-right-after-open race below |
| r3 | + 73c0013 (manager wait) | 281.0 s | 1 failed, 315 passed, 4 skipped | sum 1891 s; peak load 11.7; 0 Kodi crashes; test_back_in_the_chain_returns_to_the_crew_tab: Back on the person page had no effect, manager never saw the page close (cause open) |
| r4 | same | 244.4 s | 1 failed, 315 passed, 4 skipped, 1 error | sum 1867 s; peak load 13.2; 0 crashes; test_up_right_after_an_osd_chain_stays_on_the_tabs (HasFocus 6521 within 5 s), test_script teardown: builtin marker not seen in 10 s (marker timeout now 30 s, 3dc75c3) |

## Findings

- Baseline failures: 9 from missing data (the pool template has 3 movies, 2 shows, 0 genres,
  the tests expected an old bulk library). Fixed with temporary fixtures per test (genres via
  SetMovieDetails and a service recount, 30 movie rows via SQL in the worker's own MyVideos db,
  removed afterwards and before, in case a stopped run left them), since test_library_bar.py
  asserts exactly 3 movies.
- test_back_held_in_a_chain_from_the_player_returns_to_its_controls: not a skin bug. Commit
  8c95406 (2026-11-02) moved Back held from an OSD chain to the player's controls (first button,
  play or resume) on purpose, but left the e2e test on the old expectation (cast row) and
  DESIGN.md's wording. Fixed the test and the wording (c5e36ef).
- Thread limit: the box had cgroup pids.max 2048 earlier (8 idle workers use about 1600
  threads); the user raised it to max. ffmpeg still runs with few threads and writes the clip
  atomically, so a run killed while a worker builds its clip leaves no 0-byte file behind.
- Idle Kodis cost 4 to 6 % CPU each at 1280x720 with software GL; the saturation during a run
  (load 20+) comes from test activity, not from idle instances.
- The CPU hog: nothing throttles Kodi's render loop on Xvfb (no vblank, GLX vsync does
  nothing, Kodi 21's videoplayer.limitguiupdate is commented out in the source), so a Kodi
  playing video renders at 360 fps, and llvmpipe rasterizes on one thread per core: 1096 % CPU
  for one Kodi playing a 640x360 clip. Measured on e2e-7 (CPU, fps, playback speed):
  LP_NUM_THREADS=16 (default) 1096 % 360 fps 1.012x; 4: 348 % 168 fps 0.993x; 2: 193 % 96 fps
  0.994x; 1: 101 % 47 fps 0.994x. kodi-dev now sets LP_NUM_THREADS=2 (KODI_LP_THREADS overrides).
  Effect on a full run: peak load 44 to 13.5, wall 280 to 260 s, and the load-sensitive chain
  tests stopped failing.
- The "Back right after a page opens" tests (test_back_right_after..., test_escape_right_after...)
  are timing tests by intent. Two races, both now handled in the helper `_film_in_its_first_second`:
  (1) the key must be done while the guard (1 s from the page's onload) is still up, so the
  helper checks the guard after the key and tries again otherwise; (2) the skin's guard is a
  heuristic: TMDb Helper's window manager polls every 0.5 s for the page it opened and
  publishes nothing once it has seen it, so a held Back done after the second can still close
  the page before the manager looked, and the chain then hangs 30 s on an empty backdrop
  (reproduced 1 in 24 with 16 busy processes next to 6 Kodis; the manager logs
  "direct.open() DONE!" to kodi.log, which the helper now waits for before the key). This is a
  skin limitation under heavy load, not reachable on a normal box; the clean fix is in the
  TMDb Helper fork: publish a property once the page was seen, and let the guard wait on it.

## Tried and dropped

(filled in as it happens)

## Open points and next steps

(filled in as it happens)
