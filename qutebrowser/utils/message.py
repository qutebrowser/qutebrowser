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

# Because every method needs to have a log_stack argument
# pylint: disable=unused-argument

"""Message singleton so we don't have to define unneeded signals."""

import traceback
import typing

from PyQt5.QtCore import pyqtSignal, QObject

from qutebrowser.utils import usertypes, log, utils


def _log_stack(typ: str, stack: str) -> None:
    """Log the given message stacktrace.

    Args:
        typ: The type of the message.
        stack: An optional stacktrace.
    """
    lines = stack.splitlines()
    stack_text = '\n'.join(line.rstrip() for line in lines)
    log.message.debug("Stack for {} message:\n{}".format(typ, stack_text))


def error(message: str, *, stack: str = None, replace: bool = False) -> None:
    """Display an error message.

    Args:
        message: The message to show.
        stack: The stack trace to show (if any).
        replace: Replace existing messages which are still being shown.
    """
    if stack is None:
        stack = ''.join(traceback.format_stack())
        typ = 'error'
    else:
        typ = 'error (from exception)'
    _log_stack(typ, stack)
    log.message.error(message)
    global_bridge.show(usertypes.MessageLevel.error, message, replace)


def warning(message: str, *, replace: bool = False) -> None:
    """Display a warning message.

    Args:
        message: The message to show.
        replace: Replace existing messages which are still being shown.
    """
    _log_stack('warning', ''.join(traceback.format_stack()))
    log.message.warning(message)
    global_bridge.show(usertypes.MessageLevel.warning, message, replace)


def info(message: str, *, replace: bool = False) -> None:
    """Display an info message.

    Args:
        message: The message to show.
        replace: Replace existing messages which are still being shown.
    """
    log.message.info(message)
    global_bridge.show(usertypes.MessageLevel.info, message, replace)


def _build_question(title: str,
                    text: str = None, *,
                    mode: usertypes.PromptMode,
                    default: typing.Union[None, bool, str] = None,
                    abort_on: typing.Iterable[pyqtSignal] = (),
                    url: str = None,
                    option: bool = None) -> usertypes.Question:
    """Common function for ask/ask_async."""
    question = usertypes.Question()
    question.title = title
    question.text = text
    question.mode = mode
    question.default = default
    question.url = url

    if option is not None:
        if mode != usertypes.PromptMode.yesno:
            raise ValueError("Can only 'option' with PromptMode.yesno")
        if url is None:
            raise ValueError("Need 'url' given when 'option' is given")
    question.option = option

    for sig in abort_on:
        sig.connect(question.abort)
    return question


def ask(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
    """Ask a modular question in the statusbar (blocking).

    Args:
        message: The message to display to the user.
        mode: A PromptMode.
        default: The default value to display.
        text: Additional text to show
        option: The option for always/never question answers.
                Only available with PromptMode.yesno.
        abort_on: A list of signals which abort the question if emitted.

    Return:
        The answer the user gave or None if the prompt was cancelled.
    """
    question = _build_question(*args, **kwargs)  # pylint: disable=missing-kwoa
    global_bridge.ask(question, blocking=True)
    answer = question.answer
    question.deleteLater()
    return answer


def ask_async(title: str,
              mode: usertypes.PromptMode,
              handler: typing.Callable[[typing.Any], None],
              **kwargs: typing.Any) -> None:
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


_ActionType = typing.Callable[[], typing.Any]


def confirm_async(*, yes_action: _ActionType,
                  no_action: _ActionType = None,
                  cancel_action: _ActionType = None,
                  **kwargs: typing.Any) -> usertypes.Question:
    """Ask a yes/no question to the user and execute the given actions.

    Args:
        message: The message to display to the user.
        yes_action: Callable to be called when the user answered yes.
        no_action: Callable to be called when the user answered no.
        cancel_action: Callable to be called when the user cancelled the
                       question.
        default: True/False to set a default value, or None.
        option: The option for always/never question answers.
        text: Additional text to show.

    Return:
        The question object.
    """
    kwargs['mode'] = usertypes.PromptMode.yesno
    question = _build_question(**kwargs)  # pylint: disable=missing-kwoa
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

    Attributes:
        _connected: Whether a slot is connected and we can show messages.
        _cache: Messages shown while we were not connected.

    Signals:
        show_message: Show a message
                      arg 0: A MessageLevel member
                      arg 1: The text to show
                      arg 2: Whether to replace other messages with
                             replace=True.
        prompt_done: Emitted when a prompt was answered somewhere.
        ask_question: Ask a question to the user.
                      arg 0: The Question object to ask.
                      arg 1: Whether to block (True) or ask async (False).

                      IMPORTANT: Slots need to be connected to this signal via
                                 a Qt.DirectConnection!
        mode_left: Emitted when a keymode was left in any window.
    """

    show_message = pyqtSignal(usertypes.MessageLevel, str, bool)
    prompt_done = pyqtSignal(usertypes.KeyMode)
    ask_question = pyqtSignal(usertypes.Question, bool)
    mode_left = pyqtSignal(usertypes.KeyMode)
    clear_messages = pyqtSignal()

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)
        self._connected = False
        self._cache = [
        ]  # type: typing.List[typing.Tuple[usertypes.MessageLevel, str, bool]]

    def ask(self, question: usertypes.Question,
            blocking: bool, *,
            log_stack: bool = False) -> None:
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

    def show(self, level: usertypes.MessageLevel,
             text: str,
             replace: bool = False) -> None:
        """Show the given message."""
        if self._connected:
            self.show_message.emit(level, text, replace)
        else:
            self._cache.append((level, text, replace))

    def flush(self) -> None:
        """Flush messages which accumulated while no handler was connected.

        This is so we don't miss messages shown during some early init phase.
        It needs to be called once the show_message signal is connected.
        """
        self._connected = True
        for args in self._cache:
            self.show(*args)
        self._cache = []


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

    def __repr__(self) -> str:
        return utils.get_repr(self)

    def set_text(self, text: str, *, log_stack: bool = False) -> None:
        """Set the normal text of the statusbar.

        Args:
            text: The text to set.
            log_stack: ignored
        """
        text = str(text)
        log.message.debug(text)
        self.s_set_text.emit(text)

    def maybe_reset_text(self, text: str, *, log_stack: bool = False) -> None:
        """Reset the text in the statusbar if it matches an expected text.

        Args:
            text: The expected text.
            log_stack: ignored
        """
        self.s_maybe_reset_text.emit(str(text))


global_bridge = GlobalMessageBridge()
