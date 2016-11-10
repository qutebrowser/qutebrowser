# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Custom useful data types.

Module attributes:
    _UNSET: Used as default argument in the constructor so default can be None.
"""

import operator
import collections.abc
import enum as pyenum

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QTimer

from qutebrowser.utils import log, qtutils, utils


_UNSET = object()


def enum(name, items, start=1, is_int=False):
    """Factory for simple enumerations.

    Args:
        name: Name of the enum
        items: Iterable of items to be sequentially enumerated.
        start: The number to use for the first value.
               We use 1 as default so enum members are always True.
        is_init: True if the enum should be a Python IntEnum
    """
    enums = [(v, i) for (i, v) in enumerate(items, start)]
    base = pyenum.IntEnum if is_int else pyenum.Enum
    base = pyenum.unique(base)
    return base(name, enums)


class NeighborList(collections.abc.Sequence):

    """A list of items which saves its current position.

    Class attributes:
        Modes: Different modes, see constructor documentation.

    Attributes:
        fuzzyval: The value which is currently set but not in the list.
        _idx: The current position in the list.
        _items: A list of all items, accessed through item property.
        _mode: The current mode.
    """

    Modes = enum('Modes', ['edge', 'exception'])

    def __init__(self, items=None, default=_UNSET, mode=Modes.exception):
        """Constructor.

        Args:
            items: The list of items to iterate in.
            _default: The initially selected value.
            _mode: Behavior when the first/last item is reached.
                   Modes.edge: Go to the first/last item
                   Modes.exception: Raise an IndexError.
        """
        if not isinstance(mode, self.Modes):
            raise TypeError("Mode {} is not a Modes member!".format(mode))
        if items is None:
            self._items = []
        else:
            self._items = list(items)
        self._default = default
        if default is not _UNSET:
            self._idx = self._items.index(default)
        else:
            self._idx = None
        self._mode = mode
        self.fuzzyval = None

    def __getitem__(self, key):
        return self._items[key]

    def __len__(self):
        return len(self._items)

    def __repr__(self):
        return utils.get_repr(self, items=self._items, mode=self._mode,
                              idx=self._idx, fuzzyval=self.fuzzyval)

    def _snap_in(self, offset):
        """Set the current item to the closest item to self.fuzzyval.

        Args:
            offset: negative to get the next smaller item, positive for the
                    next bigger one.

        Return:
            True if the value snapped in (changed),
            False when the value already was in the list.
        """
        op = operator.le if offset < 0 else operator.ge
        items = [(idx, e) for (idx, e) in enumerate(self._items)
                 if op(e, self.fuzzyval)]
        if items:
            item = min(items, key=lambda tpl: abs(self.fuzzyval - tpl[1]))
        else:
            sorted_items = sorted([(idx, e) for (idx, e) in
                                   enumerate(self.items)], key=lambda e: e[1])
            idx = 0 if offset < 0 else -1
            item = sorted_items[idx]
        self._idx = item[0]
        return self.fuzzyval not in self._items

    def _get_new_item(self, offset):
        """Logic for getitem to get the item at offset.

        Args:
            offset: The offset of the current item, relative to the last one.

        Return:
            The new item.
        """
        try:
            if self._idx + offset >= 0:
                new = self._items[self._idx + offset]
            else:
                raise IndexError
        except IndexError:
            if self._mode == self.Modes.edge:
                assert offset != 0
                if offset > 0:
                    new = self.lastitem()
                else:
                    new = self.firstitem()
            elif self._mode == self.Modes.exception:  # pragma: no branch
                raise
        else:
            self._idx += offset
        return new

    @property
    def items(self):
        """Getter for items, which should not be set."""
        return self._items

    def getitem(self, offset):
        """Get the item with a relative position.

        Args:
            offset: The offset of the current item, relative to the last one.

        Return:
            The new item.
        """
        log.misc.debug("{} items, idx {}, offset {}".format(
            len(self._items), self._idx, offset))
        if not self._items:
            raise IndexError("No items found!")
        if self.fuzzyval is not None:
            # Value has been set to something not in the list, so we snap in to
            # the closest value in the right direction and count this as one
            # step towards offset.
            snapped = self._snap_in(offset)
            if snapped and offset > 0:
                offset -= 1
            elif snapped:
                offset += 1
            self.fuzzyval = None
        return self._get_new_item(offset)

    def curitem(self):
        """Get the current item in the list."""
        if self._idx is not None:
            return self._items[self._idx]
        else:
            raise IndexError("No current item!")

    def nextitem(self):
        """Get the next item in the list."""
        return self.getitem(1)

    def previtem(self):
        """Get the previous item in the list."""
        return self.getitem(-1)

    def firstitem(self):
        """Get the first item in the list."""
        if not self._items:
            raise IndexError("No items found!")
        self._idx = 0
        return self.curitem()

    def lastitem(self):
        """Get the last item in the list."""
        if not self._items:
            raise IndexError("No items found!")
        self._idx = len(self._items) - 1
        return self.curitem()

    def reset(self):
        """Reset the position to the default."""
        if self._default is _UNSET:
            raise ValueError("No default set!")
        else:
            self._idx = self._items.index(self._default)
            return self.curitem()


# The mode of a Question.
PromptMode = enum('PromptMode', ['yesno', 'text', 'user_pwd', 'alert',
                                 'download'])


# Where to open a clicked link.
ClickTarget = enum('ClickTarget', ['normal', 'tab', 'tab_bg', 'window',
                                   'hover'])


# Key input modes
KeyMode = enum('KeyMode', ['normal', 'hint', 'command', 'yesno', 'prompt',
                           'insert', 'passthrough', 'caret', 'set_mark',
                           'jump_mark', 'record_macro', 'run_macro'])


# Available command completions
Completion = enum('Completion', ['command', 'section', 'option', 'value',
                                 'helptopic', 'quickmark_by_name',
                                 'bookmark_by_url', 'url', 'tab', 'sessions',
                                 'bind'])


# Exit statuses for errors. Needs to be an int for sys.exit.
Exit = enum('Exit', ['ok', 'reserved', 'exception', 'err_ipc', 'err_init',
                     'err_config', 'err_key_config'], is_int=True, start=0)


# Load status of a tab
LoadStatus = enum('LoadStatus', ['none', 'success', 'success_https', 'error',
                                 'warn', 'loading'])


# Backend of a tab
Backend = enum('Backend', ['QtWebKit', 'QtWebEngine'])
arg2backend = {
    'webkit': Backend.QtWebKit,
    'webengine': Backend.QtWebEngine,
}


# JS world for QtWebEngine
JsWorld = enum('JsWorld', ['main', 'application', 'user', 'jseval'])


MessageLevel = enum('MessageLevel', ['error', 'warning', 'info'])


class Question(QObject):

    """A question asked to the user, e.g. via the status bar.

    Note the creator is responsible for cleaning up the question after it
    doesn't need it anymore, e.g. via connecting Question.completed to
    Question.deleteLater.

    Attributes:
        mode: A PromptMode enum member.
              yesno: A question which can be answered with yes/no.
              text: A question which requires a free text answer.
              user_pwd: A question for a username and password.
        default: The default value.
                 For yesno, None (no default), True or False.
                 For text, a default text as string.
                 For user_pwd, a default username as string.
        title: The question title to show.
        text: The prompt text to display to the user.
        answer: The value the user entered (as password for user_pwd).
        is_aborted: Whether the question was aborted.
        interrupted: Whether the question was interrupted by another one.

    Signals:
        answered: Emitted when the question has been answered by the user.
                  arg: The answer to the question.
        cancelled: Emitted when the question has been cancelled by the user.
        aborted: Emitted when the question was aborted programmatically.
                 In this case, cancelled is not emitted.
        answered_yes: Convenience signal emitted when a yesno question was
                      answered with yes.
        answered_no: Convenience signal emitted when a yesno question was
                     answered with no.
        completed: Emitted when the question was completed in any way.
    """

    answered = pyqtSignal(object)
    cancelled = pyqtSignal()
    aborted = pyqtSignal()
    answered_yes = pyqtSignal()
    answered_no = pyqtSignal()
    completed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = None
        self.default = None
        self.title = None
        self.text = None
        self.answer = None
        self.is_aborted = False
        self.interrupted = False

    def __repr__(self):
        return utils.get_repr(self, title=self.title, text=self.text,
                              mode=self._mode, default=self.default)

    @property
    def mode(self):
        """Getter for mode so we can define a setter."""
        return self._mode

    @mode.setter
    def mode(self, val):
        """Setter for mode to do basic type checking."""
        if not isinstance(val, PromptMode):
            raise TypeError("Mode {} is no PromptMode member!".format(val))
        self._mode = val

    @pyqtSlot()
    def done(self):
        """Must be called when the question was answered completely."""
        self.answered.emit(self.answer)
        if self.mode == PromptMode.yesno:
            if self.answer:
                self.answered_yes.emit()
            else:
                self.answered_no.emit()
        self.completed.emit()

    @pyqtSlot()
    def cancel(self):
        """Cancel the question (resulting from user-input)."""
        self.cancelled.emit()
        self.completed.emit()

    @pyqtSlot()
    def abort(self):
        """Abort the question."""
        if self.is_aborted:
            log.misc.debug("Question was already aborted")
            return
        self.is_aborted = True
        try:
            self.aborted.emit()
            self.completed.emit()
        except TypeError:
            # WORKAROUND
            # We seem to get "pyqtSignal must be bound to a QObject, not
            # 'Question' here, which makes no sense at all..."
            log.misc.exception("Error while aborting question")


class Timer(QTimer):

    """A timer which has a name to show in __repr__ and checks for overflows.

    Attributes:
        _name: The name of the timer.
    """

    def __init__(self, parent=None, name=None):
        super().__init__(parent)
        if name is None:
            self._name = "unnamed"
        else:
            self.setObjectName(name)
            self._name = name

    def __repr__(self):
        return utils.get_repr(self, name=self._name)

    def setInterval(self, msec):
        """Extend setInterval to check for overflows."""
        qtutils.check_overflow(msec, 'int')
        super().setInterval(msec)

    def start(self, msec=None):
        """Extend start to check for overflows."""
        if msec is not None:
            qtutils.check_overflow(msec, 'int')
            super().start(msec)
        else:
            super().start()


class AbstractCertificateErrorWrapper:

    """A wrapper over an SSL/certificate error."""

    def __init__(self, error):
        self._error = error

    def __str__(self):
        raise NotImplementedError

    def __repr__(self):
        raise NotImplementedError

    def is_overridable(self):
        raise NotImplementedError
