# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Showing prompts above the statusbar."""

import sip
import collections

from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt, QTimer
from PyQt5.QtWidgets import (QWidget, QGridLayout, QVBoxLayout, QLineEdit,
                             QLabel, QSpacerItem, QWidgetItem)

from qutebrowser.config import style, config
from qutebrowser.utils import usertypes, log, utils, qtutils
from qutebrowser.keyinput import modeman
from qutebrowser.commands import cmdutils


AuthTuple = collections.namedtuple('AuthTuple', ['user', 'password'])


class Error(Exception):

    """Base class for errors in this module."""


class UnsupportedOperationError(Exception):

    """Raised when the prompt class doesn't support the requested operation."""


class PromptContainer(QWidget):

    """Container for prompts to be shown above the statusbar.

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
        _shutting_down: Whether we're currently shutting down the prompter and
                        should ignore future questions to avoid segfaults.
        _loops: A list of local EventLoops to spin in when blocking.
        _queue: A deque of waiting questions.
        _prompt: The current prompt object if we're handling a question.
        _layout: The layout used to show prompts in.
        _win_id: The window ID this object is associated with.
    """

    STYLESHEET = """
        QWidget#Prompt {
            {% if config.get('ui', 'status-position') == 'top' %}
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
            {% else %}
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            {% endif %}
        }

        QWidget {
            /* FIXME
            font: {{ font['keyhint'] }};
            FIXME
            */
            color: {{ color['statusbar.fg.prompt'] }};
            background-color: {{ color['statusbar.bg.prompt'] }};
        }

        QLineEdit {
            border: 1px solid grey;
        }
    """
    update_geometry = pyqtSignal()

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(10, 10, 10, 10)
        self._prompt = None
        self._shutting_down = False
        self._loops = []
        self._queue = collections.deque()
        self._win_id = win_id

        self.setObjectName('Prompt')
        self.setAttribute(Qt.WA_StyledBackground, True)
        style.set_register_stylesheet(self)

    def __repr__(self):
        return utils.get_repr(self, loops=len(self._loops),
                              queue=len(self._queue), prompt=self._prompt)

    def _pop_later(self):
        """Helper to call self._pop as soon as everything else is done."""
        QTimer.singleShot(0, self._pop)

    def _pop(self):
        """Pop a question from the queue and ask it, if there are any."""
        log.prompt.debug("Popping from queue {}".format(self._queue))
        if self._queue:
            question = self._queue.popleft()
            if not sip.isdeleted(question):
                # the question could already be deleted, e.g. by a cancelled
                # download. See
                # https://github.com/The-Compiler/qutebrowser/issues/415
                self.ask_question(question, blocking=False)

    def _show_prompt(self, prompt):
        """SHow the given prompt object.

        Args:
            prompt: A Prompt object or None.

        Return: True if a prompt was shown, False otherwise.
        """
        # Before we set a new prompt, make sure the old one is what we expect
        # This will also work if self._prompt is None and verify nothing is
        # displayed.
        #
        # Note that we don't delete the old prompt here, as we might be in the
        # middle of saving/restoring an old prompt object.
        assert self._layout.count() in [0, 1], self._layout.count()
        item = self._layout.takeAt(0)
        if item is None:
            assert self._prompt is None, self._prompt
        else:
            if (not isinstance(item, QWidgetItem) or
                    item.widget() is not self._prompt):
                raise AssertionError("Expected {} to be in layout but got "
                                    "{}!".format(self._prompt, item))
            item.widget().hide()

        log.prompt.debug("Displaying prompt {}".format(prompt))
        self._prompt = prompt
        if prompt is None:
            self.hide()
            return False

        prompt.question.aborted.connect(
            lambda: modeman.maybe_leave(self._win_id, prompt.KEY_MODE,
                                        'aborted'))
        modeman.enter(self._win_id, prompt.KEY_MODE, 'question asked')
        self._prompt = prompt
        self._layout.addWidget(self._prompt)
        self._prompt.show()
        self.show()
        self._prompt.setFocus()
        self.update_geometry.emit()
        return True

    def shutdown(self):
        """Cancel all blocking questions.

        Quits and removes all running event loops.

        Return:
            True if loops needed to be aborted,
            False otherwise.
        """
        self._shutting_down = True
        if self._loops:
            for loop in self._loops:
                loop.quit()
                loop.deleteLater()
            return True
        else:
            return False

    @cmdutils.register(instance='prompt-container', hide=True, scope='window',
                       modes=[usertypes.KeyMode.prompt,
                              usertypes.KeyMode.yesno])
    def prompt_accept(self, value=None):
        """Accept the current prompt.

        //

        This executes the next action depending on the question mode, e.g. asks
        for the password or leaves the mode.

        Args:
            value: If given, uses this value instead of the entered one.
                   For boolean prompts, "yes"/"no" are accepted as value.
        """
        done = self._prompt.accept(value)
        if done:
            self._prompt.question.done()
            modeman.maybe_leave(self._win_id, self._prompt.KEY_MODE,
                                ':prompt-accept')

    @cmdutils.register(instance='prompt-container', hide=True, scope='window',
                       modes=[usertypes.KeyMode.yesno],
                       deprecated='Use :prompt-accept yes instead!')
    def prompt_yes(self):
        """Answer yes to a yes/no prompt."""
        self.prompt_accept('yes')

    @cmdutils.register(instance='prompt-container', hide=True, scope='window',
                       modes=[usertypes.KeyMode.yesno],
                       deprecated='Use :prompt-accept no instead!')
    def prompt_no(self):
        """Answer no to a yes/no prompt."""
        self.prompt_accept('no')

    @pyqtSlot(usertypes.KeyMode)
    def on_mode_left(self, mode):
        """Clear and reset input when the mode was left."""
        # FIXME when is this not the case?
        if (self._prompt is not None and
                mode == self._prompt.KEY_MODE):
            question = self._prompt.question
            self._show_prompt(None)
            # FIXME move this somewhere else?
            if question.answer is None and not question.is_aborted:
                question.cancel()


    @cmdutils.register(instance='prompter', hide=True, scope='window',
                       modes=[usertypes.KeyMode.prompt], maxsplit=0)
    def prompt_open_download(self, cmdline: str=None):
        """Immediately open a download.

        If no specific command is given, this will use the system's default
        application to open the file.

        Args:
            cmdline: The command which should be used to open the file. A `{}`
                     is expanded to the temporary file name. If no `{}` is
                     present, the filename is automatically appended to the
                     cmdline.
        """
        try:
            self._prompt.download_open(cmdline)
        except UnsupportedOperationError:
            pass

    @pyqtSlot(usertypes.Question, bool)
    def ask_question(self, question, blocking):
        """Display a prompt for a given question.

        Args:
            question: The Question object to ask.
            blocking: If True, this function blocks and returns the result.

        Return:
            The answer of the user when blocking=True.
            None if blocking=False.
        """
        log.prompt.debug("Asking question {}, blocking {}, loops {}, queue "
                         "{}".format(question, blocking, self._loops,
                                     self._queue))

        if self._shutting_down:
            # If we're currently shutting down we have to ignore this question
            # to avoid segfaults - see
            # https://github.com/The-Compiler/qutebrowser/issues/95
            log.prompt.debug("Ignoring question because we're shutting down.")
            question.abort()
            return None

        if self._prompt is not None and not blocking:
            # We got an async question, but we're already busy with one, so we
            # just queue it up for later.
            log.prompt.debug("Adding {} to queue.".format(question))
            self._queue.append(question)
            return

        if blocking:
            # If we're blocking we save the old state on the stack, so we can
            # restore it after exec, if exec gets called multiple times.
            old_prompt = self._prompt

        classes = {
            usertypes.PromptMode.yesno: YesNoPrompt,
            usertypes.PromptMode.text: LineEditPrompt,
            usertypes.PromptMode.user_pwd: AuthenticationPrompt,
            usertypes.PromptMode.download: DownloadFilenamePrompt,
            usertypes.PromptMode.alert: AlertPrompt,
        }
        klass = classes[question.mode]
        self._show_prompt(klass(question))
        if blocking:
            loop = qtutils.EventLoop()
            self._loops.append(loop)
            loop.destroyed.connect(lambda: self._loops.remove(loop))
            question.completed.connect(loop.quit)
            question.completed.connect(loop.deleteLater)
            loop.exec_()
            # FIXME don't we end up connecting modeman signals twice here now?
            if not self._show_prompt(old_prompt):
                # Nothing left to restore, so we can go back to popping async
                # questions.
                if self._queue:
                    self._pop_later()
            return question.answer
        else:
            question.completed.connect(self._pop_later)


class _BasePrompt(QWidget):

    """Base class for all prompts."""

    KEY_MODE = usertypes.KeyMode.prompt

    def __init__(self, question, parent=None):
        super().__init__(parent)
        self.question = question
        self._vbox = QVBoxLayout(self)
        self._vbox.setSpacing(15)

    def __repr__(self):
        return utils.get_repr(self, question=self.question, constructor=True)

    def _init_title(self, question):
        if question.title is None:
            title = question.text
            text = None
        else:
            title = question.title
            text = question.text

        title_label = QLabel('<b>{}</b>'.format(title), self)
        self._vbox.addWidget(title_label)
        if text is not None:
            text_label = QLabel(text)
            self._vbox.addWidget(text_label)

    def accept(self, value=None):
        raise NotImplementedError

    def open_download(self, _cmdline):
        raise UnsupportedOperationError


class LineEditPrompt(_BasePrompt):

    def __init__(self, question, parent=None):
        super().__init__(question, parent)
        self._lineedit = QLineEdit(self)
        self._init_title(question)
        self._vbox.addWidget(self._lineedit)
        if question.default:
            self._lineedit.setText(question.default)
        self.setFocusProxy(self._lineedit)

    def accept(self, value=None):
        text = value if value is not None else self._lineedit.text()
        self.question.answer = text
        return True


class DownloadFilenamePrompt(LineEditPrompt):

    # FIXME have a FilenamePrompt

    def __init__(self, question, parent=None):
        super().__init__(question, parent)
        # FIXME show :prompt-open-download keybinding
#         key_mode = self.KEY_MODES[self.question.mode]
#         key_config = objreg.get('key-config')
#         all_bindings = key_config.get_reverse_bindings_for(key_mode.name)
#         bindings = all_bindings.get('prompt-open-download', [])
#         if bindings:
#             text += ' ({} to open)'.format(bindings[0])


    def accept(self, value=None):
        text = value if value is not None else self._lineedit.text()
        self.question.answer = usertypes.FileDownloadTarget(text)
        return True

    def download_open(self, cmdline):
        self.question.answer = usertypes.OpenFileDownloadTarget(cmdline)
        modeman.maybe_leave(self._win_id, usertypes.KeyMode.prompt,
                            'download open')
        self.question.done()


class AuthenticationPrompt(_BasePrompt):

    def __init__(self, question, parent=None):
        super().__init__(question, parent)
        self._init_title(question)

        user_label = QLabel("Username:", self)
        self._user_lineedit = QLineEdit(self)

        password_label = QLabel("Password:", self)
        self._password_lineedit = QLineEdit(self)
        self._password_lineedit.setEchoMode(QLineEdit.Password)

        grid = QGridLayout()
        grid.addWidget(user_label, 1, 0)
        grid.addWidget(self._user_lineedit, 1, 1)
        grid.addWidget(password_label, 2, 0)
        grid.addWidget(self._password_lineedit, 2, 1)
        self._vbox.addLayout(grid)

        assert not question.default, question.default
        self.setFocusProxy(self._user_lineedit)

    def accept(self, value=None):
        if value is not None:
            if ':' not in value:
                raise Error("Value needs to be in the format "
                            "username:password, but {} was given".format(
                                value))
            username, password = value.split(':', maxsplit=1)
            self.question.answer = AuthTuple(username, password)
            return True
        elif self._user_lineedit.hasFocus():
            # Earlier, tab was bound to :prompt-accept, so to still support that
            # we simply switch the focus when tab was pressed.
            self._password_lineedit.setFocus()
            return False
        else:
            self.question.answer = AuthTuple(self._user_lineedit.text(),
                                             self._password_lineedit.text())
            return True


class YesNoPrompt(_BasePrompt):

    KEY_MODE = usertypes.KeyMode.yesno

    def __init__(self, question, parent=None):
        super().__init__(question, parent)
        self._init_title(question)
        # FIXME
        # "Enter/y: yes"
        # "n: no"
        # (depending on default)

    def accept(self, value=None):
        if value is None:
            self.question.answer = self.question.default
        elif value == 'yes':
            self.question.answer = True
        elif value == 'no':
            self.question.answer = False
        else:
            raise Error("Invalid value {} - expected yes/no!".format(value))
        return True


class AlertPrompt(_BasePrompt):

    def __init__(self, question, parent=None):
        super().__init__(question, parent)
        self._init_title(question)
        # FIXME
        # Enter: acknowledge

    def accept(self, value=None):
        if value is not None:
            raise Error("No value is permitted with alert prompts!")
        # Doing nothing otherwise
        return True
