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

(this session's runs follow)

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

## Tried and dropped

(filled in as it happens)

## Open points and next steps

(filled in as it happens)
