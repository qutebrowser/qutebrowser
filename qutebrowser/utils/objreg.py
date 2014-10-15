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

from PyQt5.QtCore import QObject, QTimer

from qutebrowser.utils import log


class UnsetObject:

    """Class for an unset object.

    Only used (rather than object) so we can tell pylint to shut up about it.
    """

    __slots__ = ()


class RegistryUnavailableError(Exception):

    """Exception raised when a certain registry does not exist yet."""

    pass


_UNSET = UnsetObject()


class ObjectRegistry(collections.UserDict):

    """A registry of long-living objects in qutebrowser.

    Inspired by the eric IDE code (E5Gui/E5Application.py).
    """

    def __setitem__(self, name, obj):
        """Register an object in the object registry.

        Sets a slot to remove QObjects when they are destroyed.
        """
        if name is None:
            raise TypeError("Registering '{}' with name 'None'!".format(obj))
        if obj is None:
            raise TypeError("Registering object None with name '{}'!".format(
                name))
        if isinstance(obj, QObject):
            obj.destroyed.connect(functools.partial(self.on_destroyed, name))
        super().__setitem__(name, obj)

    def on_destroyed(self, name):
        """Schedule removing of a destroyed QObject.

        We don't remove the destroyed object immediately because it might still
        be destroying its children, which might still use the object
        registry.
        """
        log.misc.debug("schedule removal: {}".format(name))
        QTimer.singleShot(0, functools.partial(self._on_destroyed, name))

    def _on_destroyed(self, name):
        """Remove a destroyed QObject."""
        log.misc.debug("removed: {}".format(name))
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


# The registry for global objects
global_registry = ObjectRegistry()
# The window registry.
window_registry = ObjectRegistry()


def _get_tab_registry(win_id, tab_id):
    """Get the registry of a tab."""
    if tab_id is None:
        tab_id = 'current'
    if tab_id == 'current' and win_id is None:
        app = get('app')
        window = app.activeWindow()
        if window is None or not hasattr(window, 'win_id'):
            raise RegistryUnavailableError('tab')
        win_id = window.win_id
    elif win_id is not None:
        window = window_registry[win_id]

    if tab_id == 'current':
        tabbed_browser = get('tabbed-browser', scope='window', window=win_id)
        tab = tabbed_browser.currentWidget()
        if tab is None:
            raise RegistryUnavailableError('window')
        tab_id = tab.tab_id
    tab_registry = get('tab-registry', scope='window', window=win_id)
    try:
        return tab_registry[tab_id].registry
    except AttributeError:
        raise RegistryUnavailableError('tab')


def _get_window_registry(window):
    """Get the registry of a window."""
    if window is None:
        raise TypeError("window is None with scope window!")
    if window == 'current':
        app = get('app')
        win = app.activeWindow()
        if win is None or not hasattr(win, 'win_id'):
            raise RegistryUnavailableError('window')
    elif window == 'last-focused':
        try:
            win = get('last-focused-main-window')
        except KeyError:
            try:
                win = get('last-main-window')
            except KeyError:
                raise RegistryUnavailableError('window')
        assert hasattr(win, 'registry')
    else:
        try:
            win = window_registry[window]
        except KeyError:
            raise RegistryUnavailableError('window')
    try:
        return win.registry
    except AttributeError:
        raise RegistryUnavailableError('window')


def _get_registry(scope, window=None, tab=None):
    """Get the correct registry for a given scope."""
    if window is not None and scope not in ('window', 'tab'):
        raise TypeError("window is set with scope {}".format(scope))
    if tab is not None and scope != 'tab':
        raise TypeError("tab is set with scope {}".format(scope))
    if scope == 'global':
        return global_registry
    elif scope == 'tab':
        return _get_tab_registry(window, tab)
    elif scope == 'window':
        return _get_window_registry(window)
    else:
        raise ValueError("Invalid scope '{}'!".format(scope))


def get(name, default=_UNSET, scope='global', window=None, tab=None):
    """Helper function to get an object.

    Args:
        default: A default to return if the object does not exist.
    """
    reg = _get_registry(scope, window, tab)
    try:
        return reg[name]
    except KeyError:
        if default is not _UNSET:
            return default
        else:
            raise


def register(name, obj, update=False, scope=None, registry=None, window=None,
             tab=None):
    """Helper function to register an object.

    Args:
        name: The name the object will be registered as.
        obj: The object to register.
        update: If True, allows to update an already registered object.
    """
    if scope is not None and registry is not None:
        raise ValueError("scope ({}) and registry ({}) can't be given at the "
                         "same time!".format(scope, registry))
    if registry is not None:
        reg = registry
    else:
        if scope is None:
            scope = 'global'
        reg = _get_registry(scope, window, tab)
    if not update and name in reg:
        raise KeyError("Object '{}' is already registered ({})!".format(
                       name, repr(reg[name])))
    reg[name] = obj


def delete(name, scope='global', window=None, tab=None):
    """Helper function to unregister an object."""
    reg = _get_registry(scope, window, tab)
    del reg[name]


def dump_objects():
    """Get all registered objects in all registries as a string."""
    blocks = []
    lines = []
    blocks.append(('global', global_registry.dump_objects()))
    for win_id in window_registry:
        registry = _get_registry('window', window=win_id)
        blocks.append(('window-{}'.format(win_id), registry.dump_objects()))
        tab_registry = get('tab-registry', scope='window', window=win_id)
        for tab_id, tab in tab_registry.items():
            dump = tab.registry.dump_objects()
            data = ['    ' + line for line in dump]
            blocks.append(('    tab-{}'.format(tab_id), data))
    for name, data in blocks:
        lines.append("")
        lines.append("{} object registry - {} objects:".format(
            name, len(data)))
        for line in data:
            lines.append("    {}".format(line))
    return lines
