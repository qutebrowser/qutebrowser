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

"""Message singleton so we don't have to define unneeded signals."""

import datetime
import collections

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject
from PyQt5.QtWidgets import QApplication

from qutebrowser.utils import usertypes, log, objreg, utils


_QUEUED = []
QueuedMsg = collections.namedtuple(
    'QueuedMsg', ['time', 'win_id', 'method_name', 'text', 'args', 'kwargs'])


def _wrapper(win_id, method_name, text, *args, **kwargs):
    """A wrapper which executes the action if possible, and queues it if not.

    It tries to get the message bridge for the given window, and if it's
    unavailable, it queues it.

    Args:
        win_id: The window ID to execute the action in,.
        method_name: The name of the MessageBridge method to call.
        text: The text do display.
        *args/**kwargs: Arguments to pass to the method.
    """
    msg = QueuedMsg(time=datetime.datetime.now(), win_id=win_id,
                    method_name=method_name, text=text, args=args,
                    kwargs=kwargs)
    try:
        bridge = _get_bridge(win_id)
    except objreg.RegistryUnavailableError:
        if win_id == 'current':
            log.message.debug("Queueing {} for current window".format(
                method_name))
            _QUEUED.append(msg)
        else:
            raise
    else:
        from qutebrowser.config import config
        win = QApplication.instance().activeWindow()
        window_focused = (win is not None and
                          win in objreg.window_registry.values() and
                          win.win_id == win_id)
        if (config.get('ui', 'message-unfocused') or
                method_name not in ('error', 'warning', 'info') or
                window_focused):
            getattr(bridge, method_name)(text, *args, **kwargs)
        else:
            log.message.debug("Queueing {} for window {}".format(
                method_name, win_id))
            _QUEUED.append(msg)


def _get_bridge(win_id):
    """Get the correct MessageBridge instance for a window."""
    try:
        int(win_id)
    except ValueError:
        if win_id == 'current':
            pass
        else:
            raise ValueError("Invalid window id {} - needs to be 'current' or "
                             "a valid integer!".format(win_id))
    return objreg.get('message-bridge', scope='window', window=win_id)


@pyqtSlot()
def on_focus_changed():
    """Show queued messages when a new window has been focused.

    Gets called when a new window has been focused.
    """
    while _QUEUED:
        msg = _QUEUED.pop()
        delta = datetime.datetime.now() - msg.time
        log.message.debug("Handling queued {} for window {}, delta {}".format(
            msg.method_name, msg.win_id, delta))
        try:
            bridge = _get_bridge(msg.win_id)
        except objreg.RegistryUnavailableError:
            # Non-mainwindow window focused.
            _QUEUED.append(msg)
            return
        if delta.total_seconds() < 1:
            text = msg.text
        else:
            text = '[{} ago] {}'.format(utils.format_timedelta(delta),
                                        msg.text)
        getattr(bridge, msg.method_name)(text, *msg.args, **msg.kwargs)


def error(win_id, message, immediately=False):
    """Convienience function to display an error message in the statusbar.

    Args:
        win_id: The ID of the window which is calling this function.
        others: See MessageBridge.error.
    """
    _wrapper(win_id, 'error', message, immediately)


def warning(win_id, message, immediately=False):
    """Convienience function to display a warning message in the statusbar.

    Args:
        win_id: The ID of the window which is calling this function.
        others: See MessageBridge.warning.
    """
    _wrapper(win_id, 'warning', message, immediately)


def info(win_id, message, immediately=True):
    """Convienience function to display an info message in the statusbar.

    Args:
        win_id: The ID of the window which is calling this function.
        others: See MessageBridge.info.
    """
    _wrapper(win_id, 'info', message, immediately)


def set_cmd_text(win_id, txt):
    """Convienience function to Set the statusbar command line to a text."""
    _wrapper(win_id, 'set_cmd_text', txt)


def ask(win_id, message, mode, default=None):
    """Ask a modular question in the statusbar (blocking).

    Args:
        win_id: The ID of the window which is calling this function.
        message: The message to display to the user.
        mode: A PromptMode.
        default: The default value to display.

    Return:
        The answer the user gave or None if the prompt was cancelled.
    """
    q = usertypes.Question()
    q.text = message
    q.mode = mode
    q.default = default
    _get_bridge(win_id).ask(q, blocking=True)
    q.deleteLater()
    return q.answer


def alert(win_id, message):
    """Display an alert which needs to be confirmed.

    Args:
        win_id: The ID of the window which is calling this function.
        message: The message to show.
    """
    q = usertypes.Question()
    q.text = message
    q.mode = usertypes.PromptMode.alert
    _wrapper(win_id, 'ask', q, blocking=True)
    q.deleteLater()


def ask_async(win_id, message, mode, handler, default=None):
    """Ask an async question in the statusbar.

    Args:
        win_id: The ID of the window which is calling this function.
        message: The message to display to the user.
        mode: A PromptMode.
        handler: The function to get called with the answer as argument.
        default: The default value to display.
    """
    if not isinstance(mode, usertypes.PromptMode):
        raise TypeError("Mode {} is no PromptMode member!".format(mode))
    q = usertypes.Question()
    q.text = message
    q.mode = mode
    q.default = default
    q.answered.connect(handler)
    q.completed.connect(q.deleteLater)
    _wrapper(win_id, 'ask', q, blocking=False)


def confirm_async(win_id, message, yes_action, no_action=None, default=None):
    """Ask a yes/no question to the user and execute the given actions.

    Args:
        win_id: The ID of the window which is calling this function.
        message: The message to display to the user.
        yes_action: Callable to be called when the user answered yes.
        no_action: Callable to be called when the user answered no.
        default: True/False to set a default value, or None.
    """
    q = usertypes.Question()
    q.text = message
    q.mode = usertypes.PromptMode.yesno
    q.default = default
    q.answered_yes.connect(yes_action)
    if no_action is not None:
        q.answered_no.connect(no_action)
    q.completed.connect(q.deleteLater)
    _wrapper(win_id, 'ask', q, blocking=False)


class MessageBridge(QObject):

    """Bridge for messages to be shown in the statusbar.

    Signals:
        s_error: Display an error message.
                 arg 0: The error message to show.
                 arg 1: Whether to show it immediately (True) or queue it
                        (False).
        s_info: Display an info message.
                args: See s_error.
        s_warning: Display a warning message.
                args: See s_error.
        s_set_text: Set a persistent text in the statusbar.
                    arg: The text to set.
        s_maybe_reset_text: Reset the text if it hasn't been changed yet.
                            arg: The expected text.
        s_set_cmd_text: Pre-set a text for the commandline prompt.
                        arg: The text to set.

        s_question: Ask a question to the user in the statusbar.
                    arg 0: The Question object to ask.
                    arg 1: Whether to block (True) or ask async (False).

                    IMPORTANT: Slots need to be connected to this signal via a
                               Qt.DirectConnection!
    """

    s_error = pyqtSignal(str, bool)
    s_warning = pyqtSignal(str, bool)
    s_info = pyqtSignal(str, bool)
    s_set_text = pyqtSignal(str)
    s_maybe_reset_text = pyqtSignal(str)
    s_set_cmd_text = pyqtSignal(str)
    s_question = pyqtSignal(usertypes.Question, bool)

    def __repr__(self):
        return utils.get_repr(self)

    def error(self, msg, immediately=False):
        """Display an error in the statusbar.

        Args:
            msg: The message to show.
            immediately: Whether to display the message immediately (True) or
                         queue it for displaying when all other messages are
                         displayed (False). Messages resulting from direct user
                         input should be displayed immediately, all other
                         messages should be queued.
        """
        msg = str(msg)
        log.message.error(msg)
        self.s_error.emit(msg, immediately)

    def warning(self, msg, immediately=False):
        """Display an warning in the statusbar.

        Args:
            msg: The message to show.
            immediately: Whether to display the message immediately (True) or
                         queue it for displaying when all other messages are
                         displayed (False). Messages resulting from direct user
                         input should be displayed immediately, all other
                         messages should be queued.
        """
        msg = str(msg)
        log.message.warning(msg)
        self.s_warning.emit(msg, immediately)

    def info(self, msg, immediately=True):
        """Display an info text in the statusbar.

        Args:
            See error(). Note immediately is True by default, because messages
            do rarely happen without user interaction.
        """
        msg = str(msg)
        log.message.info(msg)
        self.s_info.emit(msg, immediately)

    def set_cmd_text(self, text):
        """Set the command text of the statusbar.

        Args:
            text: The text to set.
        """
        text = str(text)
        log.message.debug(text)
        self.s_set_cmd_text.emit(text)

    def set_text(self, text):
        """Set the normal text of the statusbar.

        Args:
            text: The text to set.
        """
        text = str(text)
        log.message.debug(text)
        self.s_set_text.emit(text)

    def maybe_reset_text(self, text):
        """Reset the text in the statusbar if it matches an expected text.

        Args:
            text: The expected text.
        """
        self.s_maybe_reset_text.emit(str(text))

    def ask(self, question, blocking):
        """Ask a question to the user.

        Note this method doesn't return the answer, it only blocks. The caller
        needs to construct a Question object and get the answer.

        Args:
            question: A Question object.
            blocking: Whether to return immediately or wait until the
                      question is answered.
        """
        self.s_question.emit(question, blocking)
