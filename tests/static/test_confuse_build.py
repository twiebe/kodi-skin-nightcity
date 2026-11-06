import zipfile

import pytest

from conftest import ROOT, parse
from build import MARKER, assemble, build


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


def test_every_root_colour_token_exists(confuse_root):
    assert set(colour_names(ROOT)) <= set(colour_names(confuse_root))


def test_glut_palette_values(confuse_root):
    colours = {c.get('name'): c.text for c in parse(confuse_root / 'colors' / 'defaults.xml').iter('color')}
    wanted = {'bg': 'FF0F0E0D', 'surface': 'FF1E1B18', 'text': 'FFF7F3EC', 'text_dim': 'FFD3CDC3', 'text_mute': 'FFABA498',
              'accent': 'FFEFAA47', 'focus': 'FFEFAA47', 'focus_text': 'FF1A1208', 'warn': 'FFE8C468', 'fanart': '94FFFFFF',
              'text_chip': 'FFDED8CE', 'focus_text_dim': 'FF4A3514', 'disabled': 'FF9A9388'}
    assert {k: colours[k] for k in wanted} == wanted


def test_assemble_refuses_the_repo_and_its_parents(tmp_path):
    for bad in (ROOT, ROOT.parent, ROOT / 'tools' / '..'):
        with pytest.raises(ValueError):
            assemble('confuse', bad)
    assert (ROOT / 'tools' / 'build.py').exists()


def test_assemble_refuses_a_foreign_non_empty_folder(tmp_path):
    (tmp_path / 'keep.txt').write_text('x')
    with pytest.raises(ValueError):
        assemble('confuse', tmp_path)
    assert (tmp_path / 'keep.txt').exists()


def test_marker_stays_out_of_the_zip(tmp_path):
    assert any(n for n in zipfile.ZipFile(build(tmp_path / 'z', skin='confuse')).namelist())
    assert not [n for n in zipfile.ZipFile(next((tmp_path / 'z').glob('*.zip'))).namelist() if MARKER in n]


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


def _small_repo(tmp_path, monkeypatch):
    """A tree of its own, so that a test can change the overlay."""
    repo = tmp_path / 'repo'
    for name, text in (('addon.xml', '<addon id="skin.nightcity"/>'), ('shared.txt', 'shared'),
                       ('1080i/Font.xml', '<fonts><font><filename>a.ttf</filename></font></fonts>'),
                       ('fonts/a.ttf', 'font'), ('skins/small/addon.xml', '<addon id="skin.small"/>'),
                       ('skins/small/own.txt', 'own')):
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)
    monkeypatch.setattr('build.ROOT', repo)
    return repo, tmp_path / 'out'


def _stamps(folder):
    """mtime and ctime of each file: copy2 keeps the mtime of its source, only the ctime shows that
    a plain copy was written again."""
    return {p.relative_to(folder).as_posix(): (p.stat().st_mtime_ns, p.stat().st_ctime_ns)
            for p in folder.rglob('*') if p.is_file()}


def test_assemble_without_changes_touches_nothing(tmp_path):
    dest = assemble('confuse', tmp_path / 'out')
    before = _stamps(dest)
    assemble('confuse', dest)
    assert _stamps(dest) == before


def test_a_changed_overlay_file_replaces_only_that_file(tmp_path, monkeypatch):
    repo, out = _small_repo(tmp_path, monkeypatch)
    assemble('small', out)
    before = _stamps(out)
    (repo / 'skins/small/own.txt').write_text('changed')
    assemble('small', out)
    assert (out / 'own.txt').read_text() == 'changed'
    after = _stamps(out)
    assert after.pop('own.txt') != before.pop('own.txt')
    assert after == before


def test_a_stale_file_goes_and_the_others_stay_untouched(tmp_path, monkeypatch):
    repo, out = _small_repo(tmp_path, monkeypatch)
    assemble('small', out)
    before = _stamps(out)
    (repo / 'skins/small/own.txt').unlink()
    (out / 'stale' / 'deep').mkdir(parents=True)
    (out / 'stale' / 'deep' / 'file.txt').write_text('stale')
    assemble('small', out)
    assert not (out / 'own.txt').exists()
    assert not (out / 'stale').exists()
    before.pop('own.txt')
    assert _stamps(out) == before
    assert (out / MARKER).exists()


def test_stripped_labels_never_become_bare_numbers(confuse_root):
    """A label that is only digits is a string id to Kodi (GUIControlFactory.cpp:662): the number pad's
    1 would show the text of string 1. Nightcity's [UPPERCASE]1[/UPPERCASE] is not numeric, the
    stripped one is. So a number that went into a [UPPERCASE] label, as text or as the value of the
    param that fills it, is written $NUMBER[n] in the assembled tree."""
    import re
    sources = ''.join(p.read_text(encoding='utf-8') for p in sorted((ROOT / '1080i').glob('*.xml')))
    wrapped = set(re.findall(r'\[UPPERCASE\]\$PARAM\[(\w+)\]\[/UPPERCASE\]', sources))
    assert 'label' in wrapped
    found = 0
    for path in sorted((confuse_root / '1080i').glob('*.xml')):
        for el in parse(path).iter():
            if el.tag == 'param' and el.get('name') in wrapped and el.get('value', '').isdigit():
                raise AssertionError((path.name, el.get('name'), el.get('value')))
            if el.tag in ('label', 'label2', 'altlabel') and (el.text or '').strip().isdigit():
                raise AssertionError((path.name, el.tag, el.text))
            found += el.tag == 'param' and (el.get('value') or '').startswith('$NUMBER[')
    assert found >= 10  # the pad: 0 to 9
