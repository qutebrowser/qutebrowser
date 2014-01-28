import sys
import subprocess
from pkg_resources import load_entry_point, DistributionNotFound

status = {}

def run(name, args=None):
    sys.argv = [name, 'qutebrowser']
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
            print('exc {}'.format([name, 'qutebrowser'] + args))
            status[name] = subprocess.call([name] + args)
        except FileNotFoundError as e:
            print('{}: {}'.format(e.__class__.__name__, e))
            status[name] = None
    except Exception as e:
        print('{}: {}'.format(e.__class__.__name__, e))
        status[name] = None
    print()

pylint_disable = [
    'import-error', 'no-name-in-module', # import seems unreliable
    'invalid-name',                      # short variable names can be nice
    'star-args',                         # we want to use this
    'fixme',                             # I'll decide myself when to fix them
]

run('pylint', ['--ignore=appdirs.py', '--output-format=colorized',
               '--reports=no', '--disable=' + ','.join(pylint_disable)])
run('flake8', ['--max-complexity=10', '--exclude=appdirs.py'])

print('Exit status values:')
for (k, v) in status.items():
    print('  {} - {}'.format(k, v))
