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


def error(message, immediately=False):
    """Convienience function to display an error message in the statusbar.

    Args:
        See MessageBridge.error.
    """
    instance().error(message, immediately)


def info(message, immediately=True):
    """Convienience function to display an info message in the statusbar.

    Args:
        See MessageBridge.info.
    """
    instance().info(message, immediately)


def set_cmd_text(txt):
    """Convienience function to Set the statusbar command line to a text."""
    instance().set_cmd_text(txt)


def ask(message, mode, default=None):
    """Ask a modular question in the statusbar (blocking).

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


def ask_async(message, mode, handler, default=None):
    """Ask an async question in the statusbar.

    Args:
        message: The message to display to the user.
        mode: A PromptMode.
        handler: The function to get called with the answer as argument.
        default: The default value to display.
    """
    bridge = instance()
    q = Question(bridge)
    q.text = message
    q.mode = mode
    q.default = default
    q.answered.connect(handler)
    bridge.queue(bridge.question, q, False)


def confirm_async(message, yes_action, no_action=None, default=None):
    """Ask a yes/no question to the user and execute the given actions.

    Args:
        message: The message to display to the user.
        yes_action: Callable to be called when the user answered yes.
        no_action: Callable to be called when the user answered no.
        default: True/False to set a default value, or None.
    """
    bridge = instance()
    q = Question(bridge)
    q.text = message
    q.mode = PromptMode.yesno
    q.default = default
    q.answered_yes.connect(yes_action)
    if no_action is not None:
        q.answered_no.connect(no_action)
    bridge.queue(bridge.question, q, False)


class MessageBridge(QObject):

    """Bridge for messages to be shown in the statusbar.

    Signals:
        s_error: Display an error message.
                 arg 0: The error message to show.
                 arg 1: Whether to show it immediately (True) or queue it
                        (False).
        s_info: Display an info message.
                args: See s_error.
        s_set_text: Set a persistent text in the statusbar.
                    arg: The text to set.
        s_set_cmd_text: Pre-set a text for the commandline prompt.
                        arg: The text to set.

        s_question: Ask a question to the user in the statusbar.
                    arg 0: The Question object to ask.
                    arg 1: Whether to block (True) or ask async (False).

                    IMPORTANT: Slots need to be connected to this signal via a
                               Qt.DirectConnection!
    """

    s_error = pyqtSignal(str, bool)
    s_info = pyqtSignal(str, bool)
    s_set_text = pyqtSignal(str)
    s_set_cmd_text = pyqtSignal(str)
    s_question = pyqtSignal(Question, bool)

    def __repr__(self):
        return '<{}>'.format(self.__class__.__name__)

    def _emit_later(self, signal, *args):
        """Emit a message later when the mainloop is not busy anymore.

        This is especially useful when messages are sent during init, before
        the messagebridge signals are connected - messages would get lost if we
        did normally emit them.

        Args:
            signal: The signal to be emitted.
            *args: Args to be passed to the signal.
        """
        QTimer.singleShot(0, lambda: signal.emit(*args))

    def error(self, msg, immediately=False):
        """Display an error in the statusbar.

        Args:
            msg: The message to show.
            queue: Whether to queue the message (True) or display it
                   immediately (False). Messages resulting from direct user
                   input should be displayed immediately, all other messages
                   should be queued.
        """
        msg = str(msg)
        logger.error(msg)
        self._emit_later(self.s_error, msg, immediately)

    def info(self, msg, immediately=True):
        """Display an info text in the statusbar.

        Args:
            See error(). Note immediately is True by default, because messages
            do rarely happen without user interaction.
        """
        msg = str(msg)
        logger.info(msg)
        self._emit_later(self.s_info, msg, immediately)

    def set_cmd_text(self, text):
        """Set the command text of the statusbar.

        Args:
            text: The text to set.
        """
        text = str(text)
        logger.debug(text)
        self._emit_later(self.s_set_cmd_text, text)

    def set_text(self, text):
        """Set the normal text of the statusbar.

        Args:
            text: The text to set.
        """
        text = str(text)
        logger.debug(text)
        self._emit_later(self.s_set_text, text)

    def ask(self, question, blocking):
        """Ask a question to the user.

        Note this method doesn't return the answer, it only blocks. The caller
        needs to construct a Question object and get the answer.

        We don't use _emit_later here as this makes no sense with a blocking
        question.

        Args:
            question: A Question object.
            blocking: Whether to return immediately or wait until the
                      question is answered.
        """
        self.question.emit(question, blocking)
