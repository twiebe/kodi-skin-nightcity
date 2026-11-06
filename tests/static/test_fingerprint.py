"""Confuse must behave like Nightcity, window by window. The fingerprint of a window lists what a
control does (actions, conditions, focus), not how it looks; the two skins may differ only where
skins/confuse/DEVIATIONS.md says so."""
import shutil
import xml.etree.ElementTree as ET

import pytest

from conftest import ROOT
from fingerprint import diff_fingerprints, fingerprint, read_deviations

DEVIATIONS = ROOT / 'skins' / 'confuse' / 'DEVIATIONS.md'
OVERLAY_OK = {'Font.xml', 'Includes_Look.xml'}


def copy_tree(confuse_root, tmp_path):
    dest = tmp_path / 'copy'
    shutil.copytree(confuse_root, dest)
    return dest


def mutate(layout, pick, change):
    """Apply `change` to the first element `pick` finds in any file of `layout`; return the file."""
    for path in sorted(layout.glob('*.xml')):
        tree = ET.parse(path)
        for el in tree.getroot().iter():
            if pick(el):
                change(el)
                tree.write(path, encoding='utf-8')
                return path
    raise AssertionError('nothing to mutate')


def has_id_below(el):
    return any(c.get('id') for c in el.iter('control') if c is not el)


def test_confuse_behaves_like_nightcity(confuse_root):
    assert diff_fingerprints(ROOT / '1080i', confuse_root / '1080i') == read_deviations(DEVIATIONS)


def test_no_stale_deviation(tmp_path, confuse_root):
    stale = tmp_path / 'DEVIATIONS.md'
    stale.write_text('## Home.xml\n\n- `onclick=Nothing()`: made up\n', encoding='utf-8')
    assert read_deviations(stale) == {'Home.xml': ['onclick=Nothing()']}
    assert diff_fingerprints(ROOT / '1080i', confuse_root / '1080i') != read_deviations(stale)


def test_changed_onclick_is_noticed(tmp_path, confuse_root):
    layout = copy_tree(confuse_root, tmp_path) / '1080i'
    path = mutate(layout, lambda e: e.tag == 'onclick' and (e.text or '').strip(), lambda e: setattr(e, 'text', 'Dummy()'))
    diff = diff_fingerprints(ROOT / '1080i', layout)
    assert diff, path
    assert any('Dummy()' in line for lines in diff.values() for line in lines)
    assert all(name.endswith('.xml') for name in diff)


def test_changed_visible_on_a_parent_group_is_noticed(tmp_path, confuse_root):
    layout = copy_tree(confuse_root, tmp_path) / '1080i'
    mutate(layout, lambda e: e.tag == 'control' and e.get('type') == 'group' and e.find('visible') is not None and has_id_below(e),
           lambda e: setattr(e.find('visible'), 'text', 'Window.IsActive(Dummy)'))
    diff = diff_fingerprints(ROOT / '1080i', layout)
    assert any('Window.IsActive(Dummy)' in line for lines in diff.values() for line in lines)


def test_changed_defaultcontrol_is_noticed(tmp_path, confuse_root):
    layout = copy_tree(confuse_root, tmp_path) / '1080i'
    path = mutate(layout, lambda e: e.tag == 'defaultcontrol', lambda e: setattr(e, 'text', '98765'))
    diff = diff_fingerprints(ROOT / '1080i', layout)
    assert any('98765' in line for line in diff.get(path.name, []))


def test_changed_decoration_image_is_ignored(tmp_path, confuse_root):
    layout = copy_tree(confuse_root, tmp_path) / '1080i'
    mutate(layout, lambda e: e.tag == 'control' and e.get('type') == 'image' and not e.get('id') and e.find('texture') is not None,
           lambda e: setattr(e.find('texture'), 'text', 'other.png'))
    assert diff_fingerprints(ROOT / '1080i', layout) == read_deviations(DEVIATIONS)


@pytest.mark.parametrize('base', [ROOT, 'confuse'])
def test_look_includes_hold_no_behaviour(base, confuse_root):
    layout = (ROOT if base == ROOT else confuse_root) / '1080i'
    for el in ET.parse(layout / 'Includes_Look.xml').getroot().iter():
        assert el.get('id') is None, el.tag
        assert not el.tag.startswith('on') and el.tag != 'altclick', el.tag
        if el.tag == 'visible':
            assert (el.text or '').strip().startswith('$PARAM['), el.text


def test_whole_windows_in_the_overlay_are_listed(confuse_root):
    listed = set(read_deviations(DEVIATIONS))
    files = {p.name for p in (ROOT / 'skins' / 'confuse' / '1080i').glob('*.xml')}
    assert files - OVERLAY_OK <= listed
