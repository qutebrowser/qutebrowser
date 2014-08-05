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

"""Manager for questions to be shown in the statusbar."""

from collections import namedtuple, deque

from PyQt5.QtCore import pyqtSlot, QTimer
from PyQt5.QtWidgets import QLineEdit

import qutebrowser.keyinput.modeman as modeman
import qutebrowser.commands.utils as cmdutils
from qutebrowser.utils.usertypes import PromptMode, Question, KeyMode
from qutebrowser.utils.qt import EventLoop
from qutebrowser.utils.log import statusbar as logger


PromptContext = namedtuple('PromptContext', ['question', 'text', 'input_text',
                                             'echo_mode', 'input_visible'])


class Prompter:

    """Manager for questions to be shown in the statusbar.

    The way in which multiple questions are handled deserves some explanation.

    If a question is blocking, we *need* to ask it immediately, and can't wait
    for previous questions to finish. We could theoretically ask a blocking
    question inside of another blocking one, so in ask_question we simply save
    the current prompt state on the stack, let the user answer the *most
    recent* question, and then restore the previous state.

    With a non-blocking question, things are a bit easier. We simply add it to
    self._queue if we're still busy handling another question, since it can be
    answered at any time.

    In either case, as soon as we finished handling a question, we call
    _pop_later() which schedules a _pop to ask the next question in _queue. We
    schedule it rather than doing it immediately because then the order of how
    things happen is clear, e.g. on_mode_left can't happen after we already set
    up the *new* question.

    Attributes:
        question: A Question object with the question to be asked to the user.
        _loops: A list of local EventLoops to spin in when blocking.
        _queue: A deque of waiting questions.
        _prompt: The associated Prompt widget.
    """

    def __init__(self, prompt):
        self.question = None
        self._loops = []
        self._queue = deque()
        self._busy = False
        self._prompt = prompt

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
        if not self._busy:
            return None
        ctx = PromptContext(question=self.question,
                            text=self._prompt.txt.text(),
                            input_text=self._prompt.lineedit.text(),
                            echo_mode=self._prompt.lineedit.echoMode(),
                            input_visible=self._prompt.lineedit.isVisible())
        return ctx

    def _restore_ctx(self, ctx):
        """Restore state from a PromptContext.

        Args:
            ctx: A PromptContext previously saved by _get_ctx, or None.

        Return: True if a context was restored, False otherwise.
        """
        logger.debug("Restoring context {}".format(ctx))
        if ctx is None:
            self._prompt.hide_prompt.emit()
            self._busy = False
            return False
        self.question = ctx.question
        self._prompt.txt.setText(ctx.text)
        self._prompt.lineedit.setText(ctx.input_text)
        self._prompt.lineedit.setEchoMode(ctx.echo_mode)
        self._prompt.lineedit.setVisible(ctx.input_visible)
        return True

    def _display_question(self):
        """Display the question saved in self.question.

        Return:
            The mode which should be entered.

        Raise:
            ValueError if the set PromptMode is invalid.
        """
        if self.question.mode == PromptMode.yesno:
            if self.question.default is None:
                suffix = ""
            elif self.question.default:
                suffix = " (yes)"
            else:
                suffix = " (no)"
            self._prompt.txt.setText(self.question.text + suffix)
            self._prompt.lineedit.hide()
            mode = KeyMode.yesno
        elif self.question.mode == PromptMode.text:
            self._prompt.txt.setText(self.question.text)
            if self.question.default:
                self._prompt.lineedit.setText(self.question.default)
            self._prompt.lineedit.show()
            mode = KeyMode.prompt
        elif self.question.mode == PromptMode.user_pwd:
            self._prompt.txt.setText(self.question.text)
            if self.question.default:
                self._prompt.lineedit.setText(self.question.default)
            self._prompt.lineedit.show()
            mode = KeyMode.prompt
        elif self.question.mode == PromptMode.alert:
            self._prompt.txt.setText(self.question.text + ' (ok)')
            self._prompt.lineedit.hide()
            mode = KeyMode.prompt
        else:
            raise ValueError("Invalid prompt mode!")
        self._prompt.lineedit.setFocus()
        self._prompt.show_prompt.emit()
        self._busy = True
        return mode

    def shutdown(self):
        """Cancel all blocking questions.

        Quits and removes all running eventloops.

        Return:
            True if loops needed to be aborted,
            False otherwise.
        """
        if self._loops:
            for loop in self._loops:
                loop.quit()
                loop.deleteLater()
            return True
        else:
            return False

    @pyqtSlot(KeyMode)
    def on_mode_left(self, mode):
        """Clear and reset input when the mode was left."""
        if mode in (KeyMode.prompt, KeyMode.yesno):
            self._prompt.txt.setText('')
            self._prompt.lineedit.clear()
            self._prompt.lineedit.setEchoMode(QLineEdit.Normal)
            self._prompt.hide_prompt.emit()
            self._busy = False
            if self.question.answer is None and not self.question.is_aborted:
                self.question.cancel()

    @cmdutils.register(instance='mainwindow.status.prompt.prompter', hide=True,
                       modes=[KeyMode.prompt, KeyMode.yesno])
    def prompt_accept(self):
        """Accept the current prompt.

        //

        This executes the next action depending on the question mode, e.g. asks
        for the password or leaves the mode.
        """
        if (self.question.mode == PromptMode.user_pwd and
                self.question.user is None):
            # User just entered an username
            self.question.user = self._prompt.lineedit.text()
            self._prompt.txt.setText("Password:")
            self._prompt.lineedit.clear()
            self._prompt.lineedit.setEchoMode(QLineEdit.Password)
        elif self.question.mode == PromptMode.user_pwd:
            # User just entered a password
            password = self._prompt.lineedit.text()
            self.question.answer = (self.question.user, password)
            modeman.leave(KeyMode.prompt, 'prompt accept')
            self.question.done()
        elif self.question.mode == PromptMode.text:
            # User just entered text.
            self.question.answer = self._prompt.lineedit.text()
            modeman.leave(KeyMode.prompt, 'prompt accept')
            self.question.done()
        elif self.question.mode == PromptMode.yesno:
            # User wants to accept the default of a yes/no question.
            self.question.answer = self.question.default
            modeman.leave(KeyMode.yesno, 'yesno accept')
            self.question.done()
        elif self.question.mode == PromptMode.alert:
            # User acknowledged an alert
            self.question.answer = None
            modeman.leave(KeyMode.prompt, 'alert accept')
            self.question.done()
        else:
            raise ValueError("Invalid question mode!")

    @cmdutils.register(instance='mainwindow.status.prompt.prompter', hide=True,
                       modes=[KeyMode.yesno])
    def prompt_yes(self):
        """Answer yes to a yes/no prompt."""
        if self.question.mode != PromptMode.yesno:
            # We just ignore this if we don't have a yes/no question.
            return
        self.question.answer = True
        modeman.leave(KeyMode.yesno, 'yesno accept')
        self.question.done()

    @cmdutils.register(instance='mainwindow.status.prompt.prompter', hide=True,
                       modes=[KeyMode.yesno])
    def prompt_no(self):
        """Answer no to a yes/no prompt."""
        if self.question.mode != PromptMode.yesno:
            # We just ignore this if we don't have a yes/no question.
            return
        self.question.answer = False
        modeman.leave(KeyMode.yesno, 'prompt accept')
        self.question.done()

    @pyqtSlot(Question, bool)
    def ask_question(self, question, blocking):
        """Dispkay a question in the statusbar.

        Args:
            question: The Question object to ask.
            blocking: If True, this function blocks and returns the result.

        Return:
            The answer of the user when blocking=True.
            None if blocking=False.
        """
        logger.debug("Asking question {}, blocking {}, loops {}, queue "
                     "{}".format(question, blocking, self._loops, self._queue))

        if self._busy and not blocking:
            # We got an async question, but we're already busy with one, so we
            # just queue it up for later.
            logger.debug("Adding {} to queue.".format(question))
            self._queue.append(question)
            return

        if blocking:
            # If we're blocking we save the old state on the stack, so we can
            # restore it after exec, if exec gets called multiple times.
            context = self._get_ctx()

        self.question = question
        mode = self._display_question()
        question.aborted.connect(lambda: modeman.maybe_leave(mode, 'aborted'))
        try:
            modeman.enter(mode, 'question asked')
        except modeman.ModeLockedError:
            if modeman.instance().mode != KeyMode.prompt:
                question.abort()
                return None
        modeman.instance().locked = True
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
