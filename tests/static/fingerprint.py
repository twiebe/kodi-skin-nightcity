"""What a window does, as text lines, so two skins can be compared for behaviour.

One line per control with an id or a focusable type, in document order: type, id, every on* and
altclick tag, and the chain of visible and enable conditions from the window down to the control.
Items in a <content> add their actions. Window level adds defaultcontrol, menucontrol and on* tags.
Controls without id and focus are look and stay out, as do the $VAR definitions of
Includes_Look.xml (they are not part of a window)."""
import difflib
import re

import navigation

NOT_WINDOWS = {'Font.xml', 'Variables.xml'}
DEVIATION = re.compile(r'^- `(.+)`(?::.*)?$')


def _text(el):
    return ' '.join((el.text or '').split())


def _is_action(tag):
    return tag.startswith('on') or tag == 'altclick'


def _line(control, chain):
    parts = [control.get('type', ''), control.get('id', '')]
    parts += ['{}={}'.format(c.tag, _text(c)) for c in control if _is_action(c.tag)]
    for content in control.findall('content'):
        parts += ['item.{}={}'.format(a.tag, _text(a)) for item in content.findall('item') for a in item if _is_action(a.tag)]
    if chain:
        parts.append('when ' + ' > '.join(chain))
    return ' | '.join(parts)


def _walk(parent, chain, out):
    for control in parent.findall('control'):
        here = chain + ['{}: {}'.format(c.tag, _text(c)) for c in control if c.tag in ('visible', 'enable')]
        if control.get('id') or control.get('type') in navigation.FOCUSABLE:
            out.append(_line(control, here))
        _walk(control, here, out)


def fingerprint(layout, name):
    """Behaviour lines of window `name` in the 1080i folder `layout`; empty when it has no such file."""
    if not (layout / name).exists():
        return []
    window = navigation.load(name, layout=layout)
    out = ['window | {}={}'.format(tag, _text(window.find(tag))) for tag in ('defaultcontrol', 'menucontrol') if window.find(tag) is not None]
    out += ['window | {}={}'.format(c.tag, _text(c)) for c in window if _is_action(c.tag)]
    controls = window.find('controls')
    if controls is not None:
        _walk(controls, [], out)
    return out


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
        elif window and DEVIATION.match(line):
            found[window].append(DEVIATION.match(line).group(1))
    return found
