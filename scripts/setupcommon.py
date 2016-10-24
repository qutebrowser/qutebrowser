# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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


"""Data used by setup.py and scripts/freeze.py."""

import sys
import re
import ast
import os
import os.path
import subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))


if sys.hexversion >= 0x03000000:
    _open = open
else:
    import codecs
    _open = codecs.open


BASEDIR = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                       os.path.pardir)


def read_file(name):
    """Get the string contained in the file named name."""
    with _open(name, 'r', encoding='utf-8') as f:
        return f.read()


def _get_constant(name):
    """Read a __magic__ constant from qutebrowser/__init__.py.

    We don't import qutebrowser here because it can go wrong for multiple
    reasons. Instead we use re/ast to get the value directly from the source
    file.

    Args:
        name: The name of the argument to get.

    Return:
        The value of the argument.
    """
    field_re = re.compile(r'__{}__\s+=\s+(.*)'.format(re.escape(name)))
    path = os.path.join(BASEDIR, 'qutebrowser', '__init__.py')
    line = field_re.search(read_file(path)).group(1)
    value = ast.literal_eval(line)
    return value


def _git_str():
    """Try to find out git version.

    Return:
        string containing the git commit ID and timestamp.
        None if there was an error or we're not in a git repo.
    """
    if BASEDIR is None:
        return None
    if not os.path.isdir(os.path.join(BASEDIR, ".git")):
        return None
    try:
        cid = subprocess.check_output(
            ['git', 'describe', '--tags', '--dirty', '--always'],
            cwd=BASEDIR).decode('UTF-8').strip()
        date = subprocess.check_output(
            ['git', 'show', '-s', '--format=%ci', 'HEAD'],
            cwd=BASEDIR).decode('UTF-8').strip()
        return '{} ({})'.format(cid, date)
    except (subprocess.CalledProcessError, OSError):
        return None


def write_git_file():
    """Write the git-commit-id file with the current commit."""
    gitstr = _git_str()
    if gitstr is None:
        gitstr = ''
    path = os.path.join(BASEDIR, 'qutebrowser', 'git-commit-id')
    with _open(path, 'w', encoding='ascii') as f:
        f.write(gitstr)


setupdata = {
    'name': 'qutebrowser',
    'version': '.'.join(str(e) for e in _get_constant('version_info')),
    'description': _get_constant('description'),
    'long_description': read_file('README.asciidoc'),
    'url': 'https://www.qutebrowser.org/',
    'requires': ['pypeg2', 'jinja2', 'pygments', 'PyYAML'],
    'author': _get_constant('author'),
    'author_email': _get_constant('email'),
    'license': _get_constant('license'),
    'classifiers': [
        'Development Status :: 3 - Alpha',
        'Environment :: X11 Applications :: Qt',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License v3 or later '
            '(GPLv3+)',
        'Natural Language :: English',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: Microsoft :: Windows :: Windows XP',
        'Operating System :: Microsoft :: Windows :: Windows 7',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Internet',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Browsers',
    ],
    'keywords': 'pyqt browser web qt webkit',
}
