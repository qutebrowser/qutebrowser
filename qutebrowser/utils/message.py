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

# Because every method needs to have a log_stack argument
# pylint: disable=unused-variable

"""Message singleton so we don't have to define unneeded signals."""

import traceback

from PyQt5.QtCore import pyqtSignal, QObject

from qutebrowser.utils import usertypes, log, utils


def _log_stack(typ, stack):
    """Log the given message stacktrace.

    Args:
        typ: The type of the message (str)
        stack: The stack as an iterable of strings or a single string
    """
    try:
        # traceback.format_exc() produces a list of strings, while
        # traceback.format_stack() produces a single string...
        stack = stack.splitlines()
    except AttributeError:
        pass
    stack_text = '\n'.join(line.rstrip() for line in stack)
    log.message.debug("Stack for {} message:\n{}".format(typ, stack_text))


def error(message, *, stack=None):
    """Convenience function to display an error message in the statusbar.

    Args:
        message: The message to show
        stack: The stack trace to show.
    """
    if stack is None:
        stack = traceback.format_stack()
        typ = 'error'
    else:
        typ = 'error (from exception)'
    _log_stack(typ, stack)
    log.message.error(message)
    global_bridge.show_message.emit(usertypes.MessageLevel.error, message)


def warning(message):
    """Convenience function to display a warning message in the statusbar."""
    _log_stack('warning', traceback.format_stack())
    log.message.warning(message)
    global_bridge.show_message.emit(usertypes.MessageLevel.warning, message)


def info(message):
    """Convenience function to display an info message in the statusbar."""
    log.message.info(message)
    global_bridge.show_message.emit(usertypes.MessageLevel.info, message)


def _build_question(title, text=None, *, mode, default=None, abort_on=()):
    """Common function for ask/ask_async."""
    if not isinstance(mode, usertypes.PromptMode):
        raise TypeError("Mode {} is no PromptMode member!".format(mode))
    question = usertypes.Question()
    question.title = title
    question.text = text
    question.mode = mode
    question.default = default
    for sig in abort_on:
        sig.connect(question.abort)
    return question


def ask(*args, **kwargs):
    """Ask a modular question in the statusbar (blocking).

    Args:
        message: The message to display to the user.
        mode: A PromptMode.
        default: The default value to display.
        text: Additional text to show
        abort_on: A list of signals which abort the question if emitted.

    Return:
        The answer the user gave or None if the prompt was cancelled.
    """
    question = _build_question(*args, **kwargs)  # pylint: disable=missing-kwoa
    global_bridge.ask(question, blocking=True)
    answer = question.answer
    question.deleteLater()
    return answer


def ask_async(title, mode, handler, **kwargs):
    """Ask an async question in the statusbar.

    Args:
        message: The message to display to the user.
        mode: A PromptMode.
        handler: The function to get called with the answer as argument.
        default: The default value to display.
        text: Additional text to show.
    """
    question = _build_question(title, mode=mode, **kwargs)
    question.answered.connect(handler)
    question.completed.connect(question.deleteLater)
    global_bridge.ask(question, blocking=False)


def confirm_async(yes_action, no_action=None, cancel_action=None,
                  *args, **kwargs):
    """Ask a yes/no question to the user and execute the given actions.

    Args:
        message: The message to display to the user.
        yes_action: Callable to be called when the user answered yes.
        no_action: Callable to be called when the user answered no.
        cancel_action: Callable to be called when the user cancelled the
                       question.
        default: True/False to set a default value, or None.
        text: Additional text to show.

    Return:
        The question object.
    """
    kwargs['mode'] = usertypes.PromptMode.yesno
    question = _build_question(*args, **kwargs)  # pylint: disable=missing-kwoa
    question.answered_yes.connect(yes_action)
    if no_action is not None:
        question.answered_no.connect(no_action)
    if cancel_action is not None:
        question.cancelled.connect(cancel_action)

    question.completed.connect(question.deleteLater)
    global_bridge.ask(question, blocking=False)
    return question


class GlobalMessageBridge(QObject):

    """Global (not per-window) message bridge for errors/infos/warnings.

    Signals:
        show_message: Show a message
                      arg 0: A MessageLevel member
                      arg 1: The text to show
        prompt_done: Emitted when a prompt was answered somewhere.
        ask_question: Ask a question to the user.
                      arg 0: The Question object to ask.
                      arg 1: Whether to block (True) or ask async (False).

                      IMPORTANT: Slots need to be connected to this signal via
                                 a Qt.DirectConnection!
        mode_left: Emitted when a keymode was left in any window.
    """

    show_message = pyqtSignal(usertypes.MessageLevel, str)
    prompt_done = pyqtSignal(usertypes.KeyMode)
    ask_question = pyqtSignal(usertypes.Question, bool)
    mode_left = pyqtSignal(usertypes.KeyMode)

    def ask(self, question, blocking, *, log_stack=False):
        """Ask a question to the user.

        Note this method doesn't return the answer, it only blocks. The caller
        needs to construct a Question object and get the answer.

        Args:
            question: A Question object.
            blocking: Whether to return immediately or wait until the
                      question is answered.
            log_stack: ignored
        """
        self.ask_question.emit(question, blocking)


class MessageBridge(QObject):

    """Bridge for messages to be shown in the statusbar.

    Signals:
        s_set_text: Set a persistent text in the statusbar.
                    arg: The text to set.
        s_maybe_reset_text: Reset the text if it hasn't been changed yet.
                            arg: The expected text.
    """

    s_set_text = pyqtSignal(str)
    s_maybe_reset_text = pyqtSignal(str)

    def __repr__(self):
        return utils.get_repr(self)

    def set_text(self, text, *, log_stack=False):
        """Set the normal text of the statusbar.

        Args:
            text: The text to set.
            log_stack: ignored
        """
        text = str(text)
        log.message.debug(text)
        self.s_set_text.emit(text)

    def maybe_reset_text(self, text, *, log_stack=False):
        """Reset the text in the statusbar if it matches an expected text.

        Args:
            text: The expected text.
            log_stack: ignored
        """
        self.s_maybe_reset_text.emit(str(text))


global_bridge = GlobalMessageBridge()
