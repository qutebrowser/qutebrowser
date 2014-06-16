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


"""Data used by setup.py and scripts/freeze.py."""

import sys
import re
import ast
import os
import os.path
import subprocess
sys.path.insert(0, os.getcwd())


BASEDIR = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                       os.path.pardir)


def read_file(name):
    """Get the string contained in the file named name."""
    with open(name, encoding='utf-8') as f:
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
    value = str(ast.literal_eval(line))
    return value


def _git_str():
    """Try to find out git version.

    Return:
        string containing the git commit ID.
        None if there was an error or we're not in a git repo.
    """
    if BASEDIR is None:
        return None
    if not os.path.isdir(os.path.join(BASEDIR, ".git")):
        return None
    try:
        return subprocess.check_output(
            ['git', 'describe', '--tags', '--dirty', '--always'],
            cwd=BASEDIR).decode('UTF-8').strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def write_git_file():
    """Write the git-commit-id file with the current commit."""
    gitstr = _git_str()
    if gitstr is None:
        gitstr = ''
    with open(os.path.join(BASEDIR, 'qutebrowser', 'git-commit-id'), 'w') as f:
        f.write(gitstr)


setupdata = {
    'name': 'qutebrowser',
    'version': '.'.join(map(str, _get_constant('version_info'))),
    'description': ("A keyboard-driven, vim-like browser based on PyQt5 and "
                    "QtWebKit."),
    'long_description': read_file('README'),
    'url': 'http://www.qutebrowser.org/',
    'author': _get_constant('author'),
    'author_email': _get_constant('email'),
    'license': _get_constant('license'),
    'extras_require': {'nice-debugging': ['colorlog', 'colorama', 'ipdb']},
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
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Internet',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Browsers',
    ],
    'keywords': 'pyqt browser web qt webkit',
}
