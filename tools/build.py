#!/usr/bin/env python3
"""Build the installable skin zip: python tools/build.py [OUT_DIR] (default /dist)."""
import pathlib
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


def build(out_dir=pathlib.Path('/dist')):
    addon = ET.parse(ROOT / 'addon.xml').getroot()
    addon_id, version = addon.get('id'), addon.get('version')
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / '{}-{}.zip'.format(addon_id, version)
    skip = unused_fonts()
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(ROOT.rglob('*')):
            rel = path.relative_to(ROOT)
            if path.is_file() and not EXCLUDE & set(rel.parts) and not (rel.parts[0] == 'fonts' and path.name in skip):
                zf.write(path, '{}/{}'.format(addon_id, rel.as_posix()))
    return target


if __name__ == '__main__':
    print(build(*sys.argv[1:2]))
