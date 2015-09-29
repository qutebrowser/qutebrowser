# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import importlib
import collections

from PyQt5.QtCore import QT_VERSION_STR, PYQT_VERSION_STR, qVersion
from PyQt5.QtWebKit import qWebKitVersion
from PyQt5.QtNetwork import QSslSocket
from PyQt5.QtWidgets import QApplication

import qutebrowser
from qutebrowser.utils import log, utils


GPL_BOILERPLATE = """
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/> or use
:open qute:gpl.
"""


def _git_str():
    """Try to find out git version.

    Return:
        string containing the git commit ID.
        None if there was an error or we're not in a git repo.
    """
    # First try via subprocess if possible
    commit = None
    if not hasattr(sys, "frozen"):
        try:
            gitpath = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                   os.path.pardir, os.path.pardir)
        except (NameError, OSError):
            log.misc.exception("Error while getting git path")
        else:
            commit = _git_str_subprocess(gitpath)
    if commit is not None:
        return commit
    # If that fails, check the git-commit-id file.
    try:
        return utils.read_file('git-commit-id')
    except (OSError, ImportError):
        return None


def _git_str_subprocess(gitpath):
    """Try to get the git commit ID and timestamp by calling git.

    Args:
        gitpath: The path where the .git folder is.

    Return:
        The ID/timestamp on success, None on failure.
    """
    if not os.path.isdir(os.path.join(gitpath, ".git")):
        return None
    try:
        cid = subprocess.check_output(
            ['git', 'describe', '--tags', '--dirty', '--always'],
            cwd=gitpath).decode('UTF-8').strip()
        date = subprocess.check_output(
            ['git', 'show', '-s', '--format=%ci', 'HEAD'],
            cwd=gitpath).decode('UTF-8').strip()
        return '{} ({})'.format(cid, date)
    except (subprocess.CalledProcessError, OSError):
        return None


def _release_info():
    """Try to gather distribution release informations.

    Return:
        list of (filename, content) tuples.
    """
    data = []
    for fn in glob.glob("/etc/*-release"):
        try:
            with open(fn, 'r', encoding='utf-8') as f:
                data.append((fn, ''.join(f.readlines())))  # pragma: no branch
        except OSError:
            log.misc.exception("Error while reading {}.".format(fn))
    return data


def _module_versions():
    """Get versions of optional modules.

    Return:
        A list of lines with version info.
    """
    lines = []
    modules = collections.OrderedDict([
        ('sip', ['SIP_VERSION_STR']),
        ('colorlog', []),
        ('colorama', ['VERSION', '__version__']),
        ('pypeg2', ['__version__']),
        ('jinja2', ['__version__']),
        ('pygments', ['__version__']),
        ('yaml', ['__version__']),
    ])
    for name, attributes in modules.items():
        try:
            module = importlib.import_module(name)
        except ImportError:
            text = '{}: no'.format(name)
        else:
            for attr in attributes:
                try:
                    text = '{}: {}'.format(name, getattr(module, attr))
                except AttributeError:
                    pass
                else:
                    break
            else:
                text = '{}: yes'.format(name)
        lines.append(text)
    return lines


def _os_info():
    """Get operating system info.

    Return:
        A list of lines with version info.
    """
    lines = []
    releaseinfo = None
    if sys.platform == 'linux':
        osver = ''
        releaseinfo = _release_info()
    elif sys.platform == 'win32':
        osver = ', '.join(platform.win32_ver())
    elif sys.platform == 'darwin':
        # pylint: disable=unpacking-non-sequence
        # See https://bitbucket.org/logilab/pylint/issue/165/
        release, versioninfo, machine = platform.mac_ver()
        if all(not e for e in versioninfo):
            versioninfo = ''
        else:
            versioninfo = '.'.join(versioninfo)
        osver = ', '.join([e for e in (release, versioninfo, machine) if e])
    else:
        osver = '?'
    lines.append('OS Version: {}'.format(osver))
    if releaseinfo is not None:
        for (fn, data) in releaseinfo:
            lines += ['', '--- {} ---'.format(fn), data]
    return lines


def version(short=False):
    """Return a string with various version informations.

    Args:
        short: Return a shortened output.
    """
    lines = ["qutebrowser v{}".format(qutebrowser.__version__)]
    gitver = _git_str()
    if gitver is not None:
        lines.append("Git commit: {}".format(gitver))
    lines += [
        '',
        '{}: {}'.format(platform.python_implementation(),
                        platform.python_version()),
        'Qt: {}, runtime: {}'.format(QT_VERSION_STR, qVersion()),
        'PyQt: {}'.format(PYQT_VERSION_STR),
    ]

    if not short:
        style = QApplication.instance().style()
        lines += [
            'Style: {}'.format(style.metaObject().className()),
            'Desktop: {}'.format(os.environ.get('DESKTOP_SESSION')),
        ]

        lines += _module_versions()

        lines += [
            'Webkit: {}'.format(qWebKitVersion()),
            'Harfbuzz: {}'.format(os.environ.get('QT_HARFBUZZ', 'system')),
            'SSL: {}'.format(QSslSocket.sslLibraryVersionString()),
            '',
            'Frozen: {}'.format(hasattr(sys, 'frozen')),
            'Platform: {}, {}'.format(platform.platform(),
                                      platform.architecture()[0]),
        ]
        lines += _os_info()
    return '\n'.join(lines)
