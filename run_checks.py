""" Run different codecheckers over a codebase.

Runs flake8, pylint, pep257 and a CRLF/whitespace/conflict-checker by default.
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

try:
    import pep257
except ImportError:
    do_check_257 = False
else:
    do_check_257 = True
from pkg_resources import load_entry_point, DistributionNotFound

status = OrderedDict()

options = {
    'target': 'qutebrowser',
    'disable': {
        'pep257': [
            'D102',  # Docstring missing, will be handled by others
            'D209',  # Blank line before closing """ (removed from PEP257)
        ],
    },
    'exclude': ['appdirs.py'],
    'other': {
        'pylint': ['--output-format=colorized', '--reports=no',
                   '--rcfile=.pylintrc'],
        'flake8': ['--max-complexity=10', '--config=.flake8'],
    },
}


def run(name, args=None):
    """ Run a checker via distutils with optional args.

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


def check_pep257(args=None):
    sys.argv = ['pep257', options['target']]
    if args is not None:
        sys.argv += args
    print("====== pep257 ======")
    try:
        status['pep257'] = pep257.main(*pep257.parse_options())
    except Exception as e:
        print('{}: {}'.format(e.__class__.__name__, e))
        status['pep257'] = None
    print()


def check_line():
    """Checks a filetree for CRLFs, conflict markers and weird whitespace"""
    print("====== line ======")
    ret = []
    try:
        for (dirpath, dirnames, filenames) in os.walk(options['target']):
            for name in (e for e in filenames if e.endswith('.py')):
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
            elif any(line.decode('UTF-8').startswith(c * 7) for c in "<>=|"):
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


def _get_args(checker):
    args = []
    if checker == 'pylint':
        try:
            args += ['--disable=' + ','.join(options['disable']['pylint'])]
        except KeyError:
            pass
        try:
            args += ['--ignore=' + ','.join(options['exclude'])]
        except KeyError:
            pass
        try:
            args += options['other']['pylint']
        except KeyError:
            pass
    elif checker == 'flake8':
        try:
            args += ['--ignore=' + ','.join(options['disable']['flake8'])]
        except KeyError:
            pass
        try:
            args += ['--exclude=' + ','.join(options['exclude'])]
        except KeyError:
            pass
        try:
            args += options['other']['flake8']
        except KeyError:
            pass
    elif checker == 'pep257':
        args = []
        try:
            args += ['--ignore=' + ','.join(options['disable']['pep257'])]
        except KeyError:
            pass
        try:
            args += ['--match=(?!{}).*\.py'.format('|'.join(
                options['exclude']))]
        except KeyError:
            pass
        try:
            args += options['other']['pep257']
        except KeyError:
            pass
    return args

if do_check_257:
    check_pep257(_get_args('pep257'))
for checker in ['pylint', 'flake8']:
    # FIXME what the hell is the flake8 exit status?
    run(checker, _get_args(checker))
check_line()

print('Exit status values:')
for (k, v) in status.items():
    print('  {} - {}'.format(k, v))

if all(val in [True, 0] for val in status):
    sys.exit(0)
else:
    sys.exit(1)
