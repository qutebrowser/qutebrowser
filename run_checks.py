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

run('pylint', ['--ignore=appdirs.py', '--output-format=colorized',
               '--reports=no'])
run('flake8', ['--max-complexity=10', '--exclude=appdirs.py'])

print('Exit status values:')
for (k, v) in status.items():
    print('  {} - {}'.format(k, v))
