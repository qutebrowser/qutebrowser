""" Run different codecheckers over a codebase.

Runs flake8, pylint and a CRLF/whitespace/conflict-checker by default.
"""

# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import sys
import subprocess
import os
import os.path
from collections import OrderedDict

from pkg_resources import load_entry_point, DistributionNotFound

status = OrderedDict()

options = {
    'target': 'qutebrowser',
    'disable': {
        'pylint': [
            # import seems unreliable
            'import-error',
            'no-name-in-module',
            # short variable names can be nice
            'invalid-name',
            # Basically unavoidable with Qt
            'too-many-public-methods',
            'no-self-use',
            # These don't even exist in python3
            'super-on-old-class',
            'old-style-class',
            # False-positives
            'abstract-class-little-used',
            # map/filter can be nicer than comprehensions
            'bad-builtin',
            # I disagree with these
            'star-args',
            'fixme',
            'too-many-arguments',
            'too-many-locals',
            'global-statement',
            'no-init',
        ],
        'flake8': [
            'E241', # Multiple spaces after ,
        ],
    },
    'exclude': [ 'appdirs.py' ],
    'other': {
        'pylint': ['--output-format=colorized', '--reports=no'],
        'flake8': ['--max-complexity=10'],
    },
}

def run(name, args=None):
    """ Run a checker with optional args.

    name -- Name of the checker/binary
    args -- Option list of arguments to pass
    """
    sys.argv = [name, options['target']]
    if args is not None:
        sys.argv += args
    print("====== {} ======".format(name))
    try:
        load_entry_point(name, 'console_scripts', name)()
    except SystemExit as e:
        status[name] = e
    except DistributionNotFound:
        if args is None:
            args = []
        try:
            status[name] = subprocess.call([name] + args)
        except FileNotFoundError as e:
            print('{}: {}'.format(e.__class__.__name__, e))
            status[name] = None
    except Exception as e:
        print('{}: {}'.format(e.__class__.__name__, e))
        status[name] = None
    print()

def check_line():
    """Checks a filetree for CRLFs, conflict markers and weird whitespace"""
    print("====== line ======")
    ret = []
    try:
        for (dirpath, dirnames, filenames) in os.walk(options['target']):
            for name in [e for e in filenames if e.endswith('.py')]:
                fn = os.path.join(dirpath, name)
                ret.append(_check_line(fn))
        status['line'] = all(ret)
    except Exception as e:
        print('{}: {}'.format(e.__class__.__name__, e))
        status['line'] = None
    print()

def _check_line(fn):
    with open(fn, 'rb') as f:
        for line in f:
            if b'\r\n' in line:
                print('Found CRLF in {}'.format(fn))
                return False
            elif any([line.decode('UTF-8').startswith(c * 7) for c in "<>=|"]):
                print('Found conflict marker in {}'.format(fn))
                return False
            elif any([line.decode('UTF-8').rstrip('\r\n').endswith(c)
                      for c in " \t"]):
                print('Found whitespace at line ending in {}'.format(fn))
                return False
            elif b' \t' in line or b'\t ' in line:
                print('Found tab-space mix in {}'.format(fn))
                return False
    return True

args = []
if options['disable']['pylint']:
    args += ['--disable=' + ','.join(options['disable']['pylint'])]
if options['exclude']:
    args += ['--ignore=' + ','.join(options['exclude'])]
if options['other']['pylint']:
    args += options['other']['pylint']
run('pylint', args)

# FIXME what the hell is the flake8 exit status?
args = []
if options['disable']['flake8']:
    args += ['--ignore=' + ','.join(options['disable']['flake8'])]
if options['exclude']:
    args += ['--exclude=' + ','.join(options['exclude'])]
if options['other']['flake8']:
    args += options['other']['flake8']
run('flake8', args)

check_line()

print('Exit status values:')
for (k, v) in status.items():
    print('  {} - {}'.format(k, v))

if all([val in [True, 0] for val in status]):
    sys.exit(0)
else:
    sys.exit(1)
