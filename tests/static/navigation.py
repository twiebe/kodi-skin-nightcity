"""Remote-control reachability for skin windows.

Kodi has no spatial navigation: a control is reachable only through explicit onup/ondown/onleft/
onright actions, its grouplist neighbours, or the window's defaultcontrol/menucontrol. This module
expands includes (params, defaults, <nested/>) and walks those links like a D-pad would.
"""
import re
import xml.etree.ElementTree as ET

from conftest import ROOT

LAYOUT = ROOT / '1080i'
FOCUSABLE = {'button', 'radiobutton', 'togglebutton', 'list', 'panel', 'wraplist', 'fixedlist', 'edit',
             'spincontrol', 'spincontrolex', 'slider', 'sliderex', 'colorbutton', 'scrollbar'}
DIRS = ('onup', 'ondown', 'onleft', 'onright')
PARAM = re.compile(r'\$PARAM\[([^\]]+)\]')
SETFOCUS = re.compile(r'SetFocus\((\d+)[,)]')
ATOM = re.compile(r'[A-Za-z][\w.]*(?:\((?:[^()]|\([^()]*\))*\))?')
SKIN_STRING = re.compile(r'String\.(IsEqual|IsEmpty)\((Skin\.String|Window(?:\(Home\))?\.Property)\(([^)]+)\)(?:,([^)]*))?\)$')


def _atom(text, skin):
    if text in ('true', 'false'):
        return text == 'true'
    m = SKIN_STRING.match(text)
    if m:
        key = m.group(3) if m.group(2) == 'Skin.String' else '{}({})'.format(m.group(2), m.group(3))
        value = skin.get(key, '')
        return value == '' if m.group(1) == 'IsEmpty' else value.lower() == (m.group(4) or '').lower()
    m = re.match(r'Skin\.HasSetting\(([^)]+)\)$', text)
    if m:
        return bool(skin.get(m.group(1)))
    raise ValueError('cannot evaluate include condition ' + text)


def evaluate(condition, skin):
    """Value of an include condition for the skin settings in `skin` (Skin.String and
    Skin.HasSetting names to values, 'Window.Property(name)' or 'Window(Home).Property(name)' for
    properties, missing ones empty):
    Kodi builds a window with the includes whose condition holds when it loads it."""
    expr, pos = [], 0
    for m in ATOM.finditer(condition):
        expr.append(condition[pos:m.start()])
        expr.append(' {} '.format(_atom(m.group(0), skin)))
        pos = m.end()
    expr.append(condition[pos:])
    text = ''.join(expr).replace('[', '(').replace(']', ')').replace('+', ' and ').replace('|', ' or ').replace('!', ' not ')
    return bool(eval(text, {}))


def _definitions():
    defs = {}
    for path in LAYOUT.glob('Includes*.xml'):
        for el in ET.parse(path).getroot():
            if el.tag == 'include' and el.get('name'):
                defs[el.get('name')] = el
    return defs


def _subst(text, params):
    return None if text is None else PARAM.sub(lambda m: params.get(m.group(1), ''), text)


def _expand(el, params, defs, skin):
    out = []
    for child in el:
        if child.tag == 'include' and not child.get('name'):
            if child.get('condition') and not evaluate(_subst(child.get('condition'), params), skin):
                continue
            name = _subst(child.get('content') or (child.text or '').strip(), params)
            definition = defs[name]
            body = definition.find('definition')
            values = dict(params) if body is None else {}
            for p in definition.findall('param'):
                if p.get('default') is not None:
                    values[p.get('name')] = _subst(p.get('default'), params)
            for p in child.findall('param'):
                values[p.get('name')] = _subst(p.get('value') if p.get('value') is not None else p.text or '', params)
            holder = ET.Element('nested')
            for k in child:
                if k.tag != 'param':
                    holder.append(k)
            nested = _expand(holder, params, defs, skin)
            for c in _expand(body if body is not None else definition, values, defs, skin):
                if c.tag == 'param':
                    continue
                if c.tag == 'nested':
                    out.extend(nested)
                    continue
                _fill(c, nested)
                out.append(c)
        else:
            node = ET.Element(child.tag, {k: _subst(v, params) for k, v in child.attrib.items()})
            node.text = _subst(child.text, params)
            node.extend(_expand(child, params, defs, skin))
            out.append(node)
    return out


def _fill(el, nested):
    for i, k in enumerate(list(el)):
        if k.tag == 'nested':
            el.remove(k)
            for j, n in enumerate(nested):
                el.insert(i + j, n)
        else:
            _fill(k, nested)


def load(name, skin=None):
    """The window as Kodi builds it for the skin settings in `skin` (default: none set)."""
    root = ET.parse(LAYOUT / name).getroot()
    window = ET.Element(root.tag, root.attrib)
    window.extend(_expand(root, {}, _definitions(), skin or {}))
    return window


def analyze(name, skin=None):
    window = load(name, skin)
    parent, controls = {}, {}

    def walk(el, par):
        for c in el.findall('control'):
            if c.get('id'):
                controls[c.get('id')] = c
            parent[c] = par
            walk(c, c)
    walk(window.find('controls'), None)

    def target(text):
        # SetFocus(id[,position,absolute]) moves like a plain id
        m = SETFOCUS.match(text)
        return m.group(1) if m else text

    def actions(c):
        return {d: [target((e.text or '').strip()) for e in c.findall(d)] for d in DIRS}

    def focusable(c):
        # an empty grouplist is filled by Kodi at runtime (settings), so it takes focus itself;
        # a disabled control (frame text in a tab chain) never takes focus
        if (c.findtext('enable') or '').strip() == 'false':
            return False
        return c.get('type') in FOCUSABLE or (c.get('type') == 'grouplist' and c.find('control') is None)

    def slot_actions(c):
        """Kodi's CGUIControlGroupList::AddControl: every direct child of a grouplist gets the
        id of its neighbour on the grouplist axis (the grouplist's own action at the ends) unless
        it has one; a control inside a group in the grouplist gets nothing from it."""
        a = actions(c)
        p = parent[c]
        if p is None or p.get('type') != 'grouplist':
            return a
        vertical = (p.findtext('orientation') or 'vertical').strip() == 'vertical'
        siblings = p.findall('control')
        i = siblings.index(c)
        pa = actions(p)
        before, after = ('onup', 'ondown') if vertical else ('onleft', 'onright')
        # a neighbour without id gives navigation 0, where Kodi stops
        a[before] = [siblings[i - 1].get('id') or '0'] if i > 0 else pa[before]
        a[after] = [siblings[i + 1].get('id') or '0'] if i < len(siblings) - 1 else pa[after]
        for d in (('onleft', 'onright') if vertical else ('onup', 'ondown')):
            a[d] = a[d] or pa[d]
        return a

    links = {cid: slot_actions(c) for cid, c in controls.items()}

    def first_focusable(c):
        """CGUIControlGroup::GetFirstFocusableControl: descend, never follow actions."""
        if focusable(c):
            return [c.get('id')]
        for k in c.findall('control'):
            found = first_focusable(k)
            if found:
                return found
        return []

    def resolve(target, direction, seen=()):
        """CGUIWindow::OnMove: focus the target, else a focusable control in it, else follow the
        target's own action in the same direction."""
        c = target if isinstance(target, ET.Element) else controls.get(target)
        if c is None:
            return []
        if focusable(c):
            return [c.get('id')]
        if c.get('type') in ('grouplist', 'group'):
            found = first_focusable(c)
            if found:
                return found
        cid = c.get('id')
        if not cid or cid in seen:
            return []
        found = []
        for t in links.get(cid, {}).get(direction, []):
            found += resolve(t, direction, seen + (cid,))
        return found

    def reach(start):
        seen, queue = set(start), list(start)
        while queue:
            for direction, targets in links.get(queue.pop(), {}).items():
                for t in targets:
                    for y in resolve(t, direction):
                        if y not in seen:
                            seen.add(y)
                            queue.append(y)
        return seen

    start = []
    for tag in ('defaultcontrol', 'menucontrol'):
        start += resolve((window.findtext(tag) or '').strip(), 'ondown')
    # a stand-in that passes the focus on when it gets it (SetFocus in onfocus): where it can
    # pass it to is where the window starts too
    hops = list(start)
    while hops:
        c = controls.get(hops.pop())
        for e in c.findall('onfocus') if c is not None else []:
            m = SETFOCUS.match((e.text or '').strip())
            for y in resolve(m.group(1), 'ondown') if m else []:
                if y not in start:
                    start.append(y)
                    hops.append(y)
    seen = reach(start)
    lost = sorted((cid for cid, c in controls.items() if focusable(c) and cid not in seen), key=int)
    traps = sorted((cid for cid in seen if not set(start) & reach([cid])), key=int)
    return lost, traps


def unreachable(name, skin=None):
    """Ids of focusable controls a D-pad cannot reach from defaultcontrol or menucontrol."""
    return analyze(name, skin)[0]


def dead_ends(name, skin=None):
    """Ids of reachable controls from which a D-pad never gets back to where the window started."""
    return analyze(name, skin)[1]
