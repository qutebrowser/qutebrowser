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

"""Utilities to get and initialize data/config paths."""

import os
import shutil
import os.path
import contextlib

from PyQt5.QtCore import QStandardPaths
from PyQt5.QtWidgets import QApplication

from qutebrowser.utils import log, debug, usertypes, message, utils

# The cached locations
_locations = {}


Location = usertypes.enum('Location', ['config', 'auto_config',
                                       'data', 'system_data',
                                       'cache', 'download', 'runtime'])


APPNAME = 'qutebrowser'


class EmptyValueError(Exception):

    """Error raised when QStandardPaths returns an empty value."""


@contextlib.contextmanager
def _unset_organization():
    """Temporarily unset QApplication.organizationName().

    This is primarily needed in config.py.
    """
    qapp = QApplication.instance()
    if qapp is not None:
        orgname = qapp.organizationName()
        qapp.setOrganizationName(None)
    try:
        yield
    finally:
        if qapp is not None:
            qapp.setOrganizationName(orgname)


def _init_config(args):
    """Initialize the location for configs."""
    typ = QStandardPaths.ConfigLocation
    overridden, path = _from_args(typ, args)
    if not overridden:
        if utils.is_windows:
            app_data_path = _writable_location(
                QStandardPaths.AppDataLocation)
            path = os.path.join(app_data_path, 'config')
        else:
            path = _writable_location(typ)
    _create(path)
    _locations[Location.config] = path
    _locations[Location.auto_config] = path

    # Override the normal (non-auto) config on macOS
    if utils.is_mac:
        overridden, path = _from_args(typ, args)
        if not overridden:  # pragma: no branch
            path = os.path.expanduser('~/.' + APPNAME)
            _create(path)
            _locations[Location.config] = path


def config(auto=False):
    """Get the location for the config directory.

    If auto=True is given, get the location for the autoconfig.yml directory,
    which is different on macOS.
    """
    if auto:
        return _locations[Location.auto_config]
    return _locations[Location.config]


def _init_data(args):
    """Initialize the location for data."""
    typ = QStandardPaths.DataLocation
    overridden, path = _from_args(typ, args)
    if not overridden:
        if utils.is_windows:
            app_data_path = _writable_location(QStandardPaths.AppDataLocation)
            path = os.path.join(app_data_path, 'data')
        else:
            path = _writable_location(typ)
    _create(path)
    _locations[Location.data] = path

    # system_data
    _locations.pop(Location.system_data, None)  # Remove old state
    if utils.is_linux:
        path = '/usr/share/' + APPNAME
        if os.path.exists(path):
            _locations[Location.system_data] = path


def data(system=False):
    """Get the data directory.

    If system=True is given, gets the system-wide (probably non-writable) data
    directory.
    """
    if system:
        try:
            return _locations[Location.system_data]
        except KeyError:
            pass
    return _locations[Location.data]


def _init_cache(args):
    """Initialize the location for the cache."""
    typ = QStandardPaths.CacheLocation
    overridden, path = _from_args(typ, args)
    if not overridden:
        if utils.is_windows:
            # Local, not Roaming!
            data_path = _writable_location(QStandardPaths.DataLocation)
            path = os.path.join(data_path, 'cache')
        else:
            path = _writable_location(typ)
    _create(path)
    _locations[Location.cache] = path


def cache():
    return _locations[Location.cache]


def _init_download(args):
    """Initialize the location for downloads.

    Note this is only the default directory as found by Qt.
    Therefore, we also don't create it.
    """
    typ = QStandardPaths.DownloadLocation
    overridden, path = _from_args(typ, args)
    if not overridden:
        path = _writable_location(typ)
    _locations[Location.download] = path


def download():
    return _locations[Location.download]


def _init_runtime(args):
    """Initialize location for runtime data."""
    if utils.is_linux:
        typ = QStandardPaths.RuntimeLocation
    else:
        # RuntimeLocation is a weird path on macOS and Windows.
        typ = QStandardPaths.TempLocation

    overridden, path = _from_args(typ, args)

    if not overridden:
        try:
            path = _writable_location(typ)
        except EmptyValueError:
            # Fall back to TempLocation when RuntimeLocation is misconfigured
            if typ == QStandardPaths.TempLocation:
                raise
            path = _writable_location(QStandardPaths.TempLocation)

        # This is generic, but per-user.
        # _writable_location makes sure we have a qutebrowser-specific subdir.
        #
        # For TempLocation:
        # "The returned value might be application-specific, shared among
        # other applications for this user, or even system-wide."
        #
        # Unfortunately this path could get too long for sockets (which have a
        # maximum length of 104 chars), so we don't add the username here...

    _create(path)
    _locations[Location.runtime] = path


def runtime():
    return _locations[Location.runtime]


def _writable_location(typ):
    """Wrapper around QStandardPaths.writableLocation.

    Arguments:
        typ: A QStandardPaths::StandardLocation member.
    """
    typ_str = debug.qenum_key(QStandardPaths, typ)

    # Types we are sure we handle correctly below.
    assert typ in [
        QStandardPaths.ConfigLocation, QStandardPaths.DataLocation,
        QStandardPaths.CacheLocation, QStandardPaths.DownloadLocation,
        QStandardPaths.RuntimeLocation, QStandardPaths.TempLocation,
        # FIXME old Qt
        getattr(QStandardPaths, 'AppDataLocation', object())], typ_str

    with _unset_organization():
        path = QStandardPaths.writableLocation(typ)

    log.misc.debug("writable location for {}: {}".format(typ_str, path))
    if not path:
        raise EmptyValueError("QStandardPaths returned an empty value!")

    # Qt seems to use '/' as path separator even on Windows...
    path = path.replace('/', os.sep)

    # Add the application name to the given path if needed.
    # This is in order for this to work without a QApplication (and thus
    # QStandardsPaths not knowing the application name), as well as a
    # workaround for https://bugreports.qt.io/browse/QTBUG-38872
    if (typ != QStandardPaths.DownloadLocation and
            path.split(os.sep)[-1] != APPNAME):
        path = os.path.join(path, APPNAME)

    return path


def _from_args(typ, args):
    """Get the standard directory from an argparse namespace.

    Args:
        typ: A member of the QStandardPaths::StandardLocation enum
        args: An argparse namespace or None.

    Return:
        A (override, path) tuple.
            override: boolean, if the user did override the path
            path: The overridden path, or None to turn off storage.
    """
    basedir_suffix = {
        QStandardPaths.ConfigLocation: 'config',
        QStandardPaths.DataLocation: 'data',
        QStandardPaths.CacheLocation: 'cache',
        QStandardPaths.DownloadLocation: 'download',
        QStandardPaths.RuntimeLocation: 'runtime',
    }

    if getattr(args, 'basedir', None) is not None:
        basedir = args.basedir

        try:
            suffix = basedir_suffix[typ]
        except KeyError:  # pragma: no cover
            return (False, None)
        return (True, os.path.abspath(os.path.join(basedir, suffix)))
    else:
        return (False, None)


def _create(path):
    """Create the `path` directory.

    From the XDG basedir spec:
        If, when attempting to write a file, the destination directory is
        non-existent an attempt should be made to create it with permission
        0700. If the destination directory exists already the permissions
        should not be changed.
    """
    try:
        os.makedirs(path, 0o700)
    except FileExistsError:
        pass


def _init_dirs(args=None):
    """Create and cache standard directory locations.

    Mainly in a separate function because we need to call it in tests.
    """
    _init_config(args)
    _init_data(args)
    _init_cache(args)
    _init_download(args)
    _init_runtime(args)


def init(args):
    """Initialize all standard dirs."""
    if args is not None:
        # args can be None during tests
        log.init.debug("Base directory: {}".format(args.basedir))

    _init_dirs(args)
    _init_cachedir_tag()
    if args is not None and getattr(args, 'basedir', None) is None:
        if utils.is_mac:  # pragma: no cover
            _move_macos()
        elif utils.is_windows:  # pragma: no cover
            _move_windows()


def _move_macos():
    """Move most config files to new location on macOS."""
    old_config = config(auto=True)  # ~/Library/Preferences/qutebrowser
    new_config = config()  # ~/.qutebrowser
    for f in os.listdir(old_config):
        if f not in ['qsettings', 'autoconfig.yml']:
            _move_data(os.path.join(old_config, f),
                       os.path.join(new_config, f))


def _move_windows():
    """Move the whole qutebrowser directory from Local to Roaming AppData."""
    # %APPDATA%\Local\qutebrowser
    old_appdata_dir = _writable_location(QStandardPaths.DataLocation)
    # %APPDATA%\Roaming\qutebrowser
    new_appdata_dir = _writable_location(QStandardPaths.AppDataLocation)

    # data subfolder
    old_data = os.path.join(old_appdata_dir, 'data')
    new_data = os.path.join(new_appdata_dir, 'data')
    ok = _move_data(old_data, new_data)
    if not ok:  # pragma: no cover
        return

    # config files
    new_config_dir = os.path.join(new_appdata_dir, 'config')
    _create(new_config_dir)
    for f in os.listdir(old_appdata_dir):
        if f != 'cache':
            _move_data(os.path.join(old_appdata_dir, f),
                       os.path.join(new_config_dir, f))


def _init_cachedir_tag():
    """Create CACHEDIR.TAG if it doesn't exist.

    See http://www.brynosaurus.com/cachedir/spec.html
    """
    cachedir_tag = os.path.join(cache(), 'CACHEDIR.TAG')
    if not os.path.exists(cachedir_tag):
        try:
            with open(cachedir_tag, 'w', encoding='utf-8') as f:
                f.write("Signature: 8a477f597d28d172789f06886806bc55\n")
                f.write("# This file is a cache directory tag created by "
                        "qutebrowser.\n")
                f.write("# For information about cache directory tags, see:\n")
                f.write("#  http://www.brynosaurus.com/"
                        "cachedir/\n")
        except OSError:
            log.init.exception("Failed to create CACHEDIR.TAG")


def _move_data(old, new):
    """Migrate data from an old to a new directory.

    If the old directory does not exist, the migration is skipped.
    If the new directory already exists, an error is shown.

    Return: True if moving succeeded, False otherwise.
    """
    if not os.path.exists(old):
        return False

    log.init.debug("Migrating data from {} to {}".format(old, new))

    if os.path.exists(new):
        if not os.path.isdir(new) or os.listdir(new):
            message.error("Failed to move data from {} as {} is non-empty!"
                          .format(old, new))
            return False
        os.rmdir(new)

    try:
        shutil.move(old, new)
    except OSError as e:
        message.error("Failed to move data from {} to {}: {}".format(
            old, new, e))
        return False

    return True
