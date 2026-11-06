# Where Confuse behaves differently from Nightcity

tests/static/test_fingerprint.py compares what every window does in both skins (actions, focus
and visible/enable conditions, not looks). A difference is allowed only when it is listed here.

Format: one `## Window.xml` heading per window, below it one line per difference:

    - `<line of the diff, with its leading + or ->`: why Confuse differs

A window that skins/confuse/1080i replaces as a whole must be listed too. No difference is listed yet.
