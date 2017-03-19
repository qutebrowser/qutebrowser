#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

    return line


def get_requirements(requirements_file, exclude=()):
    """Get the requirements after freezing with the given file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pip_bin = os.path.join(tmpdir, 'bin', 'pip')
        subprocess.check_call(['virtualenv', tmpdir])
        if requirements_file is not None:
            subprocess.check_call([pip_bin, 'install', '-r',
                                   requirements_file])
        out = subprocess.check_output([pip_bin, 'freeze', '--all'],
                                      universal_newlines=True)

    return [line for line in out.splitlines() if line not in exclude]


def read_comments(fobj):
    """Find special comments in the config.

    Args:
        fobj: A file object for the config.

    Return:
        A dict with the parsed comment data.
    """
    comments = {
        'filter': {},
        'comment': {},
        'ignore': [],
        'replace': {},
    }
    for line in fobj:
        if line.startswith('#@'):
            command, args = line[2:].split(':', maxsplit=1)
            command = command.strip()
            args = args.strip()
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
    return comments


def get_all_names():
    """Get all requirement names based on filenames."""
    for filename in glob.glob(os.path.join(REQ_DIR, 'requirements-*.txt-raw')):
        basename = os.path.basename(filename)
        name = basename[len('requirements-'):-len('.txt-raw')]
        if name == 'cxfreeze' and sys.hexversion >= 0x030600:
            print("Warning: Skipping cxfreeze")
        else:
            yield name
    yield 'pip'


def main():
    """Re-compile the given (or all) requirement files."""
    names = sys.argv[1:] if len(sys.argv) > 1 else sorted(get_all_names())

    utils.print_title('pip')
    pip_requirements = get_requirements(None)

    for name in names:
        utils.print_title(name)

        if name == 'qutebrowser':
            outfile = os.path.join(REPO_DIR, 'requirements.txt')
        else:
            outfile = os.path.join(REQ_DIR, 'requirements-{}.txt'.format(name))

        if name == 'pip':
            requirements = [req for req in pip_requirements
                            if not req.startswith('pip==')]
            comments = {
                'filter': {},
                'comment': {},
                'ignore': [],
                'replace': {},
            }
        else:
            filename = os.path.join(REQ_DIR,
                                    'requirements-{}.txt-raw'.format(name))
            requirements = get_requirements(filename, exclude=pip_requirements)

            with open(filename, 'r', encoding='utf-8') as f:
                comments = read_comments(f)

        with open(outfile, 'w', encoding='utf-8') as f:
            f.write("# This file is automatically generated by "
                    "scripts/dev/recompile_requirements.py\n\n")
            for line in requirements:
                converted = convert_line(line, comments)
                f.write(converted + '\n')


if __name__ == '__main__':
    main()
