#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Various small code checkers."""

import os
import re
import sys
import os.path
import argparse
import subprocess
import tokenize
import traceback
import collections

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                os.pardir))

from scripts import utils


def _py_files():
    """Iterate over all python files and yield filenames."""
    for (dirpath, _dirnames, filenames) in os.walk('.'):
        parts = dirpath.split(os.sep)
        if len(parts) >= 2 and parts[1].startswith('.'):
            # ignore hidden dirs
            continue
        for name in (e for e in filenames if e.endswith('.py')):
            yield os.path.join(dirpath, name)


def check_git():
    """Check for uncommitted git files.."""
    if not os.path.isdir(".git"):
        print("No .git dir, ignoring")
        print()
        return False
    untracked = []
    gitst = subprocess.check_output(['git', 'status', '--porcelain'])
    gitst = gitst.decode('UTF-8').strip()
    for line in gitst.splitlines():
        s, name = line.split(maxsplit=1)
        if s == '??' and name != '.venv/':
            untracked.append(name)
    status = True
    if untracked:
        status = False
        utils.print_col("Untracked files:", 'red')
        print('\n'.join(untracked))
    print()
    return status


def check_spelling():
    """Check commonly misspelled words."""
    # Words which I often misspell
    words = {'[Bb]ehaviour', '[Qq]uitted', 'Ll]ikelyhood', '[Ss]ucessfully',
             '[Oo]ccur[^r .]', '[Ss]eperator', '[Ee]xplicitely', '[Rr]esetted',
             '[Aa]uxillary', '[Aa]ccidentaly', '[Aa]mbigious', '[Ll]oosly',
             '[Ii]nitialis', '[Cc]onvienence', '[Ss]imiliar', '[Uu]ncommited',
             '[Rr]eproducable'}

    # Words which look better when splitted, but might need some fine tuning.
    words |= {'[Kk]eystrings', '[Ww]ebelements', '[Mm]ouseevent',
              '[Kk]eysequence', '[Nn]ormalmode', '[Ee]ventloops',
              '[Ss]izehint', '[Ss]tatemachine', '[Mm]etaobject',
              '[Ll]ogrecord', '[Ff]iletype'}

    seen = collections.defaultdict(list)
    try:
        ok = True
        for fn in _py_files():
            with tokenize.open(fn) as f:
                if fn == os.path.join('.', 'scripts', 'dev', 'misc_checks.py'):
                    continue
                for line in f:
                    for w in words:
                        if re.search(w, line) and fn not in seen[w]:
                            print('Found "{}" in {}!'.format(w, fn))
                            seen[w].append(fn)
                            ok = False
        print()
        return ok
    except Exception:
        traceback.print_exc()
        return None


def check_vcs_conflict():
    """Check VCS conflict markers."""
    try:
        ok = True
        for fn in _py_files():
            with tokenize.open(fn) as f:
                for line in f:
                    if any(line.startswith(c * 7) for c in '<>=|'):
                        print("Found conflict marker in {}".format(fn))
                        ok = False
        print()
        return ok
    except Exception:
        traceback.print_exc()
        return None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument('checker', choices=('git', 'vcs', 'spelling'),
                        help="Which checker to run.")
    args = parser.parse_args()
    if args.checker == 'git':
        ok = check_git()
    elif args.checker == 'vcs':
        ok = check_vcs_conflict()
    elif args.checker == 'spelling':
        ok = check_spelling()
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
