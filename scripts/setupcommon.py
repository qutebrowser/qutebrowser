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
import os
import os.path
import subprocess
sys.path.insert(0, os.getcwd())
import qutebrowser


try:
    BASEDIR = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                           os.path.pardir)
except NameError:
    BASEDIR = None


def read_file(name):
    """Get the string contained in the file named name."""
    with open(name, encoding='utf-8') as f:
        return f.read()


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
    'version': qutebrowser.__version__,
    'description': ("A keyboard-driven, vim-like browser based on PyQt5 and "
                    "QtWebKit."),
    'long_description': read_file('README'),
    'url': 'http://www.qutebrowser.org/',
    'author': qutebrowser.__author__,
    'author_email': qutebrowser.__email__,
    'license': qutebrowser.__license__,
    'extras_require': {'colorlog': ['colorlog', 'colorama']},
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
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Internet',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Browsers',
    ],
    'keywords': 'pyqt browser web qt webkit',
}
