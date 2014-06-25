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

"""Message singleton so we don't have to define unneeded signals."""

from PyQt5.QtCore import pyqtSignal, QCoreApplication, QObject, QTimer

from qutebrowser.utils.usertypes import PromptMode, Question
from qutebrowser.utils.log import misc as logger


def instance():
    """Get the global messagebridge instance."""
    return QCoreApplication.instance().messagebridge


def error(message, queue=False):
    """Display an error message in the statusbar.

    Args:
        message: The message to display.
        queue: If set, message gets queued rather than being displayed
               immediately.
    """
    message = str(message)
    logger.error(message)
    bridge = instance()
    bridge.queue(bridge.error, message, queue)


def info(message, queue=False):
    """Display a temporary info message in the statusbar.

    Args:
        message: The message to display.
        queue: If set, message gets queued rather than being displayed
               immediately.
    """
    message = str(message)
    logger.info(message)
    bridge = instance()
    bridge.queue(bridge.info, message, queue)


def text(message):
    """Display a persistent message in the statusbar."""
    message = str(message)
    logger.debug(message)
    bridge = instance()
    bridge.queue(bridge.text, message)


def modular_question(message, mode, default=None):
    """Ask a modular question in the statusbar.

    Args:
        message: The message to display to the user.
        mode: A PromptMode.
        default: The default value to display.

    Return:
        The answer the user gave or None if the prompt was cancelled.
    """
    q = Question()
    q.text = message
    q.mode = mode
    q.default = default
    instance().question.emit(q, True)
    q.deleteLater()
    return q.answer


def alert(message):
    """Display an alert which needs to be confirmed."""
    q = Question()
    q.text = message
    q.mode = PromptMode.alert
    instance().question.emit(q, True)
    q.deleteLater()


def question(message, mode, handler, cancelled_handler=None, default=None):
    """Ask an async question in the statusbar.

    Args:
        message: The message to display to the user.
        mode: A PromptMode.
        handler: The function to get called with the answer as argument.
        cancelled_handler: The function to get called when the prompt was
                           cancelled by the user, or None.
        default: The default value to display.
    """
    q = Question(instance())
    q.text = message
    q.mode = mode
    q.default = default
    q.answered.connect(handler)
    if cancelled_handler is not None:
        q.cancelled.connect(cancelled_handler)
    bridge = instance()
    bridge.queue(bridge.question, q, False)


def confirm_action(message, yes_action, no_action=None, default=None):
    """Ask a yes/no question to the user and execute the given actions.

    Args:
        message: The message to display to the user.
        yes_action: Callable to be called when the user answered yes.
        no_action: Callable to be called when the user answered no.
        default: True/False to set a default value, or None.
    """
    q = Question(instance())
    q.text = message
    q.mode = PromptMode.yesno
    q.default = default
    q.answered_yes.connect(yes_action)
    if no_action is not None:
        q.answered_no.connect(no_action)
    bridge = instance()
    bridge.queue(bridge.question, q, False)


def clear():
    """Clear a persistent message in the statusbar."""
    bridge = instance()
    bridge.queue(bridge.text, '')


def set_cmd_text(txt):
    """Set the statusbar command line to a preset text."""
    bridge = instance()
    bridge.queue(bridge.set_cmd_text, txt)


class MessageBridge(QObject):

    """Bridge for messages to be shown in the statusbar."""

    error = pyqtSignal(str, bool)
    info = pyqtSignal(str, bool)
    text = pyqtSignal(str)
    set_cmd_text = pyqtSignal(str)
    question = pyqtSignal(Question, bool)

    def __repr__(self):
        return '<{}>'.format(self.__class__.__name__)

    def queue(self, signal, *args):
        """Queue a message to be emitted.

        Args:
            signal: The signal to be emitted.
            *args: Args to be passed to the signal.
        """
        QTimer.singleShot(0, lambda: signal.emit(*args))
