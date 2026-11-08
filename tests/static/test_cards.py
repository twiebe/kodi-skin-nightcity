"""Artwork cards, their progress lines and how containers load their images."""
import re

from PIL import Image

from conftest import ROOT, layout_files, parse
from navigation import with_look

CONTAINERS = ('list', 'panel', 'fixedlist', 'wraplist')


def cut_length(path):
    """Length of the top right cut: transparent pixels at the right end of the top row."""
    image = Image.open(path).convert('RGBA')
    alpha = image.getchannel('A')
    row = [alpha.getpixel((x, 0)) for x in range(image.width - 1, -1, -1)]
    return next(n for n, a in enumerate(row) if a >= 128)


def card_uses():
    for p in layout_files():
        for el in parse(p).iter('include'):
            if el.get('content') == 'CutCard':
                params = {x.get('name'): x.get('value') for x in el.findall('param')}
                yield p.name, params


def test_card_masks_match_size_and_frame():
    """A mask is drawn 1:1 at its card's size with the frame's cut, so the artwork ends exactly
    under the cut of the frame instead of poking past it."""
    frame = cut_length(ROOT / 'media' / 'ui' / 'cut.png')
    for name, params in card_uses():
        width, height = params.get('width', '200'), params.get('height', '300')
        mask = params.get('mask', 'ui/mask_200x300.png')
        assert mask == 'ui/mask_{}x{}.png'.format(width, height), (name, mask)
        image = Image.open(ROOT / 'media' / mask)
        assert image.size == (int(width), int(height)), (name, mask)
        assert abs(cut_length(ROOT / 'media' / mask) - frame) <= 1, (name, mask)


def test_one_progress_colour():
    """Movies and episodes share the progress colour: no ProgressLine sets its own."""
    for p in layout_files():
        for el in parse(p).iter('include'):
            if el.get('content') == 'ProgressLine':
                params = {x.get('name') for x in el.findall('param')}
                assert 'color' not in params, p.name


def _art_includes():
    """Include names whose definition shows artwork, also through other includes."""
    bodies = {}
    for p in layout_files():
        for el in parse(p).iter('include'):
            if el.get('name'):
                bodies[el.get('name')] = el
    art = {n for n, el in bodies.items() if 'Art(' in ''.join(el.itertext()) or
           any('Art(' in (x.get('value') or '') for x in el.iter('param'))}
    while True:
        more = {n for n, el in bodies.items() if n not in art and
                any((i.get('content') or (i.text or '').strip()) in art for i in el.iter('include'))}
        if not more:
            return art
        art |= more


def _shows_art(layout, art):
    text = ''.join(layout.itertext()) + ''.join(x.get('value') or '' for x in layout.iter('param'))
    return 'Art(' in text or any((i.get('content') or (i.text or '').strip()) in art
                                 for i in layout.iter('include'))


def test_containers_preload_artwork():
    """Containers with artwork load the images of the next and previous page in the background,
    so scrolling does not show empty cards first."""
    art = _art_includes()
    missing = []
    for p in layout_files():
        for c in parse(p).iter('control'):
            if c.get('type') not in CONTAINERS:
                continue
            layouts = c.findall('itemlayout') + c.findall('focusedlayout')
            if any(_shows_art(l, art) for l in layouts) and c.findtext('preloaditems') != '2':
                missing.append((p.name, c.get('id')))
    assert not missing


def _card():
    return with_look(next(el for p in layout_files() for el in parse(p).iter('include') if el.get('name') == 'CutCard'))


def test_card_mask_fits_card_not_cropped_image():
    """With aspectratio scale Kodi crops the artwork and would stretch the mask over the uncropped
    image, so the cut lands outside the frame for anything not exactly the card's ratio."""
    for img in _card().iter('control'):
        texture = img.find('texture')
        if img.get('type') == 'image' and texture is not None and texture.get('diffuse') and \
                img.findtext('aspectratio') == 'scale':
            assert img.find('aspectratio').get('scalediffuse') == 'false'


def test_every_card_is_cut():
    """Every card has the cut corners, focused or not: its artwork and the plate under it are cut
    by the card's mask. An unfocused card has a faint frame in border_dim; the focus brings the
    bright frame and the glow."""
    card = _card()
    art = [c for c in card.iter('control') if c.get('type') == 'image' and
           '$PARAM[image]' in (c.findtext('texture') or '')]
    assert len(art) == 2 and all(c.find('texture').get('diffuse') == '$PARAM[mask]' for c in art)
    assert sorted(c.findtext('visible') for c in art) == ['!$PARAM[focused]', '$PARAM[focused]']
    plates = [c for c in card.iter('control') if c.findtext('texture') == 'ui/white.png']
    assert plates and all(c.find('texture').get('diffuse') == '$PARAM[mask]' for c in plates)
    frames = {c.findtext('visible'): c.find('texture').get('colordiffuse')
              for c in card.iter('control') if c.findtext('texture') == 'ui/cut.png'}
    assert frames == {'$PARAM[focused]': 'focus', '!$PARAM[focused]': 'border_dim'}


DOG_EAR = 22  # px, legs of the unwatched mark


def test_unwatched_dog_ear():
    """Unwatched, never started movies, episodes and shows get a cyan (focus) dog-ear in the bottom right
    corner (like Plex marks unwatched), a good deal bigger than the frame's cut (DOG_EAR); that
    corner has no cut, so one ear serves focused and unfocused cards. No ✓ on episode stills."""
    ears = [c for c in _card().iter('control') if c.get('type') == 'image' and
            'dogear' in (c.findtext('texture') or '')]
    assert [c.findtext('texture') for c in ears] == ['ui/dogear.png']
    ear = ears[0]
    # in the colour of the focus highlight (the user's choice): it reads at a glance
    assert ear.find('texture').get('colordiffuse') == 'focus'
    assert ear.findtext('right') == '0' and ear.findtext('bottom') == '0'
    assert cut_length(ROOT / 'media' / 'ui' / 'cut.png') < DOG_EAR
    frame = DOG_EAR
    assert ear.findtext('width') == ear.findtext('height') == str(frame)
    visible = ear.findtext('visible')
    assert 'Integer.IsEqual($PARAM[item].PlayCount,0)' in visible and '!$PARAM[item].IsResumable' in visible
    # a show stays at PlayCount 0 until every episode is watched: its own count says "none yet",
    # as a string so that an item without the count gets no ear
    assert ('[String.IsEqual($PARAM[item].DBType,tvshow) + String.IsEqual($PARAM[item].Property(WatchedEpisodes),0)]'
            in visible)
    assert '!String.IsEmpty($PARAM[item].DBID)' in visible and 'focused' not in visible
    image = Image.open(ROOT / 'media' / 'ui' / 'dogear.png').convert('RGBA')
    assert image.size == (frame, frame)
    alpha = image.getchannel('A')
    assert alpha.getpixel((frame - 1, frame - 1)) > 200 and alpha.getpixel((0, 0)) < 50
    assert not (ROOT / 'media' / 'ui' / 'dogear_cut.png').exists()
    assert '✓' not in (ROOT / '1080i' / 'Includes_Info.xml').read_text(encoding='utf-8')


def test_dog_ear_asks_the_cards_own_item():
    """Inside a list layout ListItem is the card's item, by default too. The hero poster is in no
    list: there a bare ListItem is whatever holds the focus (a card of a row, a spotlight button),
    so the ear came and went with the focus. The hero hands in the item of its spotlight."""
    card = _card()
    assert next(p for p in card.findall('param') if p.get('name') == 'item').get('default') == 'ListItem'
    ear = next(c for c in card.iter('control') if 'dogear' in (c.findtext('texture') or ''))
    assert not re.search(r'(?<![\w.\]])ListItem\.', ear.findtext('visible'))
    hero = next(el for p in layout_files() for el in parse(p).iter('include') if el.get('name') == 'HeroBody')
    poster = next(el for el in hero.iter('include') if el.get('content') == '$PARAM[posterlook]')
    assert {p.get('name'): p.get('value') for p in poster.findall('param')}['item'] == '$PARAM[item]'


def _ancestors(root, target):
    parents = {c: p for p in root.iter() for c in p}
    node = target
    while node in parents:
        node = parents[node]
        yield node


def test_dog_ear_not_dimmed():
    """Dimming a row darkens the artwork, the dog-ear stays opaque."""
    card = _card()
    ears = [c for c in card.iter('control') if 'dogear' in (c.findtext('texture') or '')]
    for ear in ears:
        for group in _ancestors(card, ear):
            assert not [a for a in group.findall('animation') if a.get('effect') == 'fade'], 'ear inside a dimmed group'


def test_card_nested_at_top_level():
    """Kodi resolves <nested/> only as a child of the include's top control; deeper, the extras
    (title fallback, progress line) silently vanish."""
    for p in layout_files():
        for inc in parse(p).iter('include'):
            definition = inc.find('definition')
            if definition is None:
                continue
            for top in definition:
                for deep in top.iter('control'):
                    if deep is not top:
                        assert deep.find('nested') is None, (p.name, inc.get('name'))


def test_current_episode_is_marked_by_its_title():
    """The current episode of an episode page's list (the selected card: the head shows it) has its
    number and title in the accent colour, the others white with a dimmed number; no line over
    its still any more."""
    inc = with_look(next(i for i in parse(ROOT / '1080i' / 'Includes_Info.xml').iter('include') if i.get('name') == 'EpisodeCard'))
    assert not [c for c in inc.iter('control') if c.get('type') == 'image' and c.findtext('texture') == 'ui/white.png']
    titles = {c.findtext('visible'): c.findtext('textcolor') for c in inc.iter('control') if c.get('type') == 'label'}
    assert titles == {'$PARAM[selected]': 'accent', '!$PARAM[selected]': 'text'}
