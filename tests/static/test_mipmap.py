"""Mipmaps for artwork drawn smaller than Kodi decoded it: the texture attribute mipmap="true"
(Kodi 23, skinning v23; Kodi 21 and 22 read no such attribute and leave it be). Without them a
card shows a big image pixelated, on a Mali GPU (AM6B) most: a 1920x1080 still of an episode,
which Kodi caches at full size (16:9, fanartres), on a card of 320x180. Artwork drawn at its size
(fanart, backdrops) needs none, mipmaps take a third more video memory."""
from conftest import ROOT, parse

SKINS = (ROOT / '1080i', ROOT / 'skins' / 'confuse' / '1080i')


def _textures(folder, name):
    include = next((i for i in parse(folder / 'Includes_Look.xml').iter('include') if i.get('name') == name), None)
    assert include is not None, (folder, name)
    return list(include.iter('texture'))


def test_card_artwork_is_mipmapped():
    for folder in SKINS:
        for name in ('LookCardArt', 'LookCardArtFocused'):
            textures = _textures(folder, name)
            assert textures and all(t.get('mipmap') == 'true' for t in textures), (folder, name)


def test_spotlight_poster_and_logo_are_mipmapped_and_preloaded_so():
    """The preloads of the spotlight (10x10 images of the items to come) load what the spotlight
    draws: the mipmap flag is part of the key of a background texture, a plain preload would be a
    second copy. Fanart is drawn full screen: none."""
    textures = [t for t in parse(ROOT / '1080i' / 'Includes_Home.xml').iter('texture') if t.get('background') == 'true']
    for t in textures:
        art = t.text or ''
        if 'Art(poster)' in art or 'Art(clearlogo)' in art:
            assert t.get('mipmap') == 'true', art
        if 'Art(fanart)' in art:
            assert t.get('mipmap') is None, art
    assert sum('Art(clearlogo)' in (t.text or '') for t in textures) == 3


def test_backdrops_are_not_mipmapped():
    for path in (ROOT / '1080i' / 'Includes_Base.xml', ROOT / 'skins' / 'confuse' / '1080i' / 'Includes_Look.xml'):
        for t in parse(path).iter('texture'):
            if 'fanart' in (t.get('colordiffuse') or '') or 'mask_hero' in (t.get('diffuse') or ''):
                assert t.get('mipmap') is None, path
