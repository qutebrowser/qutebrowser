#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import os.path
import re
import sys
import argparse
import subprocess
import tokenize
import traceback
import collections
import pathlib

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
    gitst = subprocess.run(['git', 'status', '--porcelain'], check=True,
                           stdout=subprocess.PIPE).stdout
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
    words = {'behaviour', 'quitted', 'likelyhood', 'sucessfully',
             'occur[^rs .!]', 'seperator', 'explicitely', 'auxillary',
             'accidentaly', 'ambigious', 'loosly', 'initialis', 'convienence',
             'similiar', 'uncommited', 'reproducable', 'an user',
             'convienience', 'wether', 'programatically', 'splitted',
             'exitted', 'mininum', 'resett?ed', 'recieved', 'regularily',
             'underlaying', 'inexistant', 'elipsis', 'commiting', 'existant',
             'resetted', 'similarily', 'informations', 'an url', 'treshold',
             'artefact'}

    # Words which look better when splitted, but might need some fine tuning.
    words |= {'webelements', 'mouseevent', 'keysequence', 'normalmode',
              'eventloops', 'sizehint', 'statemachine', 'metaobject',
              'logrecord', 'filetype'}

    # Files which should be ignored, e.g. because they come from another
    # package
    ignored = [
        os.path.join('.', 'scripts', 'dev', 'misc_checks.py'),
        os.path.join('.', 'qutebrowser', '3rdparty', 'pdfjs'),
        os.path.join('.', 'tests', 'end2end', 'data', 'hints', 'ace',
                     'ace.js'),
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
                        pattern = '[{}{}]{}'.format(w[0], w[0].upper(), w[1:])
                        if (re.search(pattern, line) and
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


def check_userscripts_descriptions():
    """Make sure all userscripts are described properly."""
    folder = pathlib.Path('misc/userscripts')
    readme = folder / 'README.md'

    described = set()
    for line in readme.open('r'):
        line = line.strip()
        if line == '## Others':
            break

        match = re.fullmatch(r'- \[([^]]*)\].*', line)
        if match:
            described.add(match.group(1))

    present = {path.name for path in folder.iterdir()}
    present.remove('README.md')

    missing = present - described
    additional = described - present
    ok = True

    if missing:
        print("Missing userscript descriptions: {}".format(missing))
        ok = False
    if additional:
        print("Additional userscript descriptions: {}".format(additional))
        ok = False

    return ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('checker',
                        choices=('git', 'vcs', 'spelling', 'userscripts'),
                        help="Which checker to run.")
    args = parser.parse_args()
    if args.checker == 'git':
        ok = check_git()
    elif args.checker == 'vcs':
        ok = check_vcs_conflict()
    elif args.checker == 'spelling':
        ok = check_spelling()
    elif args.checker == 'userscripts':
        ok = check_userscripts_descriptions()
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
