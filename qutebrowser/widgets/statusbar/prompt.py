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

"""Prompt shown in the statusbar."""

from collections import namedtuple, deque

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QTimer
from PyQt5.QtWidgets import QHBoxLayout, QWidget, QLineEdit

import qutebrowser.keyinput.modeman as modeman
import qutebrowser.commands.utils as cmdutils
from qutebrowser.widgets.statusbar.textbase import TextBase
from qutebrowser.widgets.misc import MinimalLineEdit
from qutebrowser.utils.usertypes import PromptMode, Question
from qutebrowser.utils.qt import EventLoop
from qutebrowser.utils.log import statusbar as logger


PromptContext = namedtuple('PromptContext', ['question', 'text', 'input_text',
                                             'echo_mode', 'input_visible'])


class Prompt(QWidget):

    """The prompt widget shown in the statusbar.

    Attributes:
        question: A Question object with the question to be asked to the user.
        _loops: A list of local EventLoops to spin in when blocking.
        _hbox: The QHBoxLayout used to display the text and prompt.
        _txt: The TextBase instance (QLabel) used to display the prompt text.
        _input: The MinimalLineEdit instance (QLineEdit) used for the input.
        _queue: A deque of waiting questions.

    Signals:
        show_prompt: Emitted when the prompt widget wants to be shown.
        hide_prompt: Emitted when the prompt widget wants to be hidden.
    """

    show_prompt = pyqtSignal()
    hide_prompt = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.question = None
        self._loops = []
        self._queue = deque()

        self._hbox = QHBoxLayout(self)
        self._hbox.setContentsMargins(0, 0, 0, 0)
        self._hbox.setSpacing(5)

        self._txt = TextBase()
        self._hbox.addWidget(self._txt)

        self._input = MinimalLineEdit()
        self._hbox.addWidget(self._input)

        self.visible = False

    def __repr__(self):
        return '<{}>'.format(self.__class__.__name__)

    def _pop_later(self):
        """Helper to call self._pop as soon as everything else is done."""
        QTimer.singleShot(0, self._pop)

    def _pop(self):
        """Pop a question from the queue and ask it, if there are any."""
        logger.debug("Popping from queue {}".format(self._queue))
        if self._queue:
            self.ask_question(self._queue.popleft(), blocking=False)

    def _get_ctx(self):
        """Get a PromptContext based on the current state."""
        if not self.visible:
            # FIXME do we really use visible here?
            return None
        ctx = PromptContext(question=self.question, text=self._txt.text(),
                            input_text=self._input.text(),
                            echo_mode=self._input.echoMode(),
                            input_visible=self._input.isVisible())
        return ctx

    def _restore_ctx(self, ctx):
        """Restore state from a PromptContext.

        Args:
            ctx: A PromptContext previously saved by _get_ctx, or None.

        Return: True if a context was restored, False otherwise.
        """
        logger.debug("Restoring context {}".format(ctx))
        if ctx is None:
            self.hide_prompt.emit()
            return False
        self.question = ctx.question
        self._txt.setText(ctx.text)
        self._input.setText(ctx.input_text)
        self._input.setEchoMode(ctx.echo_mode)
        self._input.setVisible(ctx.input_visible)
        return True

    def _display_question(self):
        """Display the question saved in self.question.

        Return:
            The mode which should be entered.
        """
        if self.question.mode == PromptMode.yesno:
            if self.question.default is None:
                suffix = ""
            elif self.question.default:
                suffix = " (yes)"
            else:
                suffix = " (no)"
            self._txt.setText(self.question.text + suffix)
            self._input.hide()
            mode = 'yesno'
        elif self.question.mode == PromptMode.text:
            self._txt.setText(self.question.text)
            if self.question.default:
                self._input.setText(self.question.default)
            self._input.show()
            mode = 'prompt'
        elif self.question.mode == PromptMode.user_pwd:
            self._txt.setText(self.question.text)
            if self.question.default:
                self._input.setText(self.question.default)
            self._input.show()
            mode = 'prompt'
        elif self.question.mode == PromptMode.alert:
            self._txt.setText(self.question.text + ' (ok)')
            self._input.hide()
            mode = 'prompt'
        else:
            raise ValueError("Invalid prompt mode!")
        self._input.setFocus()
        self.show_prompt.emit()
        return mode

    def on_mode_left(self, mode):
        """Clear and reset input when the mode was left."""
        if mode in ('prompt', 'yesno'):
            self._txt.setText('')
            self._input.clear()
            self._input.setEchoMode(QLineEdit.Normal)
            self.hide_prompt.emit()
            if self.question.answer is None and not self.question.is_aborted:
                self.question.cancel()

    @cmdutils.register(instance='mainwindow.status.prompt', hide=True,
                       modes=['prompt'])
    def prompt_accept(self):
        """Accept the prompt.

        This executes the next action depending on the question mode, e.g. asks
        for the password or leaves the mode.
        """
        if (self.question.mode == PromptMode.user_pwd and
                self.question.user is None):
            # User just entered an username
            self.question.user = self._input.text()
            self._txt.setText("Password:")
            self._input.clear()
            self._input.setEchoMode(QLineEdit.Password)
        elif self.question.mode == PromptMode.user_pwd:
            # User just entered a password
            password = self._input.text()
            self.question.answer = (self.question.user, password)
            modeman.leave('prompt', 'prompt accept')
            self.question.done()
        elif self.question.mode == PromptMode.text:
            # User just entered text.
            self.question.answer = self._input.text()
            modeman.leave('prompt', 'prompt accept')
            self.question.done()
        elif self.question.mode == PromptMode.yesno:
            # User wants to accept the default of a yes/no question.
            self.question.answer = self.question.default
            modeman.leave('yesno', 'yesno accept')
            self.question.done()
        elif self.question.mode == PromptMode.alert:
            # User acknowledged an alert
            self.question.answer = None
            modeman.leave('prompt', 'alert accept')
            self.question.done()
        else:
            raise ValueError("Invalid question mode!")

    @cmdutils.register(instance='mainwindow.status.prompt', hide=True,
                       modes=['yesno'])
    def prompt_yes(self):
        """Answer yes to a yes/no prompt."""
        if self.question.mode != PromptMode.yesno:
            # We just ignore this if we don't have a yes/no question.
            return
        self.question.answer = True
        modeman.leave('yesno', 'yesno accept')
        self.question.done()

    @cmdutils.register(instance='mainwindow.status.prompt', hide=True,
                       modes=['yesno'])
    def prompt_no(self):
        """Answer no to a yes/no prompt."""
        if self.question.mode != PromptMode.yesno:
            # We just ignore this if we don't have a yes/no question.
            return
        self.question.answer = False
        modeman.leave('yesno', 'prompt accept')
        self.question.done()

    @pyqtSlot(Question, bool)
    def ask_question(self, question, blocking):
        """Dispkay a question in the statusbar.

        Args:
            question: The Question object to ask.
            blocking: If True, _spin is called and the result is returned.

        Return:
            The answer of the user when blocking=True.
            None if blocking=False.

        Raise:
            ValueError if the set PromptMode is invalid.
        """
        logger.debug("Asking question {}, blocking {}, loops {}, queue "
                     "{}".format(question, blocking, self._loops, self._queue))

        if self.visible and not blocking:
            # We got an async question, but we're already busy with one, so we
            # just queue it up for later.
            logger.debug("Adding to queue")
            self._queue.append(question)
            return

        if blocking:
            # If we're blocking we save the old state on the stack, so we can
            # restore it after exec, if exec gets called multiple times.
            context = self._get_ctx()

        self.question = question
        mode = self._display_question()
        question.aborted.connect(lambda: modeman.maybe_leave(mode, 'aborted'))
        modeman.enter(mode, 'question asked')
        if blocking:
            loop = EventLoop()
            self._loops.append(loop)
            loop.destroyed.connect(lambda: self._loops.remove(loop))
            question.completed.connect(loop.quit)
            question.completed.connect(loop.deleteLater)
            loop.exec_()
            if not self._restore_ctx(context):
                # Nothing left to restore, so we can go back to popping async
                # questions.
                if self._queue:
                    self._pop_later()
            return self.question.answer
        else:
            question.completed.connect(self._pop_later)
