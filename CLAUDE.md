# Working on Nightcity

Rules for anyone (human or agent) changing this skin. The look and the navigation rules are in
DESIGN.md (colour guide, tabs switch on focus, ...); the development setup is in README.md.

## Tests

- Run pytest as `.venv/bin/python -m pytest`, not `.venv/bin/pytest`.
- Unit and static, after every change:
  `.venv/bin/python -m pytest tests/unit tests/static -q -p no:cacheprovider`
- Test first: write the failing test, watch it fail, then change the skin.

### When to run the e2e tests

The e2e suite checks behaviour (navigation, focus, what a key does), not looks. A full run takes
about 12 minutes on the kodi-dev pool.

- **Looks only** (colours, positions, sizes, textures, fonts, strings): unit/static and a
  screenshot. No e2e, also not before a release.
- **Behaviour** (navigation, focus, `onclick`/`onfocus`/`onup`..., visible and enable
  conditions, windows and dialogs, the Python service): per change only the e2e tests that cover
  it (single tests or one file). Before a release one full run, if behaviour changed since the
  last full run.
- **Unsure:** a diff that touches a condition or an action counts as behaviour.

Full run (the pool mounts the main checkout, do not edit it while the run is on):

```
KDEV_POOL=1 .venv/bin/python -m pytest tests/e2e -m e2e -n auto --dist loadfile -q -p no:cacheprovider -rfEs
```

A test that fails in the full run but passes when its file is run again on its own is a flake:
say so in the report, do not hide it.

## Releases

Every zip that leaves the machine has its own version:

1. Bump the version in `tests/static/test_addon.py` (version and zip name) and watch it fail.
2. Bump `addon.xml` and put a news entry at the front of `<news>`: plain English sentences about
   what changed for the user, entries separated by `[CR]`. The release tag lists them.
3. Unit/static, then `.venv/bin/python tools/build.py <dir>`.
4. Commit as "Release <version>". Push only when asked.

Before the full e2e run of a release, build a prerelease for the user to try on their own Kodi
while the run is on: `.venv/bin/python tools/build.py --pre /dist`. It needs no bump or commit:
the zip carries the next version with a counter, `skin.nightcity-0.4.79~beta1.zip`, `~beta2`
on the next build, which Kodi orders below the release. Build a new one after every change the
user should see before the release.

## Writing

- The skin is English only; strings go to `language/resource.language.en_gb/strings.po`.
- No em dashes or en dashes anywhere (strings, news, docs, comments, commit messages); use a
  plain hyphen.
- Match the surrounding XML: includes, naming, comment density.
