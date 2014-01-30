""" Run different codecheckers over a codebase.

Runs flake8, pylint and a CRLF-checker by default.
"""

import sys
import subprocess
import os
import os.path
from collections import OrderedDict

from pkg_resources import load_entry_point, DistributionNotFound

status = OrderedDict()
testmodule = 'qutebrowser'

def run(name, args=None):
    """ Run a checker with optional args.

    name -- Name of the checker/binary
    args -- Option list of arguments to pass
    """
    sys.argv = [name, testmodule]
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

def check_crlf():
    """Checks a filetree for CRLFs"""
    print("====== CRLF ======")
    ret = []
    try:
        for (dirpath, dirnames, filenames) in os.walk(testmodule):
            for name in [e for e in filenames if e.endswith('.py')]:
                fn = os.path.join(dirpath, name)
                ret.append(_check_crlf(fn))
        status['crlf'] = all(ret)
    except Exception as e:
        print('{}: {}'.format(e.__class__.__name__, e))
        status['crlf'] = None
    print()

def _check_crlf(fn):
    with open(fn, 'rb') as f:
        for line in f:
            if b'\r\n' in line:
                print('Found CRLF in {}'.format(fn))
                return False
    return True


pylint_disable = [
    'import-error',               # import seems unreliable
    'no-name-in-module',
    'invalid-name',               # short variable names can be nice
    'star-args',                  # we want to use this
    'fixme',
    'too-many-public-methods',    # Basically unavoidable with Qt
    'no-self-use',
    'super-on-old-class',         # These don't even exist in python3
    'old-style-class',
    'global-statement',
    'abstract-class-little-used', # False-positives
    'bad-builtin',                # map/filter can be nicer than comprehensions
    'too-many-arguments',
]

flake8_disable = [
    'E241', # Multiple spaces after ,
]

run('pylint', ['--ignore=appdirs.py', '--output-format=colorized',
               '--reports=no', '--disable=' + ','.join(pylint_disable)])
# FIXME what the hell is the flake8 exit status?
run('flake8', ['--max-complexity=10', '--exclude=appdirs.py',
               '--ignore=' + ''.join(flake8_disable)])
check_crlf()

print('Exit status values:')
for (k, v) in status.items():
    print('  {} - {}'.format(k, v))

if all([val in [True, 0] for val in status]):
    sys.exit(0)
else:
    sys.exit(1)
