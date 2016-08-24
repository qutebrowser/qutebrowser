#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


def _get_files(only_py=False):
    """Iterate over all python files and yield filenames."""
    for (dirpath, _dirnames, filenames) in os.walk('.'):
        parts = dirpath.split(os.sep)
        if len(parts) >= 2:
            rootdir = parts[1]
            if rootdir.startswith('.') or rootdir == 'htmlcov':
                # ignore hidden dirs and htmlcov
                continue

        if only_py:
            endings = {'.py'}
        else:
            endings = {'.py', '.asciidoc', '.js', '.feature'}
        files = (e for e in filenames if os.path.splitext(e)[1] in endings)
        for name in files:
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
             '[Oo]ccur[^rs .]', '[Ss]eperator', '[Ee]xplicitely',
             '[Aa]uxillary', '[Aa]ccidentaly', '[Aa]mbigious', '[Ll]oosly',
             '[Ii]nitialis', '[Cc]onvienence', '[Ss]imiliar', '[Uu]ncommited',
             '[Rr]eproducable', '[Aa]n [Uu]ser', '[Cc]onvienience',
             '[Ww]ether', '[Pp]rogramatically', '[Ss]plitted', '[Ee]xitted',
             '[Mm]ininum', '[Rr]esett?ed', '[Rr]ecieved', '[Rr]egularily',
             '[Uu]nderlaying', '[Ii]nexistant', '[Ee]lipsis', 'commiting',
             'existant', '[Rr]esetted'}

    # Words which look better when splitted, but might need some fine tuning.
    words |= {'[Ww]ebelements', '[Mm]ouseevent', '[Kk]eysequence',
              '[Nn]ormalmode', '[Ee]ventloops', '[Ss]izehint',
              '[Ss]tatemachine', '[Mm]etaobject', '[Ll]ogrecord',
              '[Ff]iletype'}

    # Files which should be ignored, e.g. because they come from another
    # package
    ignored = [
        os.path.join('.', 'scripts', 'dev', 'misc_checks.py'),
        os.path.join('.', 'qutebrowser', '3rdparty', 'pdfjs'),
    ]

    seen = collections.defaultdict(list)
    try:
        ok = True
        for fn in _get_files():
            with tokenize.open(fn) as f:
                if any(fn.startswith(i) for i in ignored):
                    continue
                for line in f:
                    for w in words:
                        if (re.search(w, line) and
                                fn not in seen[w] and
                                '# pragma: no spellcheck' not in line):
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
        for fn in _get_files(only_py=True):
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
