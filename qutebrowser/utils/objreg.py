# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""The global object registry and related utility functions."""


import collections
import functools

from PyQt5.QtCore import QCoreApplication, QObject


_UNSET = object()


class ObjectRegistry(collections.UserDict):

    """A registry of long-living objects in qutebrowser.

    Inspired by the eric IDE code (E5Gui/E5Application.py).
    """

    def __setitem__(self, name, obj):
        """Register an object in the object registry.

        Sets a slot to remove QObjects when they are destroyed.
        """
        if isinstance(obj, QObject):
            obj.destroyed.connect(functools.partial(self.on_destroyed, name))
        super().__setitem__(name, obj)

    def on_destroyed(self, name):
        """Remove a destroyed QObject."""
        try:
            del self[name]
        except KeyError:
            pass

    def dump_objects(self):
        """Dump all objects as a list of strings."""
        lines = []
        for name, obj in self.data.items():
            lines.append("{}: {}".format(name, repr(obj)))
        return lines


def get(name, default=_UNSET):
    """Helper function to get an object.

    Args:
        default: A default to return if the object does not exist.
    """
    try:
        return QCoreApplication.instance().registry[name]
    except KeyError:
        if default is not _UNSET:
            return default
        else:
            raise


def register(name, obj, update=False):
    """Helper function to register an object.

    Args:
        name: The name the object will be registered as.
        obj: The object to register.
        update: If True, allows to update an already registered object.
    """
    registry = QCoreApplication.instance().registry
    if not update and name in registry:
        raise KeyError("Object '{}' is already registered ({})!".format(
                       name, repr(registry[name])))
    registry[name] = obj


def delete(name):
    """Helper function to unregister an object."""
    del QCoreApplication.instance().registry[name]
