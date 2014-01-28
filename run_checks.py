import sys
from pkg_resources import load_entry_point

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
    except Exception as e:
        print(e)
        status[name] = None
    print()

run('pylint')
run('flake8', ['--max-complexity', '10'])

print('Exit status values:')
for (k, v) in status.items():
    print('  {} - {}'.format(k, v))
