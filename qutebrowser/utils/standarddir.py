# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Utilities to get and initialize data/config paths."""

import os
import os.path
import sys
import contextlib
import enum
import argparse
from typing import Iterator, Optional

from PyQt5.QtCore import QStandardPaths
from PyQt5.QtWidgets import QApplication

from qutebrowser.utils import log, debug, utils, version

# The cached locations
_locations = {}


class _Location(enum.Enum):

    """A key for _locations."""

    config = enum.auto()
    auto_config = enum.auto()
    data = enum.auto()
    system_data = enum.auto()
    cache = enum.auto()
    download = enum.auto()
    runtime = enum.auto()
    config_py = enum.auto()


APPNAME = 'qutebrowser'


class EmptyValueError(Exception):

    """Error raised when QStandardPaths returns an empty value."""


@contextlib.contextmanager
def _unset_organization() -> Iterator[None]:
    """Temporarily unset QApplication.organizationName().

    This is primarily needed in config.py.
    """
    qapp = QApplication.instance()
    if qapp is not None:
        orgname = qapp.organizationName()
        qapp.setOrganizationName(None)  # type: ignore[arg-type]
    try:
        yield
    finally:
        if qapp is not None:
            qapp.setOrganizationName(orgname)


def _init_config(args: Optional[argparse.Namespace]) -> None:
    """Initialize the location for configs."""
    typ = QStandardPaths.ConfigLocation
    path = _from_args(typ, args)
    if path is None:
        if utils.is_windows:
            app_data_path = _writable_location(
                QStandardPaths.AppDataLocation)
            path = os.path.join(app_data_path, 'config')
        else:
            path = _writable_location(typ)

    _create(path)
    _locations[_Location.config] = path
    _locations[_Location.auto_config] = path

    # Override the normal (non-auto) config on macOS
    if utils.is_mac:
        path = _from_args(typ, args)
        if path is None:  # pragma: no branch
            path = os.path.expanduser('~/.' + APPNAME)
            _create(path)
            _locations[_Location.config] = path

    config_py_file = os.path.join(_locations[_Location.config], 'config.py')
    if getattr(args, 'config_py', None) is not None:
        assert args is not None
        config_py_file = os.path.abspath(args.config_py)
    _locations[_Location.config_py] = config_py_file


def config(auto: bool = False) -> str:
    """Get the location for the config directory.

    If auto=True is given, get the location for the autoconfig.yml directory,
    which is different on macOS.
    """
    if auto:
        return _locations[_Location.auto_config]
    return _locations[_Location.config]


def config_py() -> str:
    """Get the location for config.py.

    Usually, config.py is in standarddir.config(), but this can be overridden
    with the --config-py argument.
    """
    return _locations[_Location.config_py]


def _init_data(args: Optional[argparse.Namespace]) -> None:
    """Initialize the location for data."""
    typ = QStandardPaths.AppDataLocation
    path = _from_args(typ, args)
    if path is None:
        if utils.is_windows:
            app_data_path = _writable_location(typ)  # same location as config
            path = os.path.join(app_data_path, 'data')
        elif sys.platform.startswith('haiku'):
            # HaikuOS returns an empty value for AppDataLocation
            config_path = _writable_location(QStandardPaths.ConfigLocation)
            path = os.path.join(config_path, 'data')
        else:
            path = _writable_location(typ)

    _create(path)
    _locations[_Location.data] = path

    # system_data
    _locations.pop(_Location.system_data, None)  # Remove old state
    if utils.is_linux:
        path = '/usr/share/' + APPNAME
        if os.path.exists(path):
            _locations[_Location.system_data] = path


def data(system: bool = False) -> str:
    """Get the data directory.

    If system=True is given, gets the system-wide (probably non-writable) data
    directory.
    """
    if system:
        try:
            return _locations[_Location.system_data]
        except KeyError:
            pass
    return _locations[_Location.data]


def _init_cache(args: Optional[argparse.Namespace]) -> None:
    """Initialize the location for the cache."""
    typ = QStandardPaths.CacheLocation
    path = _from_args(typ, args)
    if path is None:
        if utils.is_windows:
            # Local, not Roaming!
            data_path = _writable_location(QStandardPaths.AppLocalDataLocation)
            path = os.path.join(data_path, 'cache')
        else:
            path = _writable_location(typ)

    _create(path)
    _locations[_Location.cache] = path


def cache() -> str:
    return _locations[_Location.cache]


def _init_download(args: Optional[argparse.Namespace]) -> None:
    """Initialize the location for downloads.

    Note this is only the default directory as found by Qt.
    Therefore, we also don't create it.
    """
    typ = QStandardPaths.DownloadLocation
    path = _from_args(typ, args)
    if path is None:
        path = _writable_location(typ)
    _locations[_Location.download] = path


def download() -> str:
    return _locations[_Location.download]


def _init_runtime(args: Optional[argparse.Namespace]) -> None:
    """Initialize location for runtime data."""
    if utils.is_mac or utils.is_windows:
        # RuntimeLocation is a weird path on macOS and Windows.
        typ = QStandardPaths.TempLocation
    else:
        typ = QStandardPaths.RuntimeLocation

    path = _from_args(typ, args)
    if path is None:
        try:
            path = _writable_location(typ)
        except EmptyValueError:
            # Fall back to TempLocation when RuntimeLocation is misconfigured
            if typ == QStandardPaths.TempLocation:
                raise
            path = _writable_location(  # pragma: no cover
                QStandardPaths.TempLocation)

        # This is generic, but per-user.
        # _writable_location makes sure we have a qutebrowser-specific subdir.
        #
        # For TempLocation:
        # "The returned value might be application-specific, shared among
        # other applications for this user, or even system-wide."
        #
        # Unfortunately this path could get too long for sockets (which have a
        # maximum length of 104 chars), so we don't add the username here...

        if version.is_flatpak():
            # We need a path like
            # /run/user/1000/app/org.qutebrowser.qutebrowser rather than
            # /run/user/1000/qutebrowser on Flatpak, since that's bind-mounted
            # in a way that it is accessible by any other qutebrowser
            # instances.
            *parts, app_name = os.path.split(path)
            assert app_name == APPNAME, app_name
            flatpak_id = version.flatpak_id()
            assert flatpak_id is not None
            path = os.path.join(*parts, 'app', flatpak_id)

    _create(path)
    _locations[_Location.runtime] = path


def runtime() -> str:
    return _locations[_Location.runtime]


def _writable_location(typ: QStandardPaths.StandardLocation) -> str:
    """Wrapper around QStandardPaths.writableLocation.

    Arguments:
        typ: A QStandardPaths::StandardLocation member.
    """
    typ_str = debug.qenum_key(QStandardPaths, typ)

    # Types we are sure we handle correctly below.
    assert typ in [
        QStandardPaths.ConfigLocation, QStandardPaths.AppLocalDataLocation,
        QStandardPaths.CacheLocation, QStandardPaths.DownloadLocation,
        QStandardPaths.RuntimeLocation, QStandardPaths.TempLocation,
        QStandardPaths.AppDataLocation], typ_str

    with _unset_organization():
        path = QStandardPaths.writableLocation(typ)

    log.misc.debug("writable location for {}: {}".format(typ_str, path))
    if not path:
        raise EmptyValueError("QStandardPaths returned an empty value!")

    # Qt seems to use '/' as path separator even on Windows...
    path = path.replace('/', os.sep)

    # Add the application name to the given path if needed.
    # This is in order for this to work without a QApplication (and thus
    # QStandardsPaths not knowing the application name).
    if (typ != QStandardPaths.DownloadLocation and
            path.split(os.sep)[-1] != APPNAME):
        path = os.path.join(path, APPNAME)

    return path


def _from_args(
        typ: QStandardPaths.StandardLocation,
        args: Optional[argparse.Namespace]
) -> Optional[str]:
    """Get the standard directory from an argparse namespace.

    Return:
        The overridden path, or None if there is no override.
    """
    basedir_suffix = {
        QStandardPaths.ConfigLocation: 'config',
        QStandardPaths.AppDataLocation: 'data',
        QStandardPaths.AppLocalDataLocation: 'data',
        QStandardPaths.CacheLocation: 'cache',
        QStandardPaths.DownloadLocation: 'download',
        QStandardPaths.RuntimeLocation: 'runtime',
    }

    if getattr(args, 'basedir', None) is None:
        return None
    assert args is not None

    try:
        suffix = basedir_suffix[typ]
    except KeyError:  # pragma: no cover
        return None
    return os.path.abspath(os.path.join(args.basedir, suffix))


def _create(path: str) -> None:
    """Create the `path` directory.

    From the XDG basedir spec:
        If, when attempting to write a file, the destination directory is
        non-existent an attempt should be made to create it with permission
        0700. If the destination directory exists already the permissions
        should not be changed.
    """
    if APPNAME == 'qute_test' and path.startswith('/home'):  # pragma: no cover
        for k, v in os.environ.items():
            if k == 'HOME' or k.startswith('XDG_'):
                log.init.debug(f"{k} = {v}")
        raise Exception("Trying to create directory inside /home during "
                        "tests, this should not happen.")
    os.makedirs(path, 0o700, exist_ok=True)


def _init_dirs(args: argparse.Namespace = None) -> None:
    """Create and cache standard directory locations.

    Mainly in a separate function because we need to call it in tests.
    """
    _init_config(args)
    _init_data(args)
    _init_cache(args)
    _init_download(args)
    _init_runtime(args)


def init(args: Optional[argparse.Namespace]) -> None:
    """Initialize all standard dirs."""
    if args is not None:
        # args can be None during tests
        log.init.debug("Base directory: {}".format(args.basedir))

    _init_dirs(args)
    _init_cachedir_tag()


def _init_cachedir_tag() -> None:
    """Create CACHEDIR.TAG if it doesn't exist.

    See https://bford.info/cachedir/
    """
    cachedir_tag = os.path.join(cache(), 'CACHEDIR.TAG')
    if not os.path.exists(cachedir_tag):
        try:
            with open(cachedir_tag, 'w', encoding='utf-8') as f:
                f.write("Signature: 8a477f597d28d172789f06886806bc55\n")
                f.write("# This file is a cache directory tag created by "
                        "qutebrowser.\n")
                f.write("# For information about cache directory tags, see:\n")
                f.write("#  https://bford.info/cachedir/\n")
        except OSError:
            log.init.exception("Failed to create CACHEDIR.TAG")
