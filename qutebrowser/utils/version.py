# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import re
import sys
import glob
import os.path
import platform
import subprocess
import importlib
import collections

from PyQt5.QtCore import QT_VERSION_STR, PYQT_VERSION_STR, qVersion
from PyQt5.QtNetwork import QSslSocket
from PyQt5.QtWidgets import QApplication

try:
    from PyQt5.QtWebKit import qWebKitVersion
except ImportError:  # pragma: no cover
    qWebKitVersion = None

import qutebrowser
from qutebrowser.utils import log, utils, standarddir
from qutebrowser.browser import pdfjs


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
    blacklisted = ['ANSI_COLOR=', 'HOME_URL=', 'SUPPORT_URL=',
                   'BUG_REPORT_URL=']
    data = []
    for fn in glob.glob("/etc/*-release"):
        lines = []
        try:
            with open(fn, 'r', encoding='utf-8') as f:
                for line in f.read().strip().splitlines():
                    if not any(line.startswith(bl) for bl in blacklisted):
                        lines.append(line)

                if lines:
                    data.append((fn, '\n'.join(lines)))
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
        ('colorama', ['VERSION', '__version__']),
        ('pypeg2', ['__version__']),
        ('jinja2', ['__version__']),
        ('pygments', ['__version__']),
        ('yaml', ['__version__']),
        ('cssutils', ['__version__']),
        ('typing', []),
        ('PyQt5.QtWebEngineWidgets', []),
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


def _path_info():
    """Get info about important path names.

    Return:
        A dictionary of descriptive to actual path names.
    """
    return {
        'config': standarddir.config(),
        'data': standarddir.data(),
        'system_data': standarddir.system_data(),
        'cache': standarddir.cache(),
        'download': standarddir.download(),
        'runtime': standarddir.runtime(),
    }


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
        release, versioninfo, machine = platform.mac_ver()
        if all(not e for e in versioninfo):
            versioninfo = ''
        else:
            versioninfo = '.'.join(versioninfo)
        osver = ', '.join([e for e in [release, versioninfo, machine] if e])
    else:
        osver = '?'
    lines.append('OS Version: {}'.format(osver))
    if releaseinfo is not None:
        for (fn, data) in releaseinfo:
            lines += ['', '--- {} ---'.format(fn), data]
    return lines


def _pdfjs_version():
    """Get the pdf.js version.

    Return:
        A string with the version number.
    """
    try:
        pdfjs_file, file_path = pdfjs.get_pdfjs_res_and_path('build/pdf.js')
    except pdfjs.PDFJSNotFound:
        return 'no'
    else:
        pdfjs_file = pdfjs_file.decode('utf-8')
        version_re = re.compile(
            r"^(PDFJS\.version|var pdfjsVersion) = '([^']+)';$", re.MULTILINE)

        match = version_re.search(pdfjs_file)
        if not match:
            pdfjs_version = 'unknown'
        else:
            pdfjs_version = match.group(2)
        if file_path is None:
            file_path = 'bundled'
        return '{} ({})'.format(pdfjs_version, file_path)


def version():
    """Return a string with various version informations."""
    lines = ["qutebrowser v{}".format(qutebrowser.__version__)]
    gitver = _git_str()
    if gitver is not None:
        lines.append("Git commit: {}".format(gitver))

    if qVersion() != QT_VERSION_STR:
        qt_version = 'Qt: {} (compiled {})'.format(qVersion(), QT_VERSION_STR)
    else:
        qt_version = 'Qt: {}'.format(qVersion())

    lines += [
        '',
        '{}: {}'.format(platform.python_implementation(),
                        platform.python_version()),
        qt_version,
        'PyQt: {}'.format(PYQT_VERSION_STR),
        '',
    ]

    lines += _module_versions()

    lines += ['pdf.js: {}'.format(_pdfjs_version())]

    if qWebKitVersion is None:
        lines.append('Webkit: no')
    else:
        lines.append('Webkit: {}'.format(qWebKitVersion()))

    lines += [
        'SSL: {}'.format(QSslSocket.sslLibraryVersionString()),
        '',
    ]

    qapp = QApplication.instance()
    if qapp:
        style = qapp.style()
        lines.append('Style: {}'.format(style.metaObject().className()))

    importpath = os.path.dirname(os.path.abspath(qutebrowser.__file__))

    lines += [
        'Platform: {}, {}'.format(platform.platform(),
                                  platform.architecture()[0]),
        'Frozen: {}'.format(hasattr(sys, 'frozen')),
        "Imported from {}".format(importpath),
    ]
    lines += _os_info()

    lines += [
        '',
        'Paths:',
    ]
    for name, path in _path_info().items():
        lines += ['{}: {}'.format(name, path)]

    return '\n'.join(lines)
