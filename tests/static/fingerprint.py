"""What a window does, as text lines, so two skins can be compared for behaviour.

One line per control with an id or a focusable type, in document order: type, id, every on* and
altclick tag, and the chain of visible and enable conditions from the window down to the control.
Items in a <content> add their actions and visible conditions, <content> its source. Window level
adds defaultcontrol, menucontrol and on* tags. The window is built once with no skin setting set and
once more for each skin setting its include conditions ask for; what those add is marked "with
<settings>: <line>".
Controls without id and focus are look and stay out, as do the $VAR definitions of
Includes_Look.xml (they are not part of a window)."""
import difflib
import functools
import re

import navigation

NOT_WINDOWS = {'Font.xml', 'Variables.xml'}
DEVIATION = re.compile(r'^- `(.+?)`: (\S.*)$')
LAYOUTS = ('itemlayout', 'focusedlayout')
HAS_SETTING = re.compile(r'Skin\.HasSetting\(([^)]+)\)$')


def _text(el):
    return ' '.join((el.text or '').split())


def _is_action(tag):
    return tag.startswith('on') or tag == 'altclick'


def _tag(el):
    """Tag with its attributes (always, allowhiddenfocus, ...): they change what the tag does."""
    return el.tag + ''.join('[{}={}]'.format(k, v) for k, v in sorted(el.attrib.items()))


def _line(control, chain):
    parts = [control.get('type', ''), control.get('id', '')]
    parts += ['{}={}'.format(_tag(c), _text(c)) for c in control if _is_action(c.tag) or c.tag == 'pagecontrol']
    for content in control.findall('content'):
        parts.append('{}={}'.format(_tag(content), _text(content)))
        for i, item in enumerate(content.findall('item')):
            parts += ['item{}.{}={}'.format(i, _tag(a), _text(a)) for a in item if _is_action(a.tag) or a.tag == 'visible']
    if chain:
        parts.append('when ' + ' > '.join(chain))
    return ' | '.join(parts)


def _walk(parent, chain, out):
    for control in parent.findall('control'):
        here = chain + ['{}: {}'.format(_tag(c), _text(c)) for c in control if c.tag in ('visible', 'enable')]
        if control.get('id') or control.get('type') in navigation.FOCUSABLE:
            out.append(_line(control, here))
        _walk(control, here, out)
        for layout in LAYOUTS:
            for lay in control.findall(layout):
                _walk(lay, here + [layout], out)


def _lines(window):
    out = ['window | {}={}'.format(_tag(c), _text(c)) for c in window if c.tag in ('defaultcontrol', 'menucontrol') or _is_action(c.tag)]
    controls = window.find('controls')
    if controls is not None:
        _walk(controls, [], out)
    return out


def _negated(text, pos):
    """True when the character at `pos` sits under an odd number of '!' (as in ![a | b] or !a)."""
    stack = []
    for i, ch in enumerate(text[:pos]):
        if ch == '[':
            stack.append(i > 0 and text[i - 1] == '!')
        elif ch == ']' and stack:
            stack.pop()
    return text[pos - 1:pos] == '!' or sum(stack) % 2 == 1


def _assignment(condition, scenario):
    """Skin settings that make `condition` true, taken from its atoms that are not negated, on top of
    `scenario`; None when that does not do it or adds nothing."""
    found = dict(scenario)
    for m in navigation.ATOM.finditer(condition):
        if _negated(condition, m.start()):
            continue
        atom, s = m.group(0), navigation.SKIN_STRING.match(m.group(0))
        if s and s.group(1) == 'IsEqual':
            found.setdefault(s.group(3) if s.group(2) == 'Skin.String' else '{}({})'.format(s.group(2), s.group(3)), s.group(4) or '')
        elif HAS_SETTING.match(atom):
            found.setdefault(HAS_SETTING.match(atom).group(1), True)
    if found == scenario or not navigation.evaluate(condition, found):
        return None
    return found


def _load_recording(name, layout, scenario):
    """The window for the settings in `scenario`, and the include conditions Kodi evaluated for it."""
    seen, real = [], navigation.evaluate

    def record(condition, skin):
        seen.append(condition)
        return real(condition, skin)
    navigation.evaluate = record
    try:
        return navigation.load(name, scenario, layout), seen
    finally:
        navigation.evaluate = real


def _stamp(layout):
    return tuple((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in sorted(layout.glob('*.xml')))


def fingerprint(layout, name):
    """Same as _fingerprint, remembered for as long as the files of `layout` stay as they are: a
    build for every skin setting takes seconds on the big windows."""
    return list(_fingerprint(layout, name, _stamp(layout)))


@functools.lru_cache(maxsize=None)
def _fingerprint(layout, name, stamp):
    """Behaviour lines of window `name` in the 1080i folder `layout`; empty when it has no such file.
    First the window with no skin setting set, then, for each way an include condition of it can be
    made true by skin settings, the lines that setting adds, marked 'with <settings>: <line>'."""
    if not (layout / name).exists():
        return ()
    window, conditions = _load_recording(name, layout, {})
    out = _lines(window)
    known = set(out)
    todo, done, asked = [({}, conditions)], set(), set(conditions)
    while todo:
        scenario, conditions = todo.pop(0)
        for condition in conditions:
            found = _assignment(condition, scenario)
            key = tuple(sorted(found.items())) if found else None
            if found and key not in done:
                done.add(key)
                window, more = _load_recording(name, layout, found)
                label = 'with ' + ', '.join('{}={}'.format(k, v) for k, v in key) + ': '
                for line in _lines(window):
                    if line not in known:
                        known.add(line)
                        out.append(label + line)
                todo.append((found, [c for c in more if c not in asked]))
                asked.update(more)
    return tuple(out)


def _windows(layout):
    return {p.name for p in layout.glob('*.xml') if not p.name.startswith('Includes') and p.name not in NOT_WINDOWS}


def diff_fingerprints(root_layout, other_layout):
    """Per window file the lines that differ: '-' for a line only in the first folder, '+' for one
    only in the second. Windows that behave the same are left out."""
    diff = {}
    for name in sorted(_windows(root_layout) | _windows(other_layout)):
        lines = [l for l in difflib.unified_diff(fingerprint(root_layout, name), fingerprint(other_layout, name), lineterm='', n=0)
                 if l[:1] in '+-' and not l.startswith(('---', '+++'))]
        if lines:
            diff[name] = lines
    return diff


def read_deviations(path):
    """DEVIATIONS.md: '## File.xml' per window, below it '- `diff line`: reason' per allowed difference."""
    found, window = {}, None
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith('## '):
            window = line[3:].strip()
            found.setdefault(window, [])
        elif window and line.startswith('- '):
            match = DEVIATION.match(line)
            if not match:
                raise ValueError('{}: a deviation needs a reason after the closing backtick: {}'.format(path, line))
            found[window].append(match.group(1))
    return found
