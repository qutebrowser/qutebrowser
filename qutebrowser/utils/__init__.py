"""Utility functions"""

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

import sys
import os.path
import platform
import logging
import subprocess

from PyQt5.QtCore import QUrl, QT_VERSION_STR, PYQT_VERSION_STR, qVersion
from PyQt5.QtWebKit import qWebKitVersion

import qutebrowser


def qurl(url):
    """Get a QUrl from an url string."""
    if isinstance(url, QUrl):
        logging.debug("url is already a qurl")
        return url
    newurl = QUrl.fromUserInput(url)
    logging.debug('Converting {} to qurl -> {}'.format(url, newurl.url()))
    return newurl


def version():
    """Return a string with various version informations."""
    if sys.platform == 'linux':
        osver = ', '.join((platform.dist()))
    elif sys.platform == 'win32':
        osver = ', '.join((platform.win32_ver()))
    elif sys.platform == 'darwin':
        osver = ', '.join((platform.mac_ver()))
    else:
        osver = '?'

    gitver = _git_str()

    lines = [
        'qutebrowser v{}\n\n'.format(qutebrowser.__version__),
        'Python {}\n'.format(platform.python_version()),
        'Qt {}, runtime {}\n'.format(QT_VERSION_STR, qVersion()),
        'PyQt {}\n'.format(PYQT_VERSION_STR),
        'Webkit {}\n\n'.format(qWebKitVersion()),
        'Platform: {}, {}\n'.format(platform.platform(),
                                    platform.architecture()[0]),
        'OS Version: {}\n'.format(osver),
    ]

    if gitver is not None:
        lines.append('\nGit commit: {}'.format(gitver))

    return ''.join(lines)


def _git_str():
    """Try to find out git version and return a string if possible.

    Return None if there was an error or we're not in a git repo.
    """
    # FIXME this runs in PWD, not the qutebrowser dir?!
    if not os.path.isdir(".git"):
        return None
    try:
        return subprocess.check_output(['git', 'describe', '--tags', '--dirty',
                                        '--always']).decode('UTF-8').strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
