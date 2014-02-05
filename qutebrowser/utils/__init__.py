"""Utility functions"""

import re
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
    if not (re.match(r'^\w+://', url) or url.startswith('about:')):
        logging.debug("adding http:// to {}".format(url))
        url = 'http://' + url
    qurl = QUrl(url)
    logging.debug('Converting {} to qurl -> {}'.format(url, qurl.url()))
    return qurl


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
