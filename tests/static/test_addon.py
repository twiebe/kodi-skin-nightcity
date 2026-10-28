import re
import zipfile

import pytest

from conftest import ROOT, all_xml_files, parse


def test_addon_xml_identity():
    addon = parse(ROOT / 'addon.xml')
    assert addon.get('id') == 'skin.nightcity'
    assert addon.get('version') == '0.4.53'
    res = addon.find(".//extension[@point='xbmc.gui.skin']/res")
    assert res is not None
    assert res.attrib == {'width': '1920', 'height': '1080', 'aspect': '16:9',
                          'default': 'true', 'folder': '1080i'}


def _version(text):
    return tuple(int(part) for part in text.split('.'))


def test_imports():
    imports = {i.get('addon'): i.get('version') for i in parse(ROOT / 'addon.xml').iter('import')}
    assert imports['xbmc.gui'] == '5.17.0'
    assert _version(imports['plugin.video.themoviedb.helper']) <= (6, 18, 3)


@pytest.mark.parametrize('path', all_xml_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_all_xml_parses(path):
    parse(path)


def test_build_zip(tmp_path):
    from build import build
    out = build(tmp_path)
    assert out.name == 'skin.nightcity-0.4.53.zip'
    names = zipfile.ZipFile(out).namelist()
    assert 'skin.nightcity/addon.xml' in names
    assert 'skin.nightcity/scripts/nightcity.py' in names
    fonts = {n.split('/')[-1] for n in names if '/fonts/' in n}
    assert {'Rajdhani-Medium.ttf', 'NotoSansSymbols2-Regular.ttf', 'JetBrainsMono-Regular.ttf'}.isdisjoint(fonts)
    assert {'RetroUI-Medium.ttf', 'ShareTechMono-Regular.ttf', 'Rajdhani-OFL.txt'} <= fonts
    for excluded in ('tests/', 'docs/', 'tools/', '.superpowers/', '.venv/'):
        assert not any(n.startswith('skin.nightcity/' + excluded) for n in names), excluded


def test_news_names_version():
    addon = parse(ROOT / 'addon.xml')
    news = addon.find('.//news')
    assert news is not None and addon.get('version') in news.text


def test_string_ids_unique():
    for po in ROOT.glob('language/*/strings.po'):
        ids = re.findall(r'^msgctxt "#(\d+)"$', po.read_text(encoding='utf-8'), re.M)
        assert len(ids) == len(set(ids)), (po.parent.name, sorted({i for i in ids if ids.count(i) > 1}))


def test_english_only_for_now():
    """No translation yet: summary and description in English only."""
    langs = {el.get('lang') for el in parse(ROOT / 'addon.xml').iter() if el.get('lang')}
    assert langs <= {'en_GB'}
