# Where Confuse behaves differently from Nightcity

tests/static/test_fingerprint.py compares what every window does in both skins (actions, focus
and visible/enable conditions, not looks), once with no skin setting set and once for each skin
setting the include conditions of the window ask for. A difference is allowed only when it is
listed here, with a reason.

Format: one `## Window.xml` heading per window, below it one line per difference:

    - `<line of the diff, with its leading + or ->`: why Confuse differs

The reason after the colon is required. A window that skins/confuse/1080i replaces as a whole
must be listed too.

## Startup.xml

- `-label | 0 | when visible: true`: the status line and its blinking cursor belong to the terminal look of Nightcity; the spark on the fuse shows the wait here
