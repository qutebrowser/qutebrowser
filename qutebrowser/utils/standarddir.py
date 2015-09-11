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

"""Utilities to get and initialize data/config paths."""

import os
import os.path

from PyQt5.QtCore import QCoreApplication, QStandardPaths

from qutebrowser.utils import log, qtutils


# The argparse namespace passed to init()
_args = None


def config():
    """Convenience function to get the config location."""
    return _get(QStandardPaths.ConfigLocation)


def data():
    """Convenience function to get the data location."""
    return _get(QStandardPaths.DataLocation)


def cache():
    """Convenience function to get the cache location."""
    return _get(QStandardPaths.CacheLocation)


def download():
    """Convenience function to get the download location."""
    return _get(QStandardPaths.DownloadLocation)


def runtime():
    """Convenience function to get the runtime location."""
    return _get(QStandardPaths.RuntimeLocation)


def temp():
    """Convenience function to get the temporary files location."""
    return _get(QStandardPaths.TempLocation)


def _writable_location(typ):
    """Wrapper around QStandardPaths.writableLocation."""
    with qtutils.unset_organization():
        path = QStandardPaths.writableLocation(typ)
    if not path:
        raise ValueError("QStandardPaths returned an empty value!")
    # Qt seems to use '/' as path separator even on Windows...
    path = path.replace('/', os.sep)
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
    # pylint: disable=too-many-return-statements
    typ_to_argparse_arg = {
        QStandardPaths.ConfigLocation: 'confdir',
        QStandardPaths.DataLocation: 'datadir',
        QStandardPaths.CacheLocation: 'cachedir',
    }
    basedir_suffix = {
        QStandardPaths.ConfigLocation: 'config',
        QStandardPaths.DataLocation: 'data',
        QStandardPaths.CacheLocation: 'cache',
        QStandardPaths.DownloadLocation: 'download',
        QStandardPaths.RuntimeLocation: 'runtime',
    }

    if args is None:
        return (False, None)

    if getattr(args, 'basedir', None) is not None:
        basedir = args.basedir
        try:
            suffix = basedir_suffix[typ]
        except KeyError:
            return (False, None)
        return (True, os.path.join(basedir, suffix))

    try:
        argname = typ_to_argparse_arg[typ]
    except KeyError:
        return (False, None)
    arg_value = getattr(args, argname)
    if arg_value is None:
        return (False, None)
    elif arg_value == '':
        return (True, None)
    else:
        return (True, arg_value)


def _get(typ):
    """Get the directory where files of the given type should be written to.

    Args:
        typ: A member of the QStandardPaths::StandardLocation enum,
             see http://doc.qt.io/qt-5/qstandardpaths.html#StandardLocation-enum
    """
    overridden, path = _from_args(typ, _args)
    if not overridden:
        path = _writable_location(typ)
        appname = QCoreApplication.instance().applicationName()

        if (typ == QStandardPaths.ConfigLocation and
                path.split(os.sep)[-1] != appname):
            # WORKAROUND - see
            # https://bugreports.qt.io/browse/QTBUG-38872
            path = os.path.join(path, appname)
        elif typ == QStandardPaths.DataLocation and os.name == 'nt':
            # Under windows, config/data might end up in the same directory.
            data_path = QStandardPaths.writableLocation(
                QStandardPaths.DataLocation)
            config_path = QStandardPaths.writableLocation(
                QStandardPaths.ConfigLocation)
            if data_path == config_path:
                path = os.path.join(path, 'data')
        elif typ == QStandardPaths.TempLocation:
            # "The returned value might be application-specific, shared among
            # other applications for this user, or even system-wide."
            #
            # Unfortunately this path could get too long for IPC sockets, so we
            # don't add the username here...
            subdir = appname
            path = os.path.join(path, subdir)
        elif typ == QStandardPaths.RuntimeLocation:
            # This is generic, but per-user.
            path = os.path.join(path, appname)
    # From the XDG basedir spec:
    #     If, when attempting to write a file, the destination directory is
    #     non-existant an attempt should be made to create it with permission
    #     0700. If the destination directory exists already the permissions
    #     should not be changed.
    if path is not None:
        try:
            os.makedirs(path, 0o700)
        except FileExistsError:
            pass
    return path


def init(args):
    """Initialize all standard dirs."""
    global _args
    _args = args
    _init_cachedir_tag()


def _init_cachedir_tag():
    """Create CACHEDIR.TAG if it doesn't exist.

    See http://www.brynosaurus.com/cachedir/spec.html
    """
    cache_dir = cache()
    if cache_dir is None:
        return
    cachedir_tag = os.path.join(cache_dir, 'CACHEDIR.TAG')
    if not os.path.exists(cachedir_tag):
        try:
            with open(cachedir_tag, 'w', encoding='utf-8') as f:
                f.write("Signature: 8a477f597d28d172789f06886806bc55\n")
                f.write("# This file is a cache directory tag created by "
                        "qutebrowser.\n")
                f.write("# For information about cache directory tags, see:\n")
                f.write("#  http://www.brynosaurus.com/"  # pragma: no branch
                        "cachedir/\n")
        except OSError:
            log.init.exception("Failed to create CACHEDIR.TAG")
