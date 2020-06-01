# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Utilities to show various version information."""

import re
import sys
import glob
import os.path
import platform
import subprocess
import importlib
import collections
import enum
import datetime
import getpass
import typing
import functools

import attr
import pkg_resources
from PyQt5.QtCore import PYQT_VERSION_STR, QLibraryInfo
from PyQt5.QtNetwork import QSslSocket
from PyQt5.QtGui import (QOpenGLContext, QOpenGLVersionProfile,
                         QOffscreenSurface)
from PyQt5.QtWidgets import QApplication

try:
    from PyQt5.QtWebKit import qWebKitVersion
except ImportError:  # pragma: no cover
    qWebKitVersion = None  # type: ignore[assignment]  # noqa: N816

import qutebrowser
from qutebrowser.utils import log, utils, standarddir, usertypes, message
from qutebrowser.misc import objects, earlyinit, sql, httpclient, pastebin
from qutebrowser.browser import pdfjs
from qutebrowser.config import config

try:
    from qutebrowser.browser.webengine import webenginesettings
except ImportError:  # pragma: no cover
    webenginesettings = None  # type: ignore[assignment]


@attr.s
class DistributionInfo:

    """Information about the running distribution."""

    id = attr.ib()  # type: typing.Optional[str]
    parsed = attr.ib()  # type: Distribution
    version = attr.ib()  # type: typing.Optional[typing.Tuple[str, ...]]
    pretty = attr.ib()  # type: str


pastebin_url = None
Distribution = enum.Enum(
    'Distribution', ['unknown', 'ubuntu', 'debian', 'void', 'arch',
                     'gentoo', 'fedora', 'opensuse', 'linuxmint', 'manjaro',
                     'kde_flatpak'])


def distribution() -> typing.Optional[DistributionInfo]:
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
                if (not line) or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split("=", maxsplit=1)
                info[k] = v.strip('"')
    except (OSError, UnicodeDecodeError):
        return None

    pretty = info.get('PRETTY_NAME', None)
    if pretty in ['Linux', None]:  # Funtoo has PRETTY_NAME=Linux
        pretty = info.get('NAME', 'Unknown')
    assert pretty is not None

    if 'VERSION_ID' in info:
        dist_version = pkg_resources.parse_version(
            info['VERSION_ID']
        )  # type: typing.Optional[typing.Tuple[str, ...]]
    else:
        dist_version = None

    dist_id = info.get('ID', None)
    id_mappings = {
        'funtoo': 'gentoo',  # does not have ID_LIKE=gentoo
        'org.kde.Platform': 'kde_flatpak',
    }

    parsed = Distribution.unknown
    if dist_id is not None:
        try:
            parsed = Distribution[id_mappings.get(dist_id, dist_id)]
        except KeyError:
            pass

    return DistributionInfo(parsed=parsed, version=dist_version, pretty=pretty,
                            id=dist_id)


def is_sandboxed() -> bool:
    """Whether the environment has restricted access to the host system."""
    current_distro = distribution()
    if current_distro is None:
        return False
    return current_distro.parsed == Distribution.kde_flatpak


def _git_str() -> typing.Optional[str]:
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


def _git_str_subprocess(gitpath: str) -> typing.Optional[str]:
    """Try to get the git commit ID and timestamp by calling git.

    Args:
        gitpath: The path where the .git folder is.

    Return:
        The ID/timestamp on success, None on failure.
    """
    if not os.path.isdir(os.path.join(gitpath, ".git")):
        return None
    try:
        # https://stackoverflow.com/questions/21017300/21017394#21017394
        commit_hash = subprocess.run(
            ['git', 'describe', '--match=NeVeRmAtCh', '--always', '--dirty'],
            cwd=gitpath, check=True,
            stdout=subprocess.PIPE).stdout.decode('UTF-8').strip()
        date = subprocess.run(
            ['git', 'show', '-s', '--format=%ci', 'HEAD'],
            cwd=gitpath, check=True,
            stdout=subprocess.PIPE).stdout.decode('UTF-8').strip()
        return '{} ({})'.format(commit_hash, date)
    except (subprocess.CalledProcessError, OSError):
        return None


def _release_info() -> typing.Sequence[typing.Tuple[str, str]]:
    """Try to gather distribution release information.

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


def _module_versions() -> typing.Sequence[str]:
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
        ('PyQt5.QtWebEngine', ['PYQT_WEBENGINE_VERSION_STR']),
        ('PyQt5.QtWebKitWidgets', []),
    ])  # type: typing.Mapping[str, typing.Sequence[str]]
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


def _path_info() -> typing.Mapping[str, str]:
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


def _os_info() -> typing.Sequence[str]:
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
        release, info_tpl, machine = platform.mac_ver()
        if all(not e for e in info_tpl):
            versioninfo = ''
        else:
            versioninfo = '.'.join(info_tpl)
        osver = ', '.join(e for e in [release, versioninfo, machine] if e)
    elif utils.is_posix:
        osver = ' '.join(platform.uname())
    else:
        osver = '?'
    lines.append('OS Version: {}'.format(osver))
    if releaseinfo is not None:
        for (fn, data) in releaseinfo:
            lines += ['', '--- {} ---'.format(fn), data]
    return lines


def _pdfjs_version() -> str:
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


def _chromium_version() -> str:
    """Get the Chromium version for QtWebEngine.

    This can also be checked by looking at this file with the right Qt tag:
    http://code.qt.io/cgit/qt/qtwebengine.git/tree/tools/scripts/version_resolver.py#n41

    Quick reference:

    Qt 5.7:  Chromium 49
             49.0.2623.111 (2016-03-31)
             5.7.1: Security fixes up to 54.0.2840.87 (2016-11-01)

    Qt 5.8:  Chromium 53
             53.0.2785.148 (2016-08-31)
             5.8.0: Security fixes up to 55.0.2883.75 (2016-12-01)

    Qt 5.9:  Chromium 56
    (LTS)    56.0.2924.122 (2017-01-25)
             5.9.9: Security fixes up to 78.0.3904.108 (2019-11-18)

    Qt 5.10: Chromium 61
             61.0.3163.140 (2017-09-05)
             5.10.1: Security fixes up to 64.0.3282.140 (2018-02-01)

    Qt 5.11: Chromium 65
             65.0.3325.151 (.1: .230) (2018-03-06)
             5.11.3: Security fixes up to 70.0.3538.102 (2018-11-09)

    Qt 5.12: Chromium 69
    (LTS)    69.0.3497.113 (2018-09-27)
             5.12.8: Security fixes up to 80.0.3987.149 (2020-03-18)

    Qt 5.13: Chromium 73
             73.0.3683.105 (~2019-02-28)
             5.13.2: Security fixes up to 77.0.3865.120 (2019-10-10)

    Qt 5.14: Chromium 77
             77.0.3865.129 (~2019-10-10)
             5.14.2: Security fixes up to 80.0.3987.132 (2020-03-03)

    Qt 5.15: Chromium 80
             80.0.3987.163 (2020-04-02)
             5.15.0: Security fixes up to 81.0.4044.138 (2020-05-05)

    Also see https://www.chromium.org/developers/calendar
    and https://chromereleases.googleblog.com/
    """
    if webenginesettings is None:
        return 'unavailable'  # type: ignore[unreachable]

    if webenginesettings.parsed_user_agent is None:
        webenginesettings.init_user_agent()
        assert webenginesettings.parsed_user_agent is not None

    return webenginesettings.parsed_user_agent.upstream_browser_version


def _backend() -> str:
    """Get the backend line with relevant information."""
    if objects.backend == usertypes.Backend.QtWebKit:
        return 'new QtWebKit (WebKit {})'.format(qWebKitVersion())
    else:
        webengine = usertypes.Backend.QtWebEngine
        assert objects.backend == webengine, objects.backend
        return 'QtWebEngine (Chromium {})'.format(_chromium_version())


def _uptime() -> datetime.timedelta:
    launch_time = QApplication.instance().launch_time
    time_delta = datetime.datetime.now() - launch_time
    # Round off microseconds
    time_delta -= datetime.timedelta(microseconds=time_delta.microseconds)
    return time_delta


def _autoconfig_loaded() -> str:
    return "yes" if config.instance.yaml_loaded else "no"


def _config_py_loaded() -> str:
    if config.instance.config_py_loaded:
        return "{} has been loaded".format(standarddir.config_py())
    else:
        return "no config.py was loaded"


def version_info() -> str:
    """Return a string with various version information."""
    lines = ["qutebrowser v{}".format(qutebrowser.__version__)]
    gitver = _git_str()
    if gitver is not None:
        lines.append("Git commit: {}".format(gitver))

    lines.append('Backend: {}'.format(_backend()))
    lines.append('Qt: {}'.format(earlyinit.qt_version()))

    lines += [
        '',
        '{}: {}'.format(platform.python_implementation(),
                        platform.python_version()),
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
        lines.append('Platform plugin: {}'.format(qapp.platformName()))
        lines.append('OpenGL: {}'.format(opengl_info()))

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
        "Using Python from {}".format(sys.executable),
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

    lines += [
        '',
        'Autoconfig loaded: {}'.format(_autoconfig_loaded()),
        'Config.py: {}'.format(_config_py_loaded()),
        'Uptime: {}'.format(_uptime())
    ]

    return '\n'.join(lines)


@attr.s
class OpenGLInfo:

    """Information about the OpenGL setup in use."""

    # If we're using OpenGL ES. If so, no further information is available.
    gles = attr.ib(False)  # type: bool

    # The name of the vendor. Examples:
    # - nouveau
    # - "Intel Open Source Technology Center", "Intel", "Intel Inc."
    vendor = attr.ib(None)  # type: typing.Optional[str]

    # The OpenGL version as a string. See tests for examples.
    version_str = attr.ib(None)  # type: typing.Optional[str]

    # The parsed version as a (major, minor) tuple of ints
    version = attr.ib(None)  # type: typing.Optional[typing.Tuple[int, ...]]

    # The vendor specific information following the version number
    vendor_specific = attr.ib(None)  # type: typing.Optional[str]

    def __str__(self) -> str:
        if self.gles:
            return 'OpenGL ES'
        return '{}, {}'.format(self.vendor, self.version_str)

    @classmethod
    def parse(cls, *, vendor: str, version: str) -> 'OpenGLInfo':
        """Parse OpenGL version info from a string.

        The arguments should be the strings returned by OpenGL for GL_VENDOR
        and GL_VERSION, respectively.

        According to the OpenGL reference, the version string should have the
        following format:

        <major>.<minor>[.<release>] <vendor-specific info>
        """
        if ' ' not in version:
            log.misc.warning("Failed to parse OpenGL version (missing space): "
                             "{}".format(version))
            return cls(vendor=vendor, version_str=version)

        num_str, vendor_specific = version.split(' ', maxsplit=1)

        try:
            parsed_version = tuple(int(i) for i in num_str.split('.'))
        except ValueError:
            log.misc.warning("Failed to parse OpenGL version (parsing int): "
                             "{}".format(version))
            return cls(vendor=vendor, version_str=version)

        return cls(vendor=vendor, version_str=version,
                   version=parsed_version, vendor_specific=vendor_specific)


@functools.lru_cache(maxsize=1)
def opengl_info() -> typing.Optional[OpenGLInfo]:  # pragma: no cover
    """Get the OpenGL vendor used.

    This returns a string such as 'nouveau' or
    'Intel Open Source Technology Center'; or None if the vendor can't be
    determined.
    """
    assert QApplication.instance()

    # Some setups can segfault in here if we don't do this.
    utils.libgl_workaround()

    override = os.environ.get('QUTE_FAKE_OPENGL')
    if override is not None:
        log.init.debug("Using override {}".format(override))
        vendor, version = override.split(', ', maxsplit=1)
        return OpenGLInfo.parse(vendor=vendor, version=version)

    old_context = typing.cast(typing.Optional[QOpenGLContext],
                              QOpenGLContext.currentContext())
    old_surface = None if old_context is None else old_context.surface()

    surface = QOffscreenSurface()
    surface.create()

    ctx = QOpenGLContext()
    ok = ctx.create()
    if not ok:
        log.init.debug("Creating context failed!")
        return None

    ok = ctx.makeCurrent(surface)
    if not ok:
        log.init.debug("Making context current failed!")
        return None

    try:
        if ctx.isOpenGLES():
            # Can't use versionFunctions there
            return OpenGLInfo(gles=True)

        vp = QOpenGLVersionProfile()
        vp.setVersion(2, 0)

        try:
            vf = ctx.versionFunctions(vp)
        except ImportError as e:
            log.init.debug("Importing version functions failed: {}".format(e))
            return None

        if vf is None:
            log.init.debug("Getting version functions failed!")
            return None

        vendor = vf.glGetString(vf.GL_VENDOR)
        version = vf.glGetString(vf.GL_VERSION)

        return OpenGLInfo.parse(vendor=vendor, version=version)
    finally:
        ctx.doneCurrent()
        if old_context and old_surface:
            old_context.makeCurrent(old_surface)


def pastebin_version(pbclient: pastebin.PastebinClient = None) -> None:
    """Pastebin the version and log the url to messages."""
    def _yank_url(url: str) -> None:
        utils.set_clipboard(url)
        message.info("Version url {} yanked to clipboard.".format(url))

    def _on_paste_version_success(url: str) -> None:
        assert pbclient is not None
        global pastebin_url
        url = url.strip()
        _yank_url(url)
        pbclient.deleteLater()
        pastebin_url = url

    def _on_paste_version_err(text: str) -> None:
        assert pbclient is not None
        message.error("Failed to pastebin version"
                      " info: {}".format(text))
        pbclient.deleteLater()

    if pastebin_url:
        _yank_url(pastebin_url)
        return

    app = QApplication.instance()
    http_client = httpclient.HTTPClient()

    misc_api = pastebin.PastebinClient.MISC_API_URL
    pbclient = pbclient or pastebin.PastebinClient(http_client, parent=app,
                                                   api_url=misc_api)

    pbclient.success.connect(_on_paste_version_success)
    pbclient.error.connect(_on_paste_version_err)

    pbclient.paste(getpass.getuser(),
                   "qute version info {}".format(qutebrowser.__version__),
                   version_info(),
                   private=True)
