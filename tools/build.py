#!/usr/bin/env python3
"""Build the installable skin zip: python tools/build.py [--pre] [--skin NAME] [OUT_DIR] (default /dist).

--skin NAME builds the overlay skins/NAME on top of this tree (see assemble). Without it the zip
is Nightcity, straight from the root. --skin NAME --assemble [DIR] writes only the assembled
folder (default _build/NAME), the one kodi-dev mounts, no zip.

--pre builds a prerelease of the next version for testing ahead of a release: 0.4.79~beta1,
~beta2, ... counted from the zips already in OUT_DIR. Kodi orders it below 0.4.79. Only the zip
carries that version, addon.xml in the checkout keeps the release version."""
import fnmatch
import pathlib
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXCLUDE = {'.git', '.gitignore', '.superpowers', 'CLAUDE.md', 'Makefile', 'docs', 'tests', 'tools', 'requirements-dev.txt', 'pytest.ini',
           '__pycache__', '.venv', '.pytest_cache', 'skins', '_build'}


def unused_fonts(root=ROOT):
    """Font files Font.xml does not load: the sources make_fonts.py builds from. Licenses stay."""
    used = {f.findtext('filename') for f in ET.parse(root / '1080i' / 'Font.xml').getroot().iter('font')}
    return {p.name for p in (root / 'fonts').iterdir() if p.suffix in ('.ttf', '.otf') and p.name not in used}


def prerelease(addon_id, version, out_dir):
    major, minor, patch = version.split('.')
    nxt = '{}.{}.{}'.format(major, minor, int(patch) + 1)
    pattern = re.compile(re.escape('{}-{}~beta'.format(addon_id, nxt)) + r'(\d+)\.zip$')
    taken = [int(m.group(1)) for m in (pattern.match(p.name) for p in out_dir.iterdir()) if m]
    return '{}~beta{}'.format(nxt, max(taken, default=0) + 1)


def _copy_tree(src, dest):
    for path in sorted(src.rglob('*')):
        rel = path.relative_to(src)
        if path.is_file() and not EXCLUDE & set(rel.parts):
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest / rel)


def assemble(skin, dest):
    """Lay skins/<skin> over the root tree into dest and return dest. A file of the overlay replaces
    the root file of the same path, remove.txt lists globs to drop, fonts Font.xml does not load stay
    out, and [UPPERCASE] markup goes from the windows (Confuse shows titles as written: a build rule,
    so the shared files keep it). dest stays the same folder, only its content is replaced: kodi-dev
    mounts it."""
    overlay = ROOT / 'skins' / skin
    dest = pathlib.Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for child in dest.iterdir():
        shutil.rmtree(child) if child.is_dir() and not child.is_symlink() else child.unlink()
    _copy_tree(ROOT, dest)
    _copy_tree(overlay, dest)
    (dest / 'remove.txt').unlink(missing_ok=True)
    remove = overlay / 'remove.txt'
    patterns = [l.strip() for l in remove.read_text(encoding='utf-8').splitlines() if l.strip()] if remove.exists() else []
    for path in sorted(dest.rglob('*')):
        if path.is_file() and any(fnmatch.fnmatch(path.relative_to(dest).as_posix(), p) for p in patterns):
            path.unlink()
    for name in unused_fonts(dest):
        (dest / 'fonts' / name).unlink()
    for path in (dest / '1080i').glob('*.xml'):
        text = path.read_text(encoding='utf-8')
        if '[UPPERCASE]' in text or '[/UPPERCASE]' in text:
            path.write_text(text.replace('[UPPERCASE]', '').replace('[/UPPERCASE]', ''), encoding='utf-8')
    return dest


def build(out_dir=pathlib.Path('/dist'), pre=False, skin=None):
    if skin:
        with tempfile.TemporaryDirectory() as tmp:
            return _zip(assemble(skin, pathlib.Path(tmp) / 'skin'), out_dir, pre, assembled=True)
    return _zip(ROOT, out_dir, pre)


def _zip(src, out_dir, pre, assembled=False):
    addon = ET.parse(src / 'addon.xml').getroot()
    addon_id, version = addon.get('id'), addon.get('version')
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    release = version
    if pre:
        version = prerelease(addon_id, version, out_dir)
    target = out_dir / '{}-{}.zip'.format(addon_id, version)
    skip = set() if assembled else unused_fonts()
    out_dir = out_dir.resolve()
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(src.rglob('*')):
            rel = path.relative_to(src)
            if out_dir in path.resolve().parents:
                continue  # an output folder inside the skin: the zip would pack itself
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
    only_folder = '--assemble' in args
    args = [a for a in args if a not in ('--pre', '--assemble')]
    skin = None
    if '--skin' in args:
        at = args.index('--skin')
        skin = args[at + 1]
        del args[at:at + 2]
    if only_folder:
        print(assemble(skin, args[0] if args else ROOT / '_build' / skin))
    else:
        print(build(*args[:1], pre=pre, skin=skin))
