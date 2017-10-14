# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import pkg_resources

import attr
from PyQt5.QtCore import PYQT_VERSION_STR, QLibraryInfo
from PyQt5.QtNetwork import QSslSocket
from PyQt5.QtGui import (QOpenGLContext, QOpenGLVersionProfile,
                         QOffscreenSurface)
from PyQt5.QtWidgets import QApplication

try:
    from PyQt5.QtWebKit import qWebKitVersion
except ImportError:  # pragma: no cover
    qWebKitVersion = None

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineProfile
except ImportError:  # pragma: no cover
    QWebEngineProfile = None

import qutebrowser
from qutebrowser.utils import log, utils, standarddir, usertypes
from qutebrowser.misc import objects, earlyinit, sql
from qutebrowser.browser import pdfjs


@attr.s
class DistributionInfo:

    """Information about the running distribution."""

    id = attr.ib()
    parsed = attr.ib()
    version = attr.ib()
    pretty = attr.ib()


Distribution = usertypes.enum(
    'Distribution', ['unknown', 'ubuntu', 'debian', 'void', 'arch',
                     'gentoo', 'fedora', 'opensuse', 'linuxmint', 'manjaro'])


def distribution():
    """Get some information about the running Linux distribution.

    Returns:
        A DistributionInfo object, or None if no info could be determined.
            parsed: A Distribution enum member
            version: A Version object, or None
            pretty: Always a string (might be "Unknown")
    """
    filename = os.environ.get('QUTE_FAKE_OS_RELEASE', '/etc/os-release')
    info = {}
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if (not line) or line.startswith('#'):
                    continue
                k, v = line.split("=", maxsplit=1)
                info[k] = v.strip('"')
    except (OSError, UnicodeDecodeError):
        return None

    pretty = info.get('PRETTY_NAME', 'Unknown')
    if pretty == 'Linux':  # Thanks, Funtoo
        pretty = info.get('NAME', pretty)

    if 'VERSION_ID' in info:
        dist_version = pkg_resources.parse_version(info['VERSION_ID'])
    else:
        dist_version = None

    dist_id = info.get('ID', None)
    id_mappings = {
        'funtoo': 'gentoo',  # does not have ID_LIKE=gentoo
    }
    try:
        parsed = Distribution[id_mappings.get(dist_id, dist_id)]
    except KeyError:
        parsed = Distribution.unknown

    return DistributionInfo(parsed=parsed, version=dist_version, pretty=pretty,
                            id=dist_id)


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
        ('attr', ['__version__']),
        ('PyQt5.QtWebEngineWidgets', []),
        ('PyQt5.QtWebKitWidgets', []),
    ])
    for modname, attributes in modules.items():
        try:
            module = importlib.import_module(modname)
        except ImportError:
            text = '{}: no'.format(modname)
        else:
            for name in attributes:
                try:
                    text = '{}: {}'.format(modname, getattr(module, name))
                except AttributeError:
                    pass
                else:
                    break
            else:
                text = '{}: yes'.format(modname)
        lines.append(text)
    return lines


def _path_info():
    """Get info about important path names.

    Return:
        A dictionary of descriptive to actual path names.
    """
    info = {
        'config': standarddir.config(),
        'data': standarddir.data(),
        'cache': standarddir.cache(),
        'runtime': standarddir.runtime(),
    }
    if standarddir.config() != standarddir.config(auto=True):
        info['auto config'] = standarddir.config(auto=True)
    if standarddir.data() != standarddir.data(system=True):
        info['system data'] = standarddir.data(system=True)
    return info


def _os_info():
    """Get operating system info.

    Return:
        A list of lines with version info.
    """
    lines = []
    releaseinfo = None
    if utils.is_linux:
        osver = ''
        releaseinfo = _release_info()
    elif utils.is_windows:
        osver = ', '.join(platform.win32_ver())
    elif utils.is_mac:
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
            r"^ *(PDFJS\.version|var pdfjsVersion) = '([^']+)';$",
            re.MULTILINE)

        match = version_re.search(pdfjs_file)
        if not match:
            pdfjs_version = 'unknown'
        else:
            pdfjs_version = match.group(2)
        if file_path is None:
            file_path = 'bundled'
        return '{} ({})'.format(pdfjs_version, file_path)


def _chromium_version():
    """Get the Chromium version for QtWebEngine."""
    if QWebEngineProfile is None:
        # This should never happen
        return 'unavailable'
    profile = QWebEngineProfile()
    ua = profile.httpUserAgent()
    match = re.search(r' Chrome/([^ ]*) ', ua)
    if not match:
        log.misc.error("Could not get Chromium version from: {}".format(ua))
        return 'unknown'
    return match.group(1)


def _backend():
    """Get the backend line with relevant information."""
    if objects.backend == usertypes.Backend.QtWebKit:
        return 'new QtWebKit (WebKit {})'.format(qWebKitVersion())
    else:
        webengine = usertypes.Backend.QtWebEngine
        assert objects.backend == webengine, objects.backend
        return 'QtWebEngine (Chromium {})'.format(_chromium_version())


def version():
    """Return a string with various version informations."""
    lines = ["qutebrowser v{}".format(qutebrowser.__version__)]
    gitver = _git_str()
    if gitver is not None:
        lines.append("Git commit: {}".format(gitver))

    lines.append("Backend: {}".format(_backend()))

    lines += [
        '',
        '{}: {}'.format(platform.python_implementation(),
                        platform.python_version()),
        'Qt: {}'.format(earlyinit.qt_version()),
        'PyQt: {}'.format(PYQT_VERSION_STR),
        '',
    ]

    lines += _module_versions()

    lines += [
        'pdf.js: {}'.format(_pdfjs_version()),
        'sqlite: {}'.format(sql.version()),
        'QtNetwork SSL: {}\n'.format(QSslSocket.sslLibraryVersionString()
                                     if QSslSocket.supportsSsl() else 'no'),
    ]

    qapp = QApplication.instance()
    if qapp:
        style = qapp.style()
        lines.append('Style: {}'.format(style.metaObject().className()))

    importpath = os.path.dirname(os.path.abspath(qutebrowser.__file__))

    lines += [
        'Platform: {}, {}'.format(platform.platform(),
                                  platform.architecture()[0]),
    ]
    dist = distribution()
    if dist is not None:
        lines += [
            'Linux distribution: {} ({})'.format(dist.pretty, dist.parsed.name)
        ]

    lines += [
        'Frozen: {}'.format(hasattr(sys, 'frozen')),
        "Imported from {}".format(importpath),
        "Qt library executable path: {}, data path: {}".format(
            QLibraryInfo.location(QLibraryInfo.LibraryExecutablesPath),
            QLibraryInfo.location(QLibraryInfo.DataPath)
        )
    ]

    if not dist or dist.parsed == Distribution.unknown:
        lines += _os_info()

    lines += [
        '',
        'Paths:',
    ]
    for name, path in sorted(_path_info().items()):
        lines += ['{}: {}'.format(name, path)]

    return '\n'.join(lines)


def opengl_vendor():  # pragma: no cover
    """Get the OpenGL vendor used.

    This returns a string such as 'nouveau' or
    'Intel Open Source Technology Center'; or None if the vendor can't be
    determined.
    """
    assert QApplication.instance()

    old_context = QOpenGLContext.currentContext()
    old_surface = None if old_context is None else old_context.surface()

    surface = QOffscreenSurface()
    surface.create()

    ctx = QOpenGLContext()
    ok = ctx.create()
    if not ok:
        log.init.debug("opengl_vendor: Creating context failed!")
        return None

    ok = ctx.makeCurrent(surface)
    if not ok:
        log.init.debug("opengl_vendor: Making context current failed!")
        return None

    try:
        if ctx.isOpenGLES():
            # Can't use versionFunctions there
            return None

        vp = QOpenGLVersionProfile()
        vp.setVersion(2, 0)

        vf = ctx.versionFunctions(vp)
        if vf is None:
            log.init.debug("opengl_vendor: Getting version functions failed!")
            return None

        return vf.glGetString(vf.GL_VENDOR)
    finally:
        ctx.doneCurrent()
        if old_context and old_surface:
            old_context.makeCurrent(old_surface)
