import zipfile

from conftest import ROOT, parse
from build import assemble, build


def colour_names(root):
    return [c.get('name') for c in parse(root / 'colors' / 'defaults.xml').iter('color')]


def test_overlay_file_replaces_root_file(confuse_root):
    assert parse(confuse_root / 'addon.xml').get('id') == 'skin.confuse'
    assert parse(confuse_root / 'addon.xml').get('version') == '0.1.0'


def test_shared_files_come_from_root(confuse_root):
    assert (confuse_root / 'scripts/nightcity.py').read_bytes() == (ROOT / 'scripts/nightcity.py').read_bytes()


def test_remove_list_drops_themes(confuse_root):
    assert not (confuse_root / 'colors/catppuccin.xml').exists()
    assert not (confuse_root / 'colors/tokyonight.xml').exists()


def test_same_colour_tokens(confuse_root):
    assert colour_names(confuse_root) == colour_names(ROOT)


def test_confuse_zip(tmp_path):
    names = zipfile.ZipFile(build(tmp_path, skin='confuse')).namelist()
    assert 'skin.confuse/addon.xml' in names
    assert not any(n.startswith(('skin.nightcity/', 'skin.confuse/skins/', 'skin.confuse/_build/')) for n in names)


def test_nightcity_zip_has_no_confuse(tmp_path):
    names = zipfile.ZipFile(build(tmp_path)).namelist()
    assert not any(n.startswith(('skin.nightcity/skins/', 'skin.nightcity/_build/')) for n in names)


def test_prerelease_of_confuse(tmp_path):
    assert build(tmp_path, pre=True, skin='confuse').name == 'skin.confuse-0.1.1~beta1.zip'


def test_assemble_twice_keeps_the_folder_and_drops_stale_files(tmp_path):
    dest = assemble('confuse', tmp_path / 'c')
    inode = dest.stat().st_ino
    (dest / 'stale.txt').write_text('x')
    assemble('confuse', dest)
    assert dest.stat().st_ino == inode and not (dest / 'stale.txt').exists()


def test_assembled_markup_is_title_case(confuse_root):
    assert not any('[UPPERCASE]' in p.read_text() for p in (confuse_root / '1080i').glob('*.xml'))
