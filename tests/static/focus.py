"""Remote-control focus of a window in one runtime state: which controls show, which can take the
focus and where Up, Down, Left, Right and OK lead.

navigation.py proves reachability over every link a control has, conditions ignored. Dead ends
in pages filled at runtime (TMDb lists that load, stay empty or switch with a tab) hide in the
conditions, so this module evaluates them for a given state, the way Kodi does:

- CGUIBaseContainer::CanFocus: a list takes the focus while it has items or while its content
  still loads, never once it is empty.
- CGUIAction::GetNavigation: of the numeric actions in a direction the first whose condition
  holds moves the focus; every other action whose condition holds runs as a builtin.
- CGUIWindow::OnMove: a target that cannot take the focus passes the move on with its own action
  in the same direction; a group passes the focus to its first child that can take it.
- CGUIControlGroupList: a control in a grouplist has its neighbours on the grouplist's axis
  unless it has its own action, the grouplist's actions at the ends and across.

A state is a State: the page's list item, the item counts of its containers ('items',
'updating', 'empty' or 'stale': items of the page before, which a list keeps until it loads
its own) and Window(Home) properties. Infobools it does not know raise, so a new
condition in a page fails the tests instead of slipping through.
"""
import re

from navigation import DIRS, FOCUSABLE, load

NUMBER = re.compile(r'-?\d+$')
SETFOCUS = re.compile(r'SetFocus\((\d+)[,)]')
LEAVE = re.compile(r'(Action\((Back|PreviousMenu)\)|Dialog\.Close\(|ActivateWindow\(|ReplaceWindow\()', re.I)
ATOM = re.compile(r'[A-Za-z][\w.]*(?:\((?:[^()]|\([^()]*\))*\))?(?:\.[A-Za-z]\w*(?:\((?:[^()]|\([^()]*\))*\))?)*')
LISTS = {'list', 'panel', 'wraplist', 'fixedlist'}


class State:
    """dbtype, dbid and tmdb_type of ListItem; containers {id: 'items' | 'updating' | 'empty' |
    'stale'};
    props: Window(Home) properties; extra: any other infobool, by its exact text."""

    def __init__(self, dbtype='', dbid=False, tmdb_type='', containers=None, props=None, extra=None,
                 hidden=()):
        self.dbtype, self.dbid, self.tmdb_type = dbtype, dbid, tmdb_type
        # controls the window hides from code (the keys of the keyboard without a character)
        self.hidden = set(hidden)
        self.focus = None
        self.containers = containers or {}
        self.props = props or {}
        self.extra = extra or {}

    def __repr__(self):
        shown = {k: v for k, v in self.props.items() if v}
        return 'State({} {}{} {} {}{})'.format(self.dbtype, 'dbid ' if self.dbid else '', self.tmdb_type,
                                              self.containers, shown, self.extra or '')

    def atom(self, text, visible):
        rules = (
            (r'(true|false)$', lambda m: m.group(1) == 'true'),
            (r'String\.IsEqual\(ListItem\.DBType,(\w+)\)$', lambda m: self.dbtype == m.group(1)),
            (r'String\.IsEqual\(ListItem\.Property\(tmdb_type\),(\w+)\)$', lambda m: self.tmdb_type == m.group(1)),
            (r'String\.IsEmpty\(ListItem\.Property\(tmdb_type\)\)$', lambda m: not self.tmdb_type),
            (r'String\.IsEmpty\(ListItem\.DBID\)$', lambda m: not self.dbid),
            (r'Integer\.IsGreater\(Container\((\d+)\)\.NumItems,0\)$',
             lambda m: self.containers.get(m.group(1), 'empty') in ('items', 'stale')),
            (r'Container\((\d+)\)\.IsUpdating$', lambda m: self.containers.get(m.group(1), 'empty') == 'updating'),
            (r'String\.IsEmpty\(Window\(Home\)\.Property\(([^)]+)\)\)$', lambda m: not self.props.get(m.group(1))),
            (r'String\.IsEqual\(Window\(Home\)\.Property\(([^)]+)\),([^)]*)\)$',
             lambda m: self.props.get(m.group(1), '') == m.group(2)),
            (r'Control\.IsVisible\((\d+)\)$', lambda m: visible(m.group(1))),
            (r'Control\.HasFocus\((\d+)\)$', lambda m: self.focus == m.group(1)),
            # $EXP[TmdbFresh<id>] (Includes_Tmdb.xml): the list shows items of this page
            (r'TmdbFresh(\d+)$', lambda m: self.containers.get(m.group(1), 'empty') == 'items'),
        )
        if text in self.extra:
            return self.extra[text]
        for pattern, value in rules:
            m = re.match(pattern, text)
            if m:
                return value(m)
        raise KeyError('no value for {} in {}'.format(text, self))


class Page:
    """A window as Kodi builds it (includes expanded), evaluated for one State at a time."""

    def __init__(self, name, skin=None):
        self.name = name
        self.window = load(name, skin)
        self.parent, self.controls = {}, {}

        def walk(el, par):
            for c in el.findall('control'):
                if c.get('id'):
                    self.controls[c.get('id')] = c
                self.parent[c] = par
                walk(c, c)
        walk(self.window.find('controls'), None)

    # conditions and visibility

    def holds(self, condition, state):
        if not condition:
            return True
        condition = re.sub(r'\$EXP\[(\w+)\]', r'\1', condition)
        expr, pos = [], 0
        for m in ATOM.finditer(condition):
            expr.append(condition[pos:m.start()])
            expr.append(' {} '.format(state.atom(m.group(0), lambda cid: self.visible(cid, state))))
            pos = m.end()
        expr.append(condition[pos:])
        text = ''.join(expr).replace('[', '(').replace(']', ')').replace('+', ' and ').replace('|', ' or ').replace('!', ' not ')
        return bool(eval(text, {}))

    def visible(self, c, state):
        c = self.controls[c] if isinstance(c, str) else c
        if c.get('id') in state.hidden:
            return False
        while c is not None:
            if not all(self.holds((v.text or '').strip(), state) for v in c.findall('visible')):
                return False
            c = self.parent[c]
        return True

    def can_focus(self, c, state):
        c = self.controls[c] if isinstance(c, str) else c
        kind = c.get('type')
        if kind not in LISTS | FOCUSABLE | {'group', 'grouplist'}:
            return False
        if not self.visible(c, state) or (c.findtext('enable') or '').strip() == 'false':
            return False
        if kind in LISTS:
            return state.containers.get(c.get('id'), 'items') in ('items', 'updating', 'stale')
        if kind in FOCUSABLE:
            return True
        if kind in ('group', 'grouplist'):
            return any(self.can_focus(k, state) for k in c.findall('control'))
        return False

    def faded(self, c, state):
        """A TMDb list that does not show its own items yet (TmdbStaleFade): it is faded out and
        the remote waits for it (nc_info_enter), so it need not be reachable."""
        fades = [a for a in c.findall('animation') if 'TmdbFresh' in (a.get('condition') or '')]
        return bool(fades) and state.containers.get(c.get('id'), 'items') != 'items'

    def first_focusable(self, c, state):
        """The control that takes the focus when `c` gets it: itself or its first child that can."""
        c = self.controls.get(c) if isinstance(c, str) else c
        if c is None or not self.can_focus(c, state):
            return None
        if c.get('type') in ('group', 'grouplist'):
            for k in c.findall('control'):
                found = self.first_focusable(k, state)
                if found:
                    return found
            return None
        return c.get('id')

    # actions

    def actions(self, c, tag):
        return [(e.get('condition') or '', (e.text or '').strip()) for e in c.findall(tag)]

    def nav(self, c, direction):
        """(condition, action) pairs of `c` in `direction`, grouplist neighbours included."""
        own = self.actions(c, direction)
        p = self.parent[c]
        if p is None or p.get('type') != 'grouplist':
            return own
        vertical = (p.findtext('orientation') or 'vertical').strip() == 'vertical'
        before, after = ('onup', 'ondown') if vertical else ('onleft', 'onright')
        siblings = p.findall('control')
        i = siblings.index(c)
        if direction == before:
            return own or ([('', siblings[i - 1].get('id') or '0')] if i > 0 else self.nav(p, direction))
        if direction == after:
            return own or ([('', siblings[i + 1].get('id') or '0')] if i < len(siblings) - 1 else self.nav(p, direction))
        return own or self.nav(p, direction)

    def move(self, cid, direction, state):
        """Where the focus goes from `cid`: (control id or None, builtins that ran)."""
        ran, history, current = [], [], self.controls[cid]
        state.focus = cid
        nxt = cid
        while True:
            history.append(nxt)
            nxt = None
            for condition, text in self.nav(current, direction):
                if not self.holds(condition, state):
                    continue
                if NUMBER.match(text):
                    nxt = nxt or text
                else:
                    ran.append(text)
            for text in ran:
                m = SETFOCUS.match(text)
                if m and self.first_focusable(m.group(1), state):
                    return self.first_focusable(m.group(1), state), ran
            if not nxt or nxt == '0' or nxt in history or nxt not in self.controls:
                return None, ran
            found = self.first_focusable(nxt, state)
            if found:
                return found, ran
            current = self.controls[nxt]

    def clicks(self, cid, state):
        """Builtins OK runs on `cid` (an item of a list: the list's onclick)."""
        return [text for condition, text in self.actions(self.controls[cid], 'onclick') if self.holds(condition, state)]

    # the whole page

    def start(self, state):
        return self.first_focusable((self.window.findtext('defaultcontrol') or '').strip(), state)

    def graph(self, state):
        """Focus moves from every control the remote reaches: {id: {direction: (target, builtins)}}."""
        start = self.start(state)
        seen, queue, edges = set(), [start] if start else [], {}
        while queue:
            cid = queue.pop()
            if cid in seen:
                continue
            seen.add(cid)
            edges[cid] = {d: self.move(cid, d, state) for d in DIRS}
            queue.extend(t for t, _ in edges[cid].values() if t and t not in seen)
        return edges

    def report(self, state, offscreen=()):
        """Dead ends of the page in `state`, as text; empty when there are none:
        no focus at all, controls shown but out of reach, controls with no way back to the top,
        lists of loaded items whose OK does nothing (noop only), lists without an onclick
        (Kodi then runs the item's own path) and OK that sends the focus nowhere."""
        problems = []
        start = self.start(state)
        if start is None:
            return ['nothing takes the focus when the page opens']
        edges = self.graph(state)
        shown = {cid for cid, c in self.controls.items()
                 if cid not in offscreen and c.get('type') != 'group' and c.get('type') != 'grouplist'
                 and self.can_focus(c, state) and not self.faded(c, state)}
        for cid in sorted(shown - set(edges), key=int):
            problems.append('{} shows but the remote cannot reach it'.format(cid))
        back = {cid for cid, moves in edges.items()
                if any(any(LEAVE.match(b) for b in ran) for _, ran in moves.values())}
        for cid in sorted(edges, key=int):
            if not self._reaches(edges, cid, {start} | back):
                problems.append('{}: no way back to the top'.format(cid))
        for cid in sorted(edges, key=int):
            c = self.controls[cid]
            if c.get('type') not in LISTS or state.containers.get(cid, 'items') != 'items':
                continue
            if c.find('content') is None:
                continue  # Kodi fills it and handles the click (cast list 50)
            done = [b for b in self.clicks(cid, state) if b.lower() != 'noop']
            if not self.actions(c, 'onclick'):
                problems.append('{}: no onclick, OK runs the item path'.format(cid))
            elif not done:
                problems.append('{}: OK does nothing'.format(cid))
        # GUI_MSG_SETFOCUS takes the focus from the control first: a target that cannot take it
        # leaves the page without focus, and the next key only puts it back on the default
        for cid in sorted(edges, key=int):
            for text in self.clicks(cid, state):
                m = SETFOCUS.match(text)
                if m and m.group(1) in self.controls and not self.first_focusable(m.group(1), state):
                    problems.append('{}: OK moves the focus to {}, which cannot take it'.format(cid, m.group(1)))
        return problems

    @staticmethod
    def _reaches(edges, cid, goals):
        seen, queue = set(), [cid]
        while queue:
            c = queue.pop()
            if c in goals:
                return True
            if c in seen:
                continue
            seen.add(c)
            queue.extend(t for t, _ in edges.get(c, {}).values() if t)
        return False
