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

from qutebrowser.utils import log


def _writable_location(typ):
    """Wrapper around QStandardPaths.writableLocation."""
    qapp = QCoreApplication.instance()
    orgname = qapp.organizationName()
    # We need to temporarily unset the organisationname here since the
    # webinspector wants it to be set to store its persistent data correctly,
    # but we don't want that to happen.
    qapp.setOrganizationName(None)
    try:
        path = QStandardPaths.writableLocation(typ)
    finally:
        qapp.setOrganizationName(orgname)
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
            path: The overriden path, or None to turn off storage.
    """
    typ_to_argparse_arg = {
        QStandardPaths.ConfigLocation: 'confdir'
    }
    if args is None:
        return (False, None)
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


def get(typ, args=None):
    """Get the directory where files of the given type should be written to.

    Args:
        typ: A member of the QStandardPaths::StandardLocation enum,
             see http://qt-project.org/doc/qt-5/qstandardpaths.html#StandardLocation-enum
        args: An argparse namespace which could be used to override the
              locations.
    """
    overridden, path = _from_args(typ, args)
    if not overridden:
        path = _writable_location(typ)
        appname = QCoreApplication.instance().applicationName()
        if (typ == QStandardPaths.ConfigLocation and
                path.split(os.sep)[-1] != appname):
            # WORKAROUND - see
            # https://bugreports.qt-project.org/browse/QTBUG-38872
            path = os.path.join(path, appname)
        if typ == QStandardPaths.DataLocation and os.name == 'nt':
            # Under windows, config/data might end up in the same directory.
            data_path = QStandardPaths.writableLocation(
                QStandardPaths.DataLocation)
            config_path = QStandardPaths.writableLocation(
                QStandardPaths.ConfigLocation)
            if data_path == config_path:
                path = os.path.join(path, 'data')
    if path is not None and not os.path.exists(path):
        os.makedirs(path, 0o700)
    return path


def init():
    """Initialize all standard dirs."""
    config_dir = get(QStandardPaths.ConfigLocation)
    data_dir = get(QStandardPaths.DataLocation)
    cache_dir = get(QStandardPaths.CacheLocation)
    # From the XDG basedir spec:
    #     If, when attempting to write a file, the destination directory is
    #     non-existant an attempt should be made to create it with permission
    #     0700. If the destination directory exists already the permissions
    #     should not be changed.
    #
    # This is slightly wrong according to the standard as we ensure these paths
    # exists while initializing, not when writing the file - but practicality
    # beats purity.
    for path in (config_dir, data_dir, cache_dir):
        if path is not None and not os.path.exists(path):
            os.makedirs(path, 0o700)
    # http://www.brynosaurus.com/cachedir/spec.html
    cachedir_tag = os.path.join(cache_dir, 'CACHEDIR.TAG')
    if not os.path.exists(cachedir_tag):
        try:
            with open(cachedir_tag, 'w', encoding='utf-8') as f:
                f.write("Signature: 8a477f597d28d172789f06886806bc55\n")
                f.write("# This file is a cache directory tag created by "
                        "qutebrowser.\n")
                f.write("# For information about cache directory tags, see:\n")
                f.write("#  http://www.brynosaurus.com/cachedir/\n")
        except OSError:
            log.misc.exception("Failed to create CACHEDIR.TAG")
