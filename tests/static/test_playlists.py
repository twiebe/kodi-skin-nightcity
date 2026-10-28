from conftest import ROOT, parse


def playlist(name):
    return parse(ROOT / 'playlists' / name)


def rules(pl):
    return [(r.get('field'), r.get('operator'), [v.text for v in r.iter('value')]) for r in pl.iter('rule')]


def test_spotlight_playlists():
    for name in ('SpotlightAll.xsp', 'SpotlightUnwatched.xsp'):
        pl = playlist(name)
        assert pl.get('type') == 'movies', name
        assert pl.find('limit') is None, name  # the whole library, in random order
        assert pl.findtext('order') == 'random', name
    assert rules(playlist('SpotlightAll.xsp')) == []
    assert rules(playlist('SpotlightUnwatched.xsp')) == [('playcount', 'is', ['0'])]


def test_spotlight_layout_limits():
    """Review focus 4: long titles and plots must not grow into the widget rows."""
    home = parse(ROOT / '1080i' / 'Includes_Home.xml')
    body = next(el for el in home.iter('include') if el.get('name') == 'HeroBody')
    controls = {c.get('id'): c for c in body.iter('control') if c.get('id')}
    title = next(i for i in body.iter('include') if i.get('content') == 'GlitchTitle')
    defaults = {p.get('name'): p.get('default') for p in body.findall('param')}
    args = {p.get('name'): p.get('value') for p in title.findall('param')}
    args = {k: defaults[v[7:-1]] if v.startswith('$PARAM[') and k != 'id' else v for k, v in args.items()}
    assert args['id'] == '$PARAM[titleid]'
    assert int(args['left']) + int(args['width']) <= 1920 - 64  # one line, cut at the right margin
    plot = controls['$PARAM[plotid]']
    assert plot.get('type') == 'textbox'
    assert int(plot.findtext('height')) <= 160
