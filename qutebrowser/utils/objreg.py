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

"""The global object registry and related utility functions."""


import collections
import functools
import typing

from PyQt5.QtCore import QObject, QTimer
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QWidget  # pylint: disable=unused-import

from qutebrowser.utils import log, usertypes
if typing.TYPE_CHECKING:
    from qutebrowser.mainwindow import mainwindow


_WindowTab = typing.Union[str, int, None]


class RegistryUnavailableError(Exception):

    """Exception raised when a certain registry does not exist yet."""


class NoWindow(Exception):

    """Exception raised by last_window if no window is available."""


class CommandOnlyError(Exception):

    """Raised when an object is requested which is used for commands only."""


_IndexType = typing.Union[str, int]


class ObjectRegistry(collections.UserDict):

    """A registry of long-living objects in qutebrowser.

    Inspired by the eric IDE code (E5Gui/E5Application.py).

    Attributes:
        _partial_objs: A dictionary of the connected partial objects.
        command_only: Objects which are only registered for commands.
    """

    def __init__(self) -> None:
        super().__init__()
        self._partial_objs = {
        }  # type: typing.MutableMapping[_IndexType, typing.Callable[[], None]]
        self.command_only = []  # type: typing.MutableSequence[str]

    def __setitem__(self, name: _IndexType, obj: typing.Any) -> None:
        """Register an object in the object registry.

        Sets a slot to remove QObjects when they are destroyed.
        """
        if name is None:
            raise TypeError("Registering '{}' with name 'None'!".format(obj))
        if obj is None:
            raise TypeError("Registering object None with name '{}'!".format(
                name))

        self._disconnect_destroyed(name)

        if isinstance(obj, QObject):
            func = functools.partial(self.on_destroyed, name)
            obj.destroyed.connect(func)
            self._partial_objs[name] = func

        super().__setitem__(name, obj)

    def __delitem__(self, name: str) -> None:
        """Extend __delitem__ to disconnect the destroyed signal."""
        self._disconnect_destroyed(name)
        super().__delitem__(name)

    def _disconnect_destroyed(self, name: _IndexType) -> None:
        """Disconnect the destroyed slot if it was connected."""
        try:
            partial_objs = self._partial_objs
        except AttributeError:
            # This sometimes seems to happen on Travis during
            # test_history.test_adding_item_during_async_read
            # and I have no idea why...
            return
        if name in partial_objs:
            func = partial_objs[name]
            try:
                self[name].destroyed.disconnect(func)
            except RuntimeError:
                # If C++ has deleted the object, the slot is already
                # disconnected.
                pass
            del partial_objs[name]

    def on_destroyed(self, name: str) -> None:
        """Schedule removing of a destroyed QObject.

        We don't remove the destroyed object immediately because it might still
        be destroying its children, which might still use the object
        registry.
        """
        log.destroy.debug("schedule removal: {}".format(name))
        QTimer.singleShot(0, functools.partial(self._on_destroyed, name))

    def _on_destroyed(self, name: str) -> None:
        """Remove a destroyed QObject."""
        log.destroy.debug("removed: {}".format(name))
        if not hasattr(self, 'data'):
            # This sometimes seems to happen on Travis during
            # test_history.test_adding_item_during_async_read
            # and I have no idea why...
            return
        try:
            del self[name]
            del self._partial_objs[name]
        except KeyError:
            pass

    def dump_objects(self) -> typing.Sequence[str]:
        """Dump all objects as a list of strings."""
        lines = []
        for name, obj in self.data.items():
            try:
                obj_repr = repr(obj)
            except RuntimeError:
                # Underlying object deleted probably
                obj_repr = '<deleted>'
            suffix = (" (for commands only)" if name in self.command_only
                      else "")
            lines.append("{}: {}{}".format(name, obj_repr, suffix))
        return lines


# The registry for global objects
global_registry = ObjectRegistry()
# The window registry.
window_registry = ObjectRegistry()


def _get_tab_registry(win_id: _WindowTab,
                      tab_id: _WindowTab) -> ObjectRegistry:
    """Get the registry of a tab."""
    if tab_id is None:
        raise ValueError("Got tab_id None (win_id {})".format(win_id))
    if tab_id == 'current' and win_id is None:
        window = QApplication.activeWindow()  # type: typing.Optional[QWidget]
        if window is None or not hasattr(window, 'win_id'):
            raise RegistryUnavailableError('tab')
        win_id = window.win_id
    elif win_id is None:
        raise TypeError("window is None with scope tab!")

    if tab_id == 'current':
        tabbed_browser = get('tabbed-browser', scope='window', window=win_id)
        tab = tabbed_browser.widget.currentWidget()
        if tab is None:
            raise RegistryUnavailableError('window')
        tab_id = tab.tab_id
    tab_registry = get('tab-registry', scope='window', window=win_id)
    try:
        return tab_registry[tab_id].registry
    except AttributeError:
        raise RegistryUnavailableError('tab')


def _get_window_registry(window: _WindowTab) -> ObjectRegistry:
    """Get the registry of a window."""
    if window is None:
        raise TypeError("window is None with scope window!")
    try:
        if window == 'current':
            win = QApplication.activeWindow()  # type: typing.Optional[QWidget]
        elif window == 'last-focused':
            win = last_focused_window()
        else:
            win = window_registry[window]
    except (KeyError, NoWindow):
        win = None

    if win is None:
        raise RegistryUnavailableError('window')

    try:
        return win.registry
    except AttributeError:
        raise RegistryUnavailableError('window')


def _get_registry(scope: str,
                  window: _WindowTab = None,
                  tab: _WindowTab = None) -> ObjectRegistry:
    """Get the correct registry for a given scope."""
    if window is not None and scope not in ['window', 'tab']:
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


def get(name: str,
        default: typing.Any = usertypes.UNSET,
        scope: str = 'global',
        window: _WindowTab = None,
        tab: _WindowTab = None,
        from_command: bool = False) -> typing.Any:
    """Helper function to get an object.

    Args:
        default: A default to return if the object does not exist.
    """
    reg = _get_registry(scope, window, tab)
    if name in reg.command_only and not from_command:
        raise CommandOnlyError("{} is only registered for commands"
                               .format(name))

    try:
        return reg[name]
    except KeyError:
        if default is not usertypes.UNSET:
            return default
        else:
            raise


def register(name: str,
             obj: typing.Any,
             update: bool = False,
             scope: str = None,
             registry: ObjectRegistry = None,
             window: _WindowTab = None,
             tab: _WindowTab = None,
             command_only: bool = False) -> None:
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

    if command_only:
        reg.command_only.append(name)


def delete(name: str,
           scope: str = 'global',
           window: _WindowTab = None,
           tab: _WindowTab = None) -> None:
    """Helper function to unregister an object."""
    reg = _get_registry(scope, window, tab)
    del reg[name]


def dump_objects() -> typing.Sequence[str]:
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
    for name, block_data in blocks:
        lines.append("")
        lines.append("{} object registry - {} objects:".format(
            name, len(block_data)))
        for line in block_data:
            lines.append("    {}".format(line))
    return lines


def last_visible_window() -> 'mainwindow.MainWindow':
    """Get the last visible window, or the last focused window if none."""
    try:
        return get('last-visible-main-window')
    except KeyError:
        return last_focused_window()


def last_focused_window() -> 'mainwindow.MainWindow':
    """Get the last focused window, or the last window if none."""
    try:
        return get('last-focused-main-window')
    except KeyError:
        return window_by_index(-1)


def window_by_index(idx: int) -> 'mainwindow.MainWindow':
    """Get the Nth opened window object."""
    if not window_registry:
        raise NoWindow()
    key = sorted(window_registry)[idx]
    return window_registry[key]
