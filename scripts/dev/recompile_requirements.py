#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Script to regenerate requirements files in misc/requirements."""

import re
import sys
import os.path
import glob
import subprocess
import tempfile
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                                os.pardir))

from scripts import utils

REPO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        '..', '..')  # /scripts/dev -> /scripts -> /
REQ_DIR = os.path.join(REPO_DIR, 'misc', 'requirements')

# PyQt versions which need SIP v4
OLD_PYQT = {'pyqt-5.7', 'pyqt-5.9', 'pyqt-5.10', 'pyqt-5.11'}


def convert_line(line, comments):
    """Convert the given requirement line to place into the output."""
    for pattern, repl in comments['replace'].items():
        line = re.sub(pattern, repl, line)

    pkgname = line.split('=')[0]

    if pkgname in comments['ignore']:
        line = '# ' + line

    try:
        line += '  # ' + comments['comment'][pkgname]
    except KeyError:
        pass

    try:
        line += '  # rq.filter: {}'.format(comments['filter'][pkgname])
    except KeyError:
        pass

    try:
        line += ' ; {}'.format(comments['markers'][pkgname])
    except KeyError:
        pass

    return line


def read_comments(fobj):
    """Find special comments in the config.

    Args:
        fobj: A file object for the config.

    Return:
        A dict with the parsed comment data.
    """
    comments = {
        'filter': {},
        'markers': {},
        'comment': {},
        'ignore': [],
        'add': [],
        'replace': {},
        'pre': False,
    }
    for line in fobj:
        if line.startswith('#@'):
            if ':' in line:
                command, args = line[2:].split(':', maxsplit=1)
                command = command.strip()
                args = args.strip()
            else:
                command = line[2:].strip()
                args = None

            if command == 'filter':
                pkg, filt = args.split(' ', maxsplit=1)
                comments['filter'][pkg] = filt
            elif command == 'comment':
                pkg, comment = args.split(' ', maxsplit=1)
                comments['comment'][pkg] = comment
            elif command == 'ignore':
                comments['ignore'] += args.split(', ')
            elif command == 'replace':
                pattern, replacement = args.split(' ', maxsplit=1)
                comments['replace'][pattern] = replacement
            elif command == 'markers':
                pkg, markers = args.split(' ', maxsplit=1)
                comments['markers'][pkg] = markers
            elif command == 'add':
                comments['add'].append(args)
            elif command == 'pre':
                comments['pre'] = True
    return comments


def get_all_names():
    """Get all requirement names based on filenames."""
    for filename in glob.glob(os.path.join(REQ_DIR, 'requirements-*.txt-raw')):
        basename = os.path.basename(filename)
        yield basename[len('requirements-'):-len('.txt-raw')]


def filter_names(names, old_pyqt=False):
    """Filter requirement names."""
    if old_pyqt:
        return sorted(names)
    else:
        return sorted(set(names) - OLD_PYQT)


def run_pip(venv_dir, *args, **kwargs):
    """Run pip inside the virtualenv."""
    venv_python = os.path.join(venv_dir, 'bin', 'python')
    return subprocess.run([venv_python, '-m', 'pip'] + list(args),
                          check=True, **kwargs)


def init_venv(host_python, venv_dir, requirements, pre=False):
    """Initialize a new virtualenv and install the given packages."""
    subprocess.run([host_python, '-m', 'venv', venv_dir], check=True)

    run_pip(venv_dir, 'install', '-U', 'pip')
    run_pip(venv_dir, 'install', '-U', 'setuptools', 'wheel')

    install_command = ['install', '-r', requirements]
    if pre:
        install_command.append('--pre')
    run_pip(venv_dir, *install_command)
    run_pip(venv_dir, 'check')


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--old-pyqt',
                        action='store_true',
                        help='Also include old PyQt requirements.')
    parser.add_argument('names', nargs='*')
    return parser.parse_args()


def print_changed_files():
    changed = set()
    proc = subprocess.run(['git', '--no-pager', 'diff', '--name-only'],
                          stdout=subprocess.PIPE, encoding='utf-8', check=True)
    lines = proc.stdout.splitlines()
    for line in lines:
        line = line.strip()
        if not (line.startswith('misc/requirements/') or
                line == 'requirements.txt'):
            continue
        line = line.replace('misc/requirements/requirements-', '')
        line = line.replace('.txt', '')
        changed.add(line)

    utils.print_title('Changed files')
    text = '\n'.join('- ' + line for line in sorted(changed))
    print(text)

    if 'CI' in os.environ:
        text = '## Changed requirement files:\n\n' + text
        print()
        print('::set-output name=changed::' + text.replace('\n', '%0A'))


def main():
    """Re-compile the given (or all) requirement files."""
    args = parse_args()
    if args.names:
        names = args.names
    else:
        names = filter_names(get_all_names(), old_pyqt=args.old_pyqt)

    utils.print_col('Rebuilding requirements: ' + ', '.join(names), 'green')
    for name in names:
        utils.print_title(name)
        filename = os.path.join(REQ_DIR,
                                'requirements-{}.txt-raw'.format(name))
        if name == 'qutebrowser':
            outfile = os.path.join(REPO_DIR, 'requirements.txt')
        else:
            outfile = os.path.join(REQ_DIR, 'requirements-{}.txt'.format(name))

        # Old PyQt versions need sip v4 which doesn't work on Python 3.8
        # pylint installs typed_ast on < 3.8 only
        if name in OLD_PYQT or name == 'pylint':
            host_python = 'python3.7'
        else:
            host_python = sys.executable

        utils.print_subtitle("Building")

        with open(filename, 'r', encoding='utf-8') as f:
            comments = read_comments(f)

        with tempfile.TemporaryDirectory() as tmpdir:
            init_venv(host_python=host_python,
                      venv_dir=tmpdir,
                      requirements=filename,
                      pre=comments['pre'])
            proc = run_pip(tmpdir, 'freeze', stdout=subprocess.PIPE)
            reqs = proc.stdout.decode('utf-8')

        with open(outfile, 'w', encoding='utf-8') as f:
            f.write("# This file is automatically generated by "
                    "scripts/dev/recompile_requirements.py\n\n")
            for line in reqs.splitlines():
                if line.startswith('qutebrowser=='):
                    continue
                f.write(convert_line(line, comments) + '\n')

            for line in comments['add']:
                f.write(line + '\n')

        # Test resulting file
        utils.print_subtitle("Testing")
        with tempfile.TemporaryDirectory() as tmpdir:
            init_venv(host_python, tmpdir, outfile)

    print_changed_files()


if __name__ == '__main__':
    main()
