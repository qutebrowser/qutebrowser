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

"""Utilities to show various version informations."""

import sys
import glob
import os.path
import platform
import subprocess

from PyQt5.QtCore import QT_VERSION_STR, PYQT_VERSION_STR, qVersion
from PyQt5.QtWebKit import qWebKitVersion

import qutebrowser


def _git_str():
    """Try to find out git version.

    Return:
        string containing the git commit ID.
        None if there was an error or we're not in a git repo.

    """
    if hasattr(sys, "frozen"):
        return None
    try:
        gitpath = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                               os.path.pardir, os.path.pardir)
    except NameError:
        return None
    if not os.path.isdir(os.path.join(gitpath, ".git")):
        return None
    try:
        return subprocess.check_output(
            ['git', 'describe', '--tags', '--dirty', '--always'],
            cwd=gitpath).decode('UTF-8').strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _release_info():
    """Try to gather distribution release informations.

    Return:
        list of (filename, content) tuples.
    """
    data = []
    for fn in glob.glob("/etc/*-release"):
        try:
            with open(fn, 'r') as f:
                data.append((fn, ''.join(f.readlines())))
        except IOError:
            pass
    return data

def version():
    """Return a string with various version informations."""
    releaseinfo = None
    if sys.platform == 'linux':
        osver = ', '.join([e for e in platform.dist() if e])
        releaseinfo = _release_info()
    elif sys.platform == 'win32':
        osver = ', '.join(platform.win32_ver())
    elif sys.platform == 'darwin':
        osver = ', '.join(platform.mac_ver())
    else:
        osver = '?'

    gitver = _git_str()

    lines = [
        'qutebrowser v{}'.format(qutebrowser.__version__),
        '',
        '{} {}'.format(platform.python_implementation(),
                       platform.python_version()),
        'Qt {}, runtime {}'.format(QT_VERSION_STR, qVersion()),
        'PyQt {}'.format(PYQT_VERSION_STR),
    ]

    try:
        import sipconfig  # pylint: disable=import-error
    except ImportError:
        pass
    else:
        lines.append('SIP {}'.format(
            sipconfig.Configuration().sip_version_str))

    lines += [
        'Webkit {}'.format(qWebKitVersion()),
        '',
        'Platform: {}, {}'.format(platform.platform(),
                                  platform.architecture()[0]),
        'OS Version: {}'.format(osver),
    ]

    if releaseinfo is not None:
        for (fn, data) in releaseinfo:
            lines += ['', '--- {} ---'.format(fn), data]
        lines.append('')

    if gitver is not None:
        lines.append('Git commit: {}'.format(gitver))

    return '\n'.join(lines)
