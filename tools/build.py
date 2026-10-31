#!/usr/bin/env python3
"""Build the installable skin zip: python tools/build.py [--pre] [OUT_DIR] (default /dist).

--pre builds a prerelease of the next version for testing ahead of a release: 0.4.79~beta1,
~beta2, ... counted from the zips already in OUT_DIR. Kodi orders it below 0.4.79. Only the zip
carries that version, addon.xml in the checkout keeps the release version."""
import pathlib
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXCLUDE = {'.git', '.gitignore', '.superpowers', 'CLAUDE.md', 'docs', 'tests', 'tools', 'requirements-dev.txt', 'pytest.ini',
           '__pycache__', '.venv', '.pytest_cache'}


def unused_fonts():
    """Font files Font.xml does not load: the sources make_fonts.py builds from. Licenses stay."""
    used = {f.findtext('filename') for f in ET.parse(ROOT / '1080i' / 'Font.xml').getroot().iter('font')}
    return {p.name for p in (ROOT / 'fonts').iterdir() if p.suffix in ('.ttf', '.otf') and p.name not in used}


def prerelease(addon_id, version, out_dir):
    major, minor, patch = version.split('.')
    nxt = '{}.{}.{}'.format(major, minor, int(patch) + 1)
    pattern = re.compile(re.escape('{}-{}~beta'.format(addon_id, nxt)) + r'(\d+)\.zip$')
    taken = [int(m.group(1)) for m in (pattern.match(p.name) for p in out_dir.iterdir()) if m]
    return '{}~beta{}'.format(nxt, max(taken, default=0) + 1)


def build(out_dir=pathlib.Path('/dist'), pre=False):
    addon = ET.parse(ROOT / 'addon.xml').getroot()
    addon_id, version = addon.get('id'), addon.get('version')
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    release = version
    if pre:
        version = prerelease(addon_id, version, out_dir)
    target = out_dir / '{}-{}.zip'.format(addon_id, version)
    skip = unused_fonts()
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(ROOT.rglob('*')):
            rel = path.relative_to(ROOT)
            if path.is_file() and not EXCLUDE & set(rel.parts) and not (rel.parts[0] == 'fonts' and path.name in skip):
                name = '{}/{}'.format(addon_id, rel.as_posix())
                if pre and rel.as_posix() == 'addon.xml':
                    text = path.read_text(encoding='utf-8')
                    zf.writestr(name, text.replace('version="{}"'.format(release), 'version="{}"'.format(version), 1))
                else:
                    zf.write(path, name)
    return target


if __name__ == '__main__':
    args = sys.argv[1:]
    pre = '--pre' in args
    args = [a for a in args if a != '--pre']
    print(build(*args[:1], pre=pre))
