#!/usr/bin/env python3
"""The e2e suite in two rounds: python tools/e2e.py [-n N] [PYTEST ARGS ...]

Round one runs the suite on the kodi-dev pool (KDEV_POOL, default 1) with N workers (default
auto: every worker whose Kodi answers). What fails there runs again on its own: one worker, one
test after the other, no load from the others. A test that passes then failed under load (a
flake), one that fails again is a failure. Both are named in the report, flakes too: they are
the tests to make sturdy, not to forget.

Every run adds a line to _build/e2e/history.jsonl (time, length, counts, flakes, failures, Kodi
crashes); the report ends with the tests that flaked most often there. Exit status 0 when nothing failed
twice. PYTEST ARGS narrow the run (files, -k, -m ...); without them it is the whole suite.
"""
import argparse
import collections
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / '_build' / 'e2e'
HISTORY = OUT / 'history.jsonl'
# more failures than this in round one: something is broken for all, not a flake to sort out
RERUN_MAX = 25


CRASHES = re.compile(r'Kodi crashes in this run: (\d+)')


def pytest(args, junit):
    """Run pytest, its output through; the number of Kodi crashes it reported."""
    command = [sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '-rfEs',
               '--junitxml', str(junit), *args]
    env = dict(os.environ, KDEV_POOL=os.environ.get('KDEV_POOL', '1'))
    print('$ ' + ' '.join(command), flush=True)
    crashes = 0
    with subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True) as run:
        for line in run.stdout:
            sys.stdout.write(line)
            found = CRASHES.search(line)
            if found:
                crashes += int(found.group(1))
    return crashes


def results(junit):
    """{nodeid: 'passed' | 'failed' | 'skipped'} of a JUnit XML file; an error counts as failed."""
    found = {}
    if not junit.is_file():
        return found
    for case in ET.parse(junit).iter('testcase'):
        module = case.get('classname', '').replace('.', '/')
        nodeid = '{}.py::{}'.format(module, case.get('name'))
        if case.find('failure') is not None or case.find('error') is not None:
            found[nodeid] = 'failed'
        elif case.find('skipped') is not None:
            found.setdefault(nodeid, 'skipped')
        else:
            found.setdefault(nodeid, 'passed')
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('-n', dest='workers', default='auto')
    options, rest = parser.parse_known_args()
    selection = rest or ['tests/e2e']
    OUT.mkdir(parents=True, exist_ok=True)
    start = time.time()

    first = OUT / 'round1.xml'
    first.unlink(missing_ok=True)
    crashes = pytest([*selection, '-m', 'e2e', '-n', options.workers, '--dist', 'loadfile'], first)
    round1 = results(first)
    failed = sorted(t for t, outcome in round1.items() if outcome == 'failed')

    round2 = {}
    if failed and len(failed) <= RERUN_MAX:
        print('\n{} failed: each again on its own'.format(len(failed)), flush=True)
        second = OUT / 'round2.xml'
        second.unlink(missing_ok=True)
        crashes += pytest([*failed, '-m', 'e2e', '-n', '1'], second)
        round2 = results(second)

    flaky = [t for t in failed if round2.get(t) == 'passed']
    broken = [t for t in failed if round2.get(t) != 'passed']
    counts = collections.Counter(round1.values())
    record = {'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'seconds': round(time.time() - start),
              'workers': options.workers, 'selection': selection, 'passed': counts['passed'],
              'skipped': counts['skipped'], 'flaky': flaky, 'failed': broken, 'kodi_crashes': crashes}
    with open(HISTORY, 'a') as handle:
        handle.write(json.dumps(record) + '\n')

    print('\n==== e2e: {} passed, {} skipped, {} flaky, {} failed, {} Kodi crashes in {} s'.format(
        counts['passed'], counts['skipped'], len(flaky), len(broken), crashes, record['seconds']))
    for test in flaky:
        print('  flaky (failed under load, passed on its own): ' + test)
    for test in broken:
        print('  FAILED (also on its own): ' + test)
    if failed and len(failed) > RERUN_MAX:
        print('  {} failed in round one: not run again, look at the run'.format(len(failed)))
    often = collections.Counter()
    runs = 0
    for line in HISTORY.read_text().splitlines():
        runs += 1
        often.update(json.loads(line).get('flaky', []))
    if often:
        print('flaky most often in {} runs of {}:'.format(runs, HISTORY.relative_to(ROOT)))
        for test, times in often.most_common(5):
            print('  {}x {}'.format(times, test))
    return 1 if broken or len(failed) > RERUN_MAX else 0


if __name__ == '__main__':
    sys.exit(main())
