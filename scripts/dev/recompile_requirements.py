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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                                os.pardir))

from scripts import utils

REPO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        '..', '..')  # /scripts/dev -> /scripts -> /
REQ_DIR = os.path.join(REPO_DIR, 'misc', 'requirements')


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


def init_venv(host_python, venv_dir, requirements, pre=False):
    """Initialize a new virtualenv and install the given packages."""
    subprocess.run([host_python, '-m', 'venv', venv_dir], check=True)

    venv_python = os.path.join(venv_dir, 'bin', 'python')
    subprocess.run([venv_python, '-m', 'pip',
                    'install', '-U', 'pip'], check=True)

    install_command = [venv_python, '-m', 'pip', 'install', '-r', requirements]
    if pre:
        install_command.append('--pre')
    subprocess.run(install_command, check=True)
    subprocess.run([venv_python, '-m', 'pip', 'check'], check=True)
    return venv_python


def main():
    """Re-compile the given (or all) requirement files."""
    names = sys.argv[1:] if len(sys.argv) > 1 else sorted(get_all_names())

    for name in names:
        utils.print_title(name)
        filename = os.path.join(REQ_DIR,
                                'requirements-{}.txt-raw'.format(name))
        if name == 'qutebrowser':
            outfile = os.path.join(REPO_DIR, 'requirements.txt')
        else:
            outfile = os.path.join(REQ_DIR, 'requirements-{}.txt'.format(name))

        if name in [
                # Need sip v4 which doesn't work on Python 3.8
                'pyqt-5.7', 'pyqt-5.9', 'pyqt-5.10', 'pyqt-5.11', 'pyqt-5.12',
                # Installs typed_ast on < 3.8 only
                'pylint',
        ]:
            host_python = 'python3.7'
        else:
            host_python = sys.executable

        utils.print_subtitle("Building")

        with open(filename, 'r', encoding='utf-8') as f:
            comments = read_comments(f)

        with tempfile.TemporaryDirectory() as tmpdir:
            venv_python = init_venv(host_python=host_python,
                                    venv_dir=tmpdir,
                                    requirements=filename,
                                    pre=comments['pre'])
            proc = subprocess.run([venv_python, '-m', 'pip', 'freeze'],
                                  check=True, stdout=subprocess.PIPE)
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


if __name__ == '__main__':
    main()
