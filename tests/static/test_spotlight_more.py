"""A dim > right of the spotlight buttons, as tall as they are: Right on the last button moves
the spotlight on to the next title (movies, shows, music)."""
import re
import xml.etree.ElementTree as ET

from conftest import ROOT

SKIN = ROOT / '1080i'


def _include(name):
    text = (SKIN / 'Includes_Home.xml').read_text(encoding='utf-8')
    match = re.search(r'<include name="{}">(.*?)</include>'.format(name), text, re.S)
    assert match, name
    return match.group(1)


def test_spotlight_more_is_a_dim_arrow_as_tall_as_the_buttons():
    body = _include('SpotlightMore')
    assert '<control type="label">' in body
    assert '<label>&gt;</label>' in body
    assert '<textcolor>state</textcolor>' in body
    assert '<height>54</height>' in body
    assert '<aligny>center</aligny>' in body


def test_every_spotlight_button_row_ends_with_the_arrow():
    rows = []
    for name in ('Includes_Home.xml', 'Includes_Music.xml'):
        root = ET.parse(SKIN / name).getroot()
        rows += [c for c in root.iter('control') if c.get('type') == 'grouplist'
                 and c.findtext('left') == '384' and c.findtext('top') == '490']
    assert len(rows) == 3, len(rows)
    for row in rows:
        last = [c for c in row if c.tag in ('include', 'control')][-1]
        assert last.tag == 'include' and last.text == 'SpotlightMore', ET.tostring(last)[:80]
