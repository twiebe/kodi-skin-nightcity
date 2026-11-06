"""Confuse must behave like Nightcity, window by window. The fingerprint of a window lists what a
control does (actions, conditions, focus), not how it looks; the two skins may differ only where
skins/confuse/DEVIATIONS.md says so."""
import shutil
import xml.etree.ElementTree as ET

import pytest

from conftest import ROOT
from navigation import FOCUSABLE, evaluate
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


def includes_used(layout, windows_only=True):
    """Include name -> windows that use it without a condition, and include name -> its conditions."""
    plain, gated = {}, {}
    for path in layout.glob('*.xml'):
        if windows_only and path.name.startswith('Includes'):
            continue
        for el in ET.parse(path).getroot().iter('include'):
            name = (el.get('content') or el.text or '').strip()
            if el.get('name') or not name or '$' in name:
                continue
            if el.get('condition'):
                gated.setdefault(name, []).append(el.get('condition'))
            else:
                plain.setdefault(name, set()).add(path.name)
    return plain, gated


def fingerprinted_onclicks(inc):
    """onclick tags of a definition that sit on a control with an id or a focusable type."""
    for control in inc.iter('control'):
        if (control.get('id') and '$' not in control.get('id')) or control.get('type') in FOCUSABLE:
            for el in control.findall('onclick'):
                if (el.text or '').strip() and '$' not in el.text:
                    yield el


def definition_with_onclick(layout, name):
    for path in sorted(layout.glob('Includes*.xml')):
        for inc in ET.parse(path).getroot().iter('include'):
            if inc.get('name') == name and next(fingerprinted_onclicks(inc), None) is not None:
                return path
    return None


def rewrite_onclick(layout, name, text):
    path = definition_with_onclick(layout, name)
    tree = ET.parse(path)
    for inc in tree.getroot().iter('include'):
        if inc.get('name') == name and next(fingerprinted_onclicks(inc), None) is not None:
            next(fingerprinted_onclicks(inc)).text = text
            break
    tree.write(path, encoding='utf-8')


def test_changed_onclick_is_noticed(tmp_path, confuse_root):
    layout = copy_tree(confuse_root, tmp_path) / '1080i'
    plain, gated = includes_used(layout)
    name = next(n for n in sorted(plain) if n not in gated and definition_with_onclick(layout, n))
    rewrite_onclick(layout, name, 'Dummy()')
    diff = diff_fingerprints(ROOT / '1080i', layout)
    assert plain[name] <= set(diff), set(diff)
    assert all(any('Dummy()' in line for line in diff[w]) for w in plain[name])


def test_changed_onclick_behind_a_skin_setting_is_noticed(tmp_path, confuse_root):
    """Every control with an id in the includes gets another onclick. Controls that Kodi builds only
    for some skin setting (listed in Home.xml as 'with <settings>: ...') must show it too."""
    layout = copy_tree(confuse_root, tmp_path) / '1080i'
    before = [line for line in fingerprint(layout, 'Home.xml') if line.startswith('with ') and ': window | ' not in line]
    assert before
    for path in sorted(layout.glob('Includes*.xml')):
        tree = ET.parse(path)
        for control in tree.getroot().iter('control'):
            if control.get('id'):
                ET.SubElement(control, 'onclick').text = 'Dummy()'
        tree.write(path, encoding='utf-8')
    diff = diff_fingerprints(ROOT / '1080i', layout)
    changed = [line for line in diff.get('Home.xml', []) if line.startswith('+with ') and 'Dummy()' in line]
    assert len(changed) == len(before), (len(changed), len(before))


def test_deviation_without_a_reason_is_refused(tmp_path):
    for entry in ('- `onclick=X`', '- `onclick=X`:', '- `onclick=X`:   '):
        bad = tmp_path / 'DEVIATIONS.md'
        bad.write_text('## Home.xml\n\n' + entry + '\n', encoding='utf-8')
        with pytest.raises(ValueError):
            read_deviations(bad)


def test_reason_may_hold_backticks(tmp_path):
    ok = tmp_path / 'DEVIATIONS.md'
    ok.write_text('## Home.xml\n\n- `-onclick=X`: because `Y` is gone\n', encoding='utf-8')
    assert read_deviations(ok) == {'Home.xml': ['-onclick=X']}


@pytest.mark.parametrize('what, pick, change, expected', [
    ('always on defaultcontrol', lambda e: e.tag == 'defaultcontrol', lambda e: e.set('always', 'zzz'), 'always=zzz'),
    ('allowhiddenfocus on visible', lambda e: e.tag == 'control' and e.get('id') and e.find('visible') is not None,
     lambda e: e.find('visible').set('allowhiddenfocus', 'zzz'), 'allowhiddenfocus=zzz'),
    ('pagecontrol', lambda e: e.tag == 'pagecontrol', lambda e: setattr(e, 'text', '98765'), '98765'),
    ('content source', lambda e: e.tag == 'content' and (e.text or '').strip(), lambda e: setattr(e, 'text', 'plugin://dummy/'), 'plugin://dummy/'),
    ('control in itemlayout', lambda e: e.tag in ('itemlayout', 'focusedlayout'),
     lambda e: e.append(ET.fromstring('<control type="button" id="98765"><onclick>Dummy()</onclick></control>')), 'Dummy()'),
])
def test_other_behaviour_changes_are_noticed(what, pick, change, expected, tmp_path, confuse_root):
    layout = copy_tree(confuse_root, tmp_path) / '1080i'
    mutate(layout, pick, change)
    diff = diff_fingerprints(ROOT / '1080i', layout)
    assert any(expected in line for lines in diff.values() for line in lines), what


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
