# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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


"""Data used by setup.py and the PyInstaller qutebrowser.spec."""

import sys
import os
import os.path
import subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))


if sys.hexversion >= 0x03000000:
    open_file = open
else:
    import codecs
    open_file = codecs.open


BASEDIR = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                       os.path.pardir)


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
        # https://stackoverflow.com/questions/21017300/21017394#21017394
        commit_hash = subprocess.run(
            ['git', 'describe', '--match=NeVeRmAtCh', '--always', '--dirty'],
            cwd=BASEDIR, check=True,
            stdout=subprocess.PIPE).stdout.decode('UTF-8').strip()
        date = subprocess.run(
            ['git', 'show', '-s', '--format=%ci', 'HEAD'],
            cwd=BASEDIR, check=True,
            stdout=subprocess.PIPE).stdout.decode('UTF-8').strip()
        return '{} ({})'.format(commit_hash, date)
    except (subprocess.CalledProcessError, OSError):
        return None


def write_git_file():
    """Write the git-commit-id file with the current commit."""
    gitstr = _git_str()
    if gitstr is None:
        gitstr = ''
    path = os.path.join(BASEDIR, 'qutebrowser', 'git-commit-id')
    with open_file(path, 'w', encoding='ascii') as f:
        f.write(gitstr)
