# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Utilities to show various version information."""

import re
import sys
import glob
import os.path
import platform
import subprocess
import importlib
import pathlib
import configparser
import enum
import datetime
import getpass
import functools
import dataclasses
import importlib.metadata
from typing import (Optional, ClassVar, Any,
                    TYPE_CHECKING)
from collections.abc import Mapping, Sequence

from qutebrowser.qt import machinery
from qutebrowser.qt.core import PYQT_VERSION_STR
from qutebrowser.qt.network import QSslSocket
from qutebrowser.qt.gui import QOpenGLContext, QOffscreenSurface
from qutebrowser.qt.opengl import QOpenGLVersionProfile
from qutebrowser.qt.widgets import QApplication

try:
    from qutebrowser.qt.webkit import qWebKitVersion
except ImportError:  # pragma: no cover
    qWebKitVersion = None  # type: ignore[assignment]  # noqa: N816
try:
    from qutebrowser.qt.webenginecore import PYQT_WEBENGINE_VERSION_STR
except ImportError:  # pragma: no cover
    # QtWebKit
    PYQT_WEBENGINE_VERSION_STR = None  # type: ignore[assignment]


import qutebrowser
from qutebrowser.utils import (log, utils, standarddir, usertypes, message, resources,
                               qtutils)
from qutebrowser.misc import objects, earlyinit, sql, httpclient, pastebin, elf
from qutebrowser.browser import pdfjs
from qutebrowser.config import config
if TYPE_CHECKING:
    from qutebrowser.config import websettings

_LOGO = r'''
         ______     ,,
    ,.-"`      | ,-` |
  .^           ||    |
 /    ,-*^|    ||    |
;    /    |    ||    ;-*```^*.
;   ;     |    |;,-*`         \
|   |     |  ,-*`    ,-"""\    \
|    \   ,-"`    ,-^`|     \    |
 \    `^^    ,-;|    |     ;    |
  *;     ,-*`  ||    |     /   ;;
    `^^`` |    ||    |   ,^    /
          |    ||    `^^`    ,^
          |  _,"|        _,-"
          -*`   ****"""``

'''


@dataclasses.dataclass
class DistributionInfo:

    """Information about the running distribution."""

    id: Optional[str]
    parsed: 'Distribution'
    pretty: str


pastebin_url: Optional[str] = None


class Distribution(enum.Enum):

    """A known Linux distribution.

    Usually lines up with ID=... in /etc/os-release.
    """

    unknown = enum.auto()
    ubuntu = enum.auto()
    debian = enum.auto()
    void = enum.auto()
    arch = enum.auto()  # includes rolling-release derivatives
    gentoo = enum.auto()  # includes funtoo
    fedora = enum.auto()
    opensuse = enum.auto()
    linuxmint = enum.auto()
    manjaro = enum.auto()
    kde_flatpak = enum.auto()  # org.kde.Platform
    neon = enum.auto()
    nixos = enum.auto()
    alpine = enum.auto()
    solus = enum.auto()


def _parse_os_release() -> Optional[dict[str, str]]:
    """Parse an /etc/os-release file."""
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

    return info


def distribution() -> Optional[DistributionInfo]:
    """Get some information about the running Linux distribution.

    Returns:
        A DistributionInfo object, or None if no info could be determined.
            parsed: A Distribution enum member
            pretty: Always a string (might be "Unknown")
    """
    info = _parse_os_release()
    if info is None:
        return None

    pretty = info.get('PRETTY_NAME', None)
    if pretty in ['Linux', None]:  # Funtoo has PRETTY_NAME=Linux
        pretty = info.get('NAME', 'Unknown')
    assert pretty is not None

    dist_id = info.get('ID', None)
    id_mappings = {
        'funtoo': 'gentoo',  # does not have ID_LIKE=gentoo
        'artix': 'arch',
        'org.kde.Platform': 'kde_flatpak',
    }

    ids = []
    if dist_id is not None:
        ids.append(id_mappings.get(dist_id, dist_id))
    if 'ID_LIKE' in info:
        ids.extend(info['ID_LIKE'].split())

    parsed = Distribution.unknown
    for cur_id in ids:
        try:
            parsed = Distribution[cur_id]
        except KeyError:
            pass
        else:
            break

    return DistributionInfo(parsed=parsed, pretty=pretty, id=dist_id)


def is_flatpak() -> bool:
    """Whether qutebrowser is running via Flatpak.

    If packaged via Flatpak, the environment is has restricted access to the host
    system.
    """
    return flatpak_id() is not None


_FLATPAK_INFO_PATH = '/.flatpak-info'


def flatpak_id() -> Optional[str]:
    """Get the ID of the currently running Flatpak (or None if outside of Flatpak)."""
    if 'FLATPAK_ID' in os.environ:
        return os.environ['FLATPAK_ID']

    # 'FLATPAK_ID' was only added in Flatpak 1.2.0:
    # https://lists.freedesktop.org/archives/flatpak/2019-January/001464.html
    # but e.g. Ubuntu 18.04 ships 1.0.9.
    info_file = pathlib.Path(_FLATPAK_INFO_PATH)
    if not info_file.exists():
        return None

    parser = configparser.ConfigParser()
    parser.read(info_file)
    return parser['Application']['name']


def _git_str() -> Optional[str]:
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
        return resources.read_file('git-commit-id')
    except (OSError, ImportError):
        return None


def _call_git(gitpath: str, *args: str) -> str:
    """Call a git subprocess."""
    return subprocess.run(
        ['git'] + list(args),
        cwd=gitpath, check=True,
        stdout=subprocess.PIPE).stdout.decode('UTF-8').strip()


def _git_str_subprocess(gitpath: str) -> Optional[str]:
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
        commit_hash = _call_git(gitpath, 'describe', '--match=NeVeRmAtCh',
                                '--always', '--dirty')
        date = _call_git(gitpath, 'show', '-s', '--format=%ci', 'HEAD')
        branch = _call_git(gitpath, 'rev-parse', '--abbrev-ref', 'HEAD')
        return '{} on {} ({})'.format(commit_hash, branch, date)
    except (subprocess.CalledProcessError, OSError):
        return None


def _release_info() -> Sequence[tuple[str, str]]:
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


class ModuleInfo:

    """Class to query version information of qutebrowser dependencies.

    Attributes:
        name: Name of the module as it is imported.
        _version_attributes:
            Sequence of attribute names belonging to the module which may hold
            version information.
        min_version: Minimum version of this module which qutebrowser can use.
        _installed: Is the module installed? Determined at runtime.
        _version: Version of the module. Determined at runtime.
        _initialized:
            Set to `True` if the `self._installed` and `self._version`
            attributes have been set.
    """

    def __init__(
        self,
        name: str,
        version_attributes: Sequence[str],
        min_version: Optional[str] = None
    ):
        self.name = name
        self._version_attributes = version_attributes
        self.min_version = min_version
        self._installed = False
        self._version: Optional[str] = None
        self._initialized = False

    def _reset_cache(self) -> None:
        """Reset the version cache.

        It is necessary to call this method in unit tests that mock a module's
        version number.
        """
        self._installed = False
        self._version = None
        self._initialized = False

    def _initialize_info(self) -> None:
        """Import module and set `self.installed` and `self.version`."""
        try:
            module = importlib.import_module(self.name)
        except (ImportError, ValueError):
            self._installed = False
            return

        self._installed = True

        for attribute_name in self._version_attributes:
            if hasattr(module, attribute_name):
                version = getattr(module, attribute_name)
                assert isinstance(version, (str, float))
                self._version = str(version)
                break

        if self._version is None:
            try:
                self._version = importlib.metadata.version(self.name)
            except importlib.metadata.PackageNotFoundError:
                log.misc.debug(f"{self.name} not found")
                self._version = None

        self._initialized = True

    def get_version(self) -> Optional[str]:
        """Finds the module version if it exists."""
        if not self._initialized:
            self._initialize_info()
        return self._version

    def is_installed(self) -> bool:
        """Checks whether the module is installed."""
        if not self._initialized:
            self._initialize_info()
        return self._installed

    def is_outdated(self) -> Optional[bool]:
        """Checks whether the module is outdated.

        Return:
            A boolean when the version and minimum version are both defined.
            Otherwise `None`.
        """
        version = self.get_version()
        if (
            not self.is_installed()
            or version is None
            or self.min_version is None
        ):
            return None
        return version < self.min_version

    def is_usable(self) -> bool:
        """Whether the module is both installed and not outdated."""
        return self.is_installed() and not self.is_outdated()

    def __str__(self) -> str:
        if not self.is_installed():
            return f'{self.name}: no'

        version = self.get_version()
        if version is None:
            return f'{self.name}: unknown'

        text = f'{self.name}: {version}'
        if self.is_outdated():
            text += f" (< {self.min_version}, outdated)"
        return text


def _create_module_info() -> dict[str, ModuleInfo]:
    packages = [
        ('colorama', ['VERSION', '__version__']),
        ('jinja2', []),
        ('pygments', ['__version__']),
        ('yaml', ['__version__']),
        ('adblock', ['__version__'], "0.3.2"),
        ('objc', ['__version__']),
    ]

    if machinery.IS_QT5:
        packages += [
            ('PyQt5.QtWebEngineWidgets', []),
            ('PyQt5.QtWebEngine', ['PYQT_WEBENGINE_VERSION_STR']),
            ('PyQt5.QtWebKitWidgets', []),
            ('PyQt5.sip', ['SIP_VERSION_STR']),
        ]
    elif machinery.IS_QT6:
        packages += [
            ('PyQt6.QtWebEngineCore', ['PYQT_WEBENGINE_VERSION_STR']),
            ('PyQt6.sip', ['SIP_VERSION_STR']),
        ]
    else:
        raise utils.Unreachable()

    # Mypy doesn't understand this. See https://github.com/python/mypy/issues/9706
    return {
        name: ModuleInfo(name, *args)  # type: ignore[arg-type, misc]
        for (name, *args) in packages
    }


MODULE_INFO: Mapping[str, ModuleInfo] = _create_module_info()


def _module_versions() -> Sequence[str]:
    """Get versions of optional modules.

    Return:
        A list of lines with version info.
    """
    return [str(mod_info) for mod_info in MODULE_INFO.values()]


def _path_info() -> Mapping[str, str]:
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


def _os_info() -> Sequence[str]:
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
        pdfjs_file, file_path = pdfjs.get_pdfjs_res_and_path(pdfjs.get_pdfjs_js_path())
    except pdfjs.PDFJSNotFound:
        return 'no'
    else:
        pdfjs_file = pdfjs_file.decode('utf-8')
        version_re = re.compile(
            r"""^ *(PDFJS\.version|(var|const|\*) pdfjsVersion) = ['"]?(?P<version>[^'"\n]+)['"]?;?$""",
            re.MULTILINE)

        match = version_re.search(pdfjs_file)
        pdfjs_version = 'unknown' if not match else match.group('version')
        if file_path is None:
            file_path = 'bundled'

        return '{} ({})'.format(pdfjs_version, file_path)


def _get_pyqt_webengine_qt_version() -> Optional[str]:
    """Get the version of the PyQtWebEngine-Qt package.

    With PyQtWebEngine 5.15.3, the QtWebEngine binary got split into its own
    PyQtWebEngine-Qt PyPI package:

    https://www.riverbankcomputing.com/pipermail/pyqt/2021-February/043591.html
    https://www.riverbankcomputing.com/pipermail/pyqt/2021-February/043638.html

    PyQtWebEngine 5.15.4 renamed it to PyQtWebEngine-Qt5...:
    https://www.riverbankcomputing.com/pipermail/pyqt/2021-March/043699.html

    Here, we try to use importlib.metadata to figure out that version number.
    If PyQtWebEngine is installed via pip, this will give us an accurate answer.
    """
    names = (
        ['PyQt6-WebEngine-Qt6']
        if machinery.IS_QT6 else
        ['PyQtWebEngine-Qt5', 'PyQtWebEngine-Qt']
    )

    for name in names:
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            log.misc.debug(f"{name} not found")

    return None


@dataclasses.dataclass
class WebEngineVersions:

    """Version numbers for QtWebEngine and the underlying Chromium."""

    webengine: utils.VersionNumber
    chromium: Optional[str]
    source: str
    chromium_security: Optional[str] = None
    chromium_major: Optional[int] = dataclasses.field(init=False)

    # Dates based on https://chromium.googlesource.com/chromium/src/+refs
    _BASES: ClassVar[dict[int, str]] = {
        83: '83.0.4103.122',  # 2020-06-27, Qt 5.15.2
        87: '87.0.4280.144',  # 2021-01-08, Qt 5.15
        90: '90.0.4430.228',  # 2021-06-22, Qt 6.2
        94: '94.0.4606.126',  # 2021-11-17, Qt 6.3
        102: '102.0.5005.177',  # 2022-09-01, Qt 6.4
        # (.220 claimed by code, .181 claimed by CHROMIUM_VERSION)
        108: '108.0.5359.220',  # 2023-01-27, Qt 6.5
        112: '112.0.5615.213',  # 2023-05-24, Qt 6.6
        118: '118.0.5993.220',  # 2024-01-25, Qt 6.7
        122: '122.0.6261.171',  # 2024-04-15, Qt 6.8
        130: '130.0.6723.192',  # 2025-01-06, Qt 6.9
    }

    # Dates based on https://chromereleases.googleblog.com/
    _CHROMIUM_VERSIONS: ClassVar[dict[utils.VersionNumber, tuple[str, Optional[str]]]] = {
        # ====== UNSUPPORTED =====

        # Qt 5.12: Chromium 69
        # (LTS)    69.0.3497.128 (~2018-09-11)
        #          5.12.10: Security fixes up to 86.0.4240.75 (2020-10-06)

        # Qt 5.13: Chromium 73
        #          73.0.3683.105 (~2019-02-28)
        #          5.13.2: Security fixes up to 77.0.3865.120 (2019-10-10)

        # Qt 5.14: Chromium 77
        #          77.0.3865.129 (~2019-10-10)
        #          5.14.2: Security fixes up to 80.0.3987.132 (2020-03-03)

        # Qt 5.15: Chromium 80
        #          80.0.3987.163 (2020-04-02)
        #          5.15.0: Security fixes up to 81.0.4044.138 (2020-05-05)
        #          5.15.1: Security fixes up to 85.0.4183.83  (2020-08-25)

        # ====== SUPPORTED =====
        #                               base         security
        ## Qt 5.15
        utils.VersionNumber(5, 15, 2): (_BASES[83], '86.0.4240.183'),  # 2020-11-02
        utils.VersionNumber(5, 15): (_BASES[87], None),  # >= 5.15.3
        utils.VersionNumber(5, 15, 3): (_BASES[87], '88.0.4324.150'),  # 2021-02-04
        # 5.15.4 to 5.15.6: unknown security fixes
        utils.VersionNumber(5, 15, 7): (_BASES[87], '94.0.4606.61'),  # 2021-09-24
        utils.VersionNumber(5, 15, 8): (_BASES[87], '96.0.4664.110'),  # 2021-12-13
        utils.VersionNumber(5, 15, 9): (_BASES[87], '98.0.4758.102'),  # 2022-02-14
        utils.VersionNumber(5, 15, 10): (_BASES[87], '98.0.4758.102'),  # (?) 2022-02-14
        utils.VersionNumber(5, 15, 11): (_BASES[87], '98.0.4758.102'),  # (?) 2022-02-14
        utils.VersionNumber(5, 15, 12): (_BASES[87], '98.0.4758.102'),  # (?) 2022-02-14
        utils.VersionNumber(5, 15, 13): (_BASES[87], '108.0.5359.124'),  # 2022-12-13
        utils.VersionNumber(5, 15, 14): (_BASES[87], '113.0.5672.64'),  # 2023-05-02
        # 5.15.15: unknown security fixes
        utils.VersionNumber(5, 15, 16): (_BASES[87], '119.0.6045.123'),  # 2023-11-07
        utils.VersionNumber(5, 15, 17): (_BASES[87], '123.0.6312.58'),  # 2024-03-19
        utils.VersionNumber(5, 15, 18): (_BASES[87], '130.0.6723.59'),  # 2024-10-14
        utils.VersionNumber(5, 15, 19): (_BASES[87], '135.0.7049.95'),  # 2025-04-14


        ## Qt 6.2
        utils.VersionNumber(6, 2): (_BASES[90], '93.0.4577.63'),  # 2021-08-31
        utils.VersionNumber(6, 2, 1): (_BASES[90], '94.0.4606.61'),  # 2021-09-24
        utils.VersionNumber(6, 2, 2): (_BASES[90], '96.0.4664.45'),  # 2021-11-15
        utils.VersionNumber(6, 2, 3): (_BASES[90], '96.0.4664.45'),  # 2021-11-15
        utils.VersionNumber(6, 2, 4): (_BASES[90], '98.0.4758.102'),  # 2022-02-14
        # 6.2.5 / 6.2.6: unknown security fixes
        utils.VersionNumber(6, 2, 7): (_BASES[90], '107.0.5304.110'),  # 2022-11-08
        utils.VersionNumber(6, 2, 8): (_BASES[90], '111.0.5563.110'),  # 2023-03-21

        ## Qt 6.3
        utils.VersionNumber(6, 3): (_BASES[94], '99.0.4844.84'),  # 2022-03-25
        utils.VersionNumber(6, 3, 1): (_BASES[94], '101.0.4951.64'),  # 2022-05-10
        utils.VersionNumber(6, 3, 2): (_BASES[94], '104.0.5112.81'),  # 2022-08-01

        ## Qt 6.4
        utils.VersionNumber(6, 4): (_BASES[102], '104.0.5112.102'),  # 2022-08-16
        utils.VersionNumber(6, 4, 1): (_BASES[102], '107.0.5304.88'),  # 2022-10-27
        utils.VersionNumber(6, 4, 2): (_BASES[102], '108.0.5359.94'),  # 2022-12-02
        utils.VersionNumber(6, 4, 3): (_BASES[102], '110.0.5481.78'),  # 2023-02-07

        ## Qt 6.5
        utils.VersionNumber(6, 5): (_BASES[108], '110.0.5481.104'),  # 2023-02-16
        utils.VersionNumber(6, 5, 1): (_BASES[108], '112.0.5615.138'),  # 2023-04-18
        utils.VersionNumber(6, 5, 2): (_BASES[108], '114.0.5735.133'),  # 2023-06-13
        utils.VersionNumber(6, 5, 3): (_BASES[108], '117.0.5938.63'),  # 2023-09-12

        ## Qt 6.6
        utils.VersionNumber(6, 6): (_BASES[112], '117.0.5938.63'),  # 2023-09-12
        utils.VersionNumber(6, 6, 1): (_BASES[112], '119.0.6045.123'),  # 2023-11-07
        utils.VersionNumber(6, 6, 2): (_BASES[112], '121.0.6167.160'),  # 2024-02-06
        utils.VersionNumber(6, 6, 3): (_BASES[112], '122.0.6261.128'),  # 2024-03-12

        ## Qt 6.7
        utils.VersionNumber(6, 7): (_BASES[118], '122.0.6261.128'),  # 2024-03-12
        utils.VersionNumber(6, 7, 1): (_BASES[118], '124.0.6367.202'),  # 2024-05-09
        utils.VersionNumber(6, 7, 2): (_BASES[118], '125.0.6422.142'),  # 2024-05-30
        utils.VersionNumber(6, 7, 3): (_BASES[118], '129.0.6668.58'),  # 2024-09-17

        ## Qt 6.8
        utils.VersionNumber(6, 8): (_BASES[122], '129.0.6668.70'),  # 2024-09-24
        utils.VersionNumber(6, 8, 1): (_BASES[122], '131.0.6778.70'),  # 2024-11-12
        utils.VersionNumber(6, 8, 2): (_BASES[122], '132.0.6834.111'),  # 2025-01-22
        utils.VersionNumber(6, 8, 3): (_BASES[122], '134.0.6998.89'),  # 2025-03-10

        ## Qt 6.9
        utils.VersionNumber(6, 9): (_BASES[130], '133.0.6943.141'),  # 2025-02-25
        utils.VersionNumber(6, 9, 1): (_BASES[130], '136.0.7103.114'),  # 2025-05-13
    }

    def __post_init__(self) -> None:
        """Set the major Chromium version."""
        if self.chromium is None:
            self.chromium_major = None
        else:
            self.chromium_major = int(self.chromium.split('.')[0])

    def __str__(self) -> str:
        lines = [f'QtWebEngine {self.webengine}']
        if self.chromium is not None:
            lines.append(f'  based on Chromium {self.chromium}')
        if self.chromium_security is not None:
            lines.append(f'  with security patches up to {self.chromium_security} (plus any distribution patches)')
        lines.append(f'  (source: {self.source})')
        return "\n".join(lines)

    @classmethod
    def from_ua(cls, ua: 'websettings.UserAgent') -> 'WebEngineVersions':
        """Get the versions parsed from a user agent.

        This is the most reliable and "default" way to get this information for
        older Qt versions that don't provide an API for it. However, it needs a
        fully initialized QtWebEngine, and we sometimes need this information
        before that is available.
        """
        assert ua.qt_version is not None, ua
        webengine = utils.VersionNumber.parse(ua.qt_version)
        chromium_inferred, chromium_security = cls._infer_chromium_version(webengine)
        if ua.upstream_browser_version != chromium_inferred:  # pragma: no cover
            # should never happen, but let's play it safe
            log.misc.debug(
                f"Chromium version mismatch: {ua.upstream_browser_version} (UA) != "
                f"{chromium_inferred} (inferred)")
            chromium_security = None

        return cls(
            webengine=webengine,
            chromium=ua.upstream_browser_version,
            chromium_security=chromium_security,
            source='UA',
        )

    @classmethod
    def from_elf(cls, versions: elf.Versions) -> 'WebEngineVersions':
        """Get the versions based on an ELF file.

        This only works on Linux, and even there, depends on various assumption on how
        QtWebEngine is built (e.g. that the version string is in the .rodata section).

        On Windows/macOS, we instead rely on from_pyqt, but especially on Linux, people
        sometimes mix and match Qt/QtWebEngine versions, so this is a more reliable
        (though hackish) way to get a more accurate result.
        """
        webengine = utils.VersionNumber.parse(versions.webengine)
        chromium_inferred, chromium_security = cls._infer_chromium_version(webengine)
        if versions.chromium != chromium_inferred:  # pragma: no cover
            # should never happen, but let's play it safe
            log.misc.debug(
                f"Chromium version mismatch: {versions.chromium} (ELF) != "
                f"{chromium_inferred} (inferred)")
            chromium_security = None

        return cls(
            webengine=webengine,
            chromium=versions.chromium,
            chromium_security=chromium_security,
            source='ELF',
        )

    @classmethod
    def _infer_chromium_version(
            cls,
            pyqt_webengine_version: utils.VersionNumber,
    ) -> tuple[Optional[str], Optional[str]]:
        """Infer the Chromium version based on the PyQtWebEngine version.

        Returns:
            A tuple of the Chromium version and the security patch version.
        """
        chromium_version, security_version = cls._CHROMIUM_VERSIONS.get(
            pyqt_webengine_version, (None, None))
        if chromium_version is not None:
            return chromium_version, security_version

        # 5.15 patch versions change their QtWebEngine version, but no changes are
        # expected after 5.15.3 and 5.15.[01] are unsupported.
        assert pyqt_webengine_version != utils.VersionNumber(5, 15, 2)

        # e.g. 5.15.4 -> 5.15
        # we ignore the security version as that one will have changed from .0
        # and is thus unknown.
        minor_version = pyqt_webengine_version.strip_patch()
        chromium_ver, _security_ver = cls._CHROMIUM_VERSIONS.get(
            minor_version, (None, None))

        return chromium_ver, None

    @classmethod
    def from_api(
        cls,
        qtwe_version: str,
        chromium_version: Optional[str],
        chromium_security: Optional[str] = None,
    ) -> 'WebEngineVersions':
        """Get the versions based on the exact versions.

        This is called if we have proper APIs to get the versions easily
        (Qt 6.2 with PyQt 6.3.1+).
        """
        parsed = utils.VersionNumber.parse(qtwe_version)
        return cls(
            webengine=parsed,
            chromium=chromium_version,
            chromium_security=chromium_security,
            source='api',
        )

    @classmethod
    def from_webengine(
        cls,
        pyqt_webengine_qt_version: str,
        source: str,
    ) -> 'WebEngineVersions':
        """Get the versions based on the PyQtWebEngine version.

        This is called if we don't want to fully initialize QtWebEngine (so
        from_ua isn't possible), we're not on Linux (or ELF parsing failed), but we have
        a PyQtWebEngine-Qt{,5} package from PyPI, so we could query its exact version.
        """
        parsed = utils.VersionNumber.parse(pyqt_webengine_qt_version)
        chromium, chromium_security = cls._infer_chromium_version(parsed)
        return cls(
            webengine=parsed,
            chromium=chromium,
            chromium_security=chromium_security,
            source=source,
        )

    @classmethod
    def from_pyqt(cls, pyqt_webengine_version: str, source: str = "PyQt") -> 'WebEngineVersions':
        """Get the versions based on the PyQtWebEngine version.

        This is the "last resort" if we don't want to fully initialize QtWebEngine (so
        from_ua isn't possible), we're not on Linux (or ELF parsing failed), and
        PyQtWebEngine-Qt{5,} isn't available from PyPI.

        Here, we assume that the PyQtWebEngine version is the same as the QtWebEngine
        version, and infer the Chromium version from that. This assumption isn't
        generally true, but good enough for some scenarios, especially the prebuilt
        Windows/macOS releases.
        """
        parsed = utils.VersionNumber.parse(pyqt_webengine_version)
        if utils.VersionNumber(5, 15, 3) <= parsed < utils.VersionNumber(6):
            # If we land here, we're in a tricky situation where we are forced to guess:
            #
            # PyQt 5.15.3 and 5.15.4 from PyPI come with QtWebEngine 5.15.2 (Chromium
            # 83), not 5.15.3 (Chromium 87). Given that there was no binary release of
            # QtWebEngine 5.15.3, this is unlikely to change before Qt 6.
            #
            # However, at this point:
            #
            # - ELF parsing failed
            #   (so we're likely on macOS or Windows, but not definitely)
            #
            # - Getting infos from a PyPI-installed PyQtWebEngine failed
            #   (so we're either in a PyInstaller-deployed qutebrowser, or a self-built
            #   or distribution-installed Qt)
            #
            # PyQt 5.15.3 and 5.15.4 come with QtWebEngine 5.15.2 (83-based), but if
            # someone lands here with the last Qt/PyQt installed from source, they might
            # be using QtWebEngine 5.15.3 (87-based). For now, we play it safe, and only
            # do this kind of "downgrade" when we know we're using PyInstaller.
            frozen = hasattr(sys, 'frozen')
            log.misc.debug(f"PyQt5 >= 5.15.3, frozen {frozen}")
            if frozen:
                parsed = utils.VersionNumber(5, 15, 2)

        chromium, chromium_security = cls._infer_chromium_version(parsed)

        return cls(
            webengine=parsed,
            chromium=chromium,
            chromium_security=chromium_security,
            source=source,
        )


def qtwebengine_versions(*, avoid_init: bool = False) -> WebEngineVersions:
    """Get the QtWebEngine and Chromium version numbers.

    If we have a parsed user agent, we use it here. If not, we avoid initializing
    things at all costs (because this gets called early to find out about commandline
    arguments). Instead, we fall back on looking at the ELF file (on Linux), or, if that
    fails, use the PyQtWebEngine version.

    This can also be checked by looking at this file with the right Qt tag:
    https://code.qt.io/cgit/qt/qtwebengine.git/tree/tools/scripts/version_resolver.py#n41

    See WebEngineVersions above for a quick reference.

    Also see:

    - https://chromiumdash.appspot.com/schedule
    - https://www.chromium.org/developers/calendar
    - https://chromereleases.googleblog.com/
    """
    override = os.environ.get('QUTE_QTWEBENGINE_VERSION_OVERRIDE')
    if override is not None:
        return WebEngineVersions.from_pyqt(override, source='override')

    if machinery.IS_QT6:
        try:
            from qutebrowser.qt.webenginecore import (
                qWebEngineVersion,
                qWebEngineChromiumVersion,
            )
        except ImportError:
            pass  # Needs QtWebEngine 6.2+ with PyQtWebEngine 6.3.1+
        else:
            try:
                from qutebrowser.qt.webenginecore import (
                    qWebEngineChromiumSecurityPatchVersion,
                )
                chromium_security = qWebEngineChromiumSecurityPatchVersion()
            except ImportError:
                chromium_security = None  # Needs QtWebEngine 6.3+

            qtwe_version = qWebEngineVersion()
            assert qtwe_version is not None
            return WebEngineVersions.from_api(
                qtwe_version=qtwe_version,
                chromium_version=qWebEngineChromiumVersion(),
                chromium_security=chromium_security,
            )

    from qutebrowser.browser.webengine import webenginesettings

    if webenginesettings.parsed_user_agent is None and not avoid_init:
        webenginesettings.init_user_agent()

    if webenginesettings.parsed_user_agent is not None:
        return WebEngineVersions.from_ua(webenginesettings.parsed_user_agent)

    versions = elf.parse_webenginecore()
    if versions is not None:
        return WebEngineVersions.from_elf(versions)

    pyqt_webengine_qt_version = _get_pyqt_webengine_qt_version()
    if pyqt_webengine_qt_version is not None:
        return WebEngineVersions.from_webengine(
            pyqt_webengine_qt_version, source='importlib')

    assert PYQT_WEBENGINE_VERSION_STR is not None
    return WebEngineVersions.from_pyqt(PYQT_WEBENGINE_VERSION_STR)


def _backend() -> str:
    """Get the backend line with relevant information."""
    if objects.backend == usertypes.Backend.QtWebKit:
        return 'new QtWebKit (WebKit {})'.format(qWebKitVersion())
    elif objects.backend == usertypes.Backend.QtWebEngine:
        return str(qtwebengine_versions(
            avoid_init='avoid-chromium-init' in objects.debug_flags))
    raise utils.Unreachable(objects.backend)


def _uptime() -> datetime.timedelta:
    time_delta = datetime.datetime.now() - objects.qapp.launch_time
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
    lines = _LOGO.lstrip('\n').splitlines()

    lines.append("qutebrowser v{}".format(qutebrowser.__version__))
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
        str(machinery.INFO),
        '',
    ]

    lines += _module_versions()

    lines += [
        'pdf.js: {}'.format(_pdfjs_version()),
        'sqlite: {}'.format(sql.version()),
        'QtNetwork SSL: {}\n'.format(QSslSocket.sslLibraryVersionString()
                                     if QSslSocket.supportsSsl() else 'no'),
    ]

    if objects.qapp:
        style = objects.qapp.style()
        assert style is not None
        metaobj = style.metaObject()
        assert metaobj is not None
        lines.append('Style: {}'.format(metaobj.className()))
        lines.append('Platform plugin: {}'.format(objects.qapp.platformName()))
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
            qtutils.library_path(qtutils.LibraryPath.library_executables),
            qtutils.library_path(qtutils.LibraryPath.data),
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


@dataclasses.dataclass
class OpenGLInfo:

    """Information about the OpenGL setup in use."""

    # If we're using OpenGL ES. If so, no further information is available.
    gles: bool = False

    # The name of the vendor. Examples:
    # - nouveau
    # - "Intel Open Source Technology Center", "Intel", "Intel Inc."
    vendor: Optional[str] = None

    # The OpenGL version as a string. See tests for examples.
    version_str: Optional[str] = None

    # The parsed version as a (major, minor) tuple of ints
    version: Optional[tuple[int, ...]] = None

    # The vendor specific information following the version number
    vendor_specific: Optional[str] = None

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
def opengl_info() -> Optional[OpenGLInfo]:  # pragma: no cover
    """Get the OpenGL vendor used.

    This returns a string such as 'nouveau' or
    'Intel Open Source Technology Center'; or None if the vendor can't be
    determined.
    """
    assert QApplication.instance()

    override = os.environ.get('QUTE_FAKE_OPENGL')
    if override is not None:
        log.init.debug("Using override {}".format(override))
        vendor, version = override.split(', ', maxsplit=1)
        return OpenGLInfo.parse(vendor=vendor, version=version)

    old_context: Optional[QOpenGLContext] = QOpenGLContext.currentContext()
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
            if machinery.IS_QT5:
                vf = ctx.versionFunctions(vp)
            else:
                # Qt 6
                from qutebrowser.qt.opengl import QOpenGLVersionFunctionsFactory
                vf: Any = QOpenGLVersionFunctionsFactory.get(vp, ctx)
        except ImportError as e:
            log.init.debug("Importing version functions failed: {}".format(e))
            return None

        if vf is None:
            log.init.debug("Getting version functions failed!")
            return None

        # FIXME:mypy PyQt6-stubs issue?
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
