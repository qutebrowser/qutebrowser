# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import os.path
import html
import collections
import functools
import typing

import attr
from PyQt5.QtCore import (pyqtSlot, pyqtSignal, Qt, QTimer, QDir, QModelIndex,
                          QItemSelectionModel, QObject, QEventLoop)
from PyQt5.QtWidgets import (QWidget, QGridLayout, QVBoxLayout, QLineEdit,
                             QLabel, QFileSystemModel, QTreeView, QSizePolicy,
                             QSpacerItem)

from qutebrowser.browser import downloads
from qutebrowser.config import config, configtypes, configexc, stylesheet
from qutebrowser.utils import usertypes, log, utils, qtutils, objreg, message
from qutebrowser.keyinput import modeman
from qutebrowser.api import cmdutils
from qutebrowser.utils import urlmatch


prompt_queue = typing.cast('PromptQueue', None)


@attr.s
class AuthInfo:

    """Authentication info returned by a prompt."""

    user = attr.ib()
    password = attr.ib()


class Error(Exception):

    """Base class for errors in this module."""


class UnsupportedOperationError(Error):

    """Raised when the prompt class doesn't support the requested operation."""


class PromptQueue(QObject):

    """Global manager and queue for upcoming prompts.

    The way in which multiple questions are handled deserves some explanation.

    If a question is blocking, we *need* to ask it immediately, and can't wait
    for previous questions to finish. We could theoretically ask a blocking
    question inside of another blocking one, so in ask_question we simply save
    the current question on the stack, let the user answer the *most recent*
    question, and then restore the previous state.

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
        _question: The current Question object if we're handling a question.

    Signals:
        show_prompts: Emitted with a Question object when prompts should be
                      shown.
    """

    show_prompts = pyqtSignal(usertypes.Question)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._question = None
        self._shutting_down = False
        self._loops = []  # type: typing.MutableSequence[qtutils.EventLoop]
        self._queue = collections.deque(
        )  # type: typing.Deque[usertypes.Question]
        message.global_bridge.mode_left.connect(self._on_mode_left)

    def __repr__(self):
        return utils.get_repr(self, loops=len(self._loops),
                              queue=len(self._queue), question=self._question)

    def _pop_later(self):
        """Helper to call self._pop as soon as everything else is done."""
        QTimer.singleShot(0, self._pop)

    def _pop(self):
        """Pop a question from the queue and ask it, if there are any."""
        log.prompt.debug("Popping from queue {}".format(self._queue))
        if self._queue:
            question = self._queue.popleft()
            if not question.is_aborted:
                # the question could already be aborted, e.g. by a cancelled
                # download. See
                # https://github.com/qutebrowser/qutebrowser/issues/415 and
                # https://github.com/qutebrowser/qutebrowser/issues/1249
                self.ask_question(question, blocking=False)

    def shutdown(self):
        """Cancel all blocking questions.

        Quits and removes all running event loops.

        Return:
            True if loops needed to be aborted,
            False otherwise.
        """
        log.prompt.debug("Shutting down with loops {}".format(self._loops))
        self._shutting_down = True
        if self._loops:
            for loop in self._loops:
                loop.quit()
                loop.deleteLater()
            return True
        else:
            return False

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
            # https://github.com/qutebrowser/qutebrowser/issues/95
            log.prompt.debug("Ignoring question because we're shutting down.")
            question.abort()
            return None

        if self._question is not None and not blocking:
            # We got an async question, but we're already busy with one, so we
            # just queue it up for later.
            log.prompt.debug("Adding {} to queue.".format(question))
            self._queue.append(question)
            return None

        if blocking:
            # If we're blocking we save the old question on the stack, so we
            # can restore it after exec, if exec gets called multiple times.
            log.prompt.debug("New question is blocking, saving {}".format(
                self._question))
            old_question = self._question
            if old_question is not None:
                old_question.interrupted = True

        self._question = question
        self.show_prompts.emit(question)

        if blocking:
            loop = qtutils.EventLoop()
            self._loops.append(loop)
            loop.destroyed.connect(lambda: self._loops.remove(loop))
            question.completed.connect(loop.quit)
            question.completed.connect(loop.deleteLater)
            log.prompt.debug("Starting loop.exec_() for {}".format(question))
            flags = typing.cast(QEventLoop.ProcessEventsFlags,
                                QEventLoop.ExcludeSocketNotifiers)
            loop.exec_(flags)
            log.prompt.debug("Ending loop.exec_() for {}".format(question))

            log.prompt.debug("Restoring old question {}".format(old_question))
            self._question = old_question
            self.show_prompts.emit(old_question)
            if old_question is None:
                # Nothing left to restore, so we can go back to popping async
                # questions.
                if self._queue:
                    self._pop_later()

            return question.answer
        else:
            question.completed.connect(self._pop_later)
            return None

    @pyqtSlot(usertypes.KeyMode)
    def _on_mode_left(self, mode):
        """Abort question when a prompt mode was left."""
        if mode not in [usertypes.KeyMode.prompt, usertypes.KeyMode.yesno]:
            return
        if self._question is None:
            return

        log.prompt.debug("Left mode {}, hiding {}".format(
            mode, self._question))
        self.show_prompts.emit(None)
        if self._question.answer is None and not self._question.is_aborted:
            log.prompt.debug("Cancelling {} because {} was left".format(
                self._question, mode))
            self._question.cancel()
        self._question = None


class PromptContainer(QWidget):

    """Container for prompts to be shown above the statusbar.

    This is a per-window object, however each window shows the same prompt.

    Attributes:
        _layout: The layout used to show prompts in.
        _win_id: The window ID this object is associated with.

    Signals:
        update_geometry: Emitted when the geometry should be updated.
    """

    STYLESHEET = """
        QWidget#PromptContainer {
            {% if conf.statusbar.position == 'top' %}
                border-bottom-left-radius: {{ conf.prompt.radius }}px;
                border-bottom-right-radius: {{ conf.prompt.radius }}px;
            {% else %}
                border-top-left-radius: {{ conf.prompt.radius }}px;
                border-top-right-radius: {{ conf.prompt.radius }}px;
            {% endif %}
        }

        QWidget {
            font: {{ conf.fonts.prompts }};
            color: {{ conf.colors.prompts.fg }};
            background-color: {{ conf.colors.prompts.bg }};
        }

        QLineEdit {
            border: {{ conf.colors.prompts.border }};
        }

        QTreeView {
            selection-background-color: {{ conf.colors.prompts.selected.bg }};
            border: {{ conf.colors.prompts.border }};
        }

        QTreeView::branch {
            background-color: {{ conf.colors.prompts.bg }};
        }

        QTreeView::item:selected, QTreeView::item:selected:hover,
        QTreeView::branch:selected {
            background-color: {{ conf.colors.prompts.selected.bg }};
        }
    """
    update_geometry = pyqtSignal()

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(10, 10, 10, 10)
        self._win_id = win_id
        self._prompt = None  # type: typing.Optional[_BasePrompt]

        self.setObjectName('PromptContainer')
        self.setAttribute(Qt.WA_StyledBackground, True)
        stylesheet.set_register(self)

        message.global_bridge.prompt_done.connect(self._on_prompt_done)
        prompt_queue.show_prompts.connect(self._on_show_prompts)
        message.global_bridge.mode_left.connect(self._on_global_mode_left)

    def __repr__(self):
        return utils.get_repr(self, win_id=self._win_id)

    @pyqtSlot(usertypes.Question)
    def _on_show_prompts(self, question):
        """Show a prompt for the given question.

        Args:
            question: A Question object or None.
        """
        item = self._layout.takeAt(0)
        if item is not None:
            widget = item.widget()
            log.prompt.debug("Deleting old prompt {}".format(widget))
            widget.hide()
            widget.deleteLater()

        if question is None:
            log.prompt.debug("No prompts left, hiding prompt container.")
            self._prompt = None
            self.hide()
            return

        classes = {
            usertypes.PromptMode.yesno: YesNoPrompt,
            usertypes.PromptMode.text: LineEditPrompt,
            usertypes.PromptMode.user_pwd: AuthenticationPrompt,
            usertypes.PromptMode.download: DownloadFilenamePrompt,
            usertypes.PromptMode.alert: AlertPrompt,
        }
        klass = classes[question.mode]
        prompt = klass(question)

        log.prompt.debug("Displaying prompt {}".format(prompt))
        self._prompt = prompt

        # If this question was interrupted, we already connected the signal
        if not question.interrupted:
            question.aborted.connect(
                functools.partial(self._on_aborted, prompt.KEY_MODE))
        modeman.enter(self._win_id, prompt.KEY_MODE, 'question asked')

        self.setSizePolicy(prompt.sizePolicy())
        self._layout.addWidget(prompt)
        prompt.show()
        self.show()
        prompt.setFocus()
        self.update_geometry.emit()

    @pyqtSlot()
    def _on_aborted(self, key_mode):
        """Leave KEY_MODE whenever a prompt is aborted."""
        try:
            modeman.leave(self._win_id, key_mode, 'aborted', maybe=True)
        except objreg.RegistryUnavailableError:
            # window was deleted: ignore
            pass

    @pyqtSlot(usertypes.KeyMode)
    def _on_prompt_done(self, key_mode):
        """Leave the prompt mode in this window if a question was answered."""
        modeman.leave(self._win_id, key_mode, ':prompt-accept', maybe=True)

    @pyqtSlot(usertypes.KeyMode)
    def _on_global_mode_left(self, mode):
        """Leave prompt/yesno mode in this window if it was left elsewhere.

        This ensures no matter where a prompt was answered, we leave the prompt
        mode and dispose of the prompt object in every window.
        """
        if mode not in [usertypes.KeyMode.prompt, usertypes.KeyMode.yesno]:
            return
        modeman.leave(self._win_id, mode, 'left in other window', maybe=True)
        item = self._layout.takeAt(0)
        if item is not None:
            widget = item.widget()
            log.prompt.debug("Deleting prompt {}".format(widget))
            widget.hide()
            widget.deleteLater()

    @cmdutils.register(instance='prompt-container', scope='window',
                       modes=[usertypes.KeyMode.prompt,
                              usertypes.KeyMode.yesno])
    def prompt_accept(self, value=None, *, save=False):
        """Accept the current prompt.

        //

        This executes the next action depending on the question mode, e.g. asks
        for the password or leaves the mode.

        Args:
            value: If given, uses this value instead of the entered one.
                   For boolean prompts, "yes"/"no" are accepted as value.
            save: Save the value to the config.
        """
        assert self._prompt is not None
        question = self._prompt.question

        try:
            done = self._prompt.accept(value, save=save)
        except Error as e:
            raise cmdutils.CommandError(str(e))

        if done:
            message.global_bridge.prompt_done.emit(self._prompt.KEY_MODE)
            question.done()

    @cmdutils.register(instance='prompt-container', scope='window',
                       modes=[usertypes.KeyMode.prompt], maxsplit=0)
    def prompt_open_download(self, cmdline: str = None,
                             pdfjs: bool = False) -> None:
        """Immediately open a download.

        If no specific command is given, this will use the system's default
        application to open the file.

        Args:
            cmdline: The command which should be used to open the file. A `{}`
                     is expanded to the temporary file name. If no `{}` is
                     present, the filename is automatically appended to the
                     cmdline.
            pdfjs: Open the download via PDF.js.
        """
        assert self._prompt is not None
        try:
            self._prompt.download_open(cmdline, pdfjs=pdfjs)
        except UnsupportedOperationError:
            pass

    @cmdutils.register(instance='prompt-container', scope='window',
                       modes=[usertypes.KeyMode.prompt])
    @cmdutils.argument('which', choices=['next', 'prev'])
    def prompt_item_focus(self, which):
        """Shift the focus of the prompt file completion menu to another item.

        Args:
            which: 'next', 'prev'
        """
        assert self._prompt is not None
        try:
            self._prompt.item_focus(which)
        except UnsupportedOperationError:
            pass

    @cmdutils.register(
        instance='prompt-container', scope='window',
        modes=[usertypes.KeyMode.prompt, usertypes.KeyMode.yesno])
    def prompt_yank(self, sel=False):
        """Yank URL to clipboard or primary selection.

        Args:
            sel: Use the primary selection instead of the clipboard.
        """
        assert self._prompt is not None
        question = self._prompt.question
        if question.url is None:
            message.error('No URL found.')
            return
        if sel and utils.supports_selection():
            target = 'primary selection'
        else:
            sel = False
            target = 'clipboard'
        utils.set_clipboard(question.url, sel)
        message.info("Yanked to {}: {}".format(target, question.url))


class LineEdit(QLineEdit):

    """A line edit used in prompts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
            }
        """)
        self.setAttribute(Qt.WA_MacShowFocusRect, False)

    def keyPressEvent(self, e):
        """Override keyPressEvent to paste primary selection on Shift + Ins."""
        if e.key() == Qt.Key_Insert and e.modifiers() == Qt.ShiftModifier:
            try:
                text = utils.get_clipboard(selection=True, fallback=True)
            except utils.ClipboardError:  # pragma: no cover
                e.ignore()
            else:
                e.accept()
                self.insert(text)
            return
        super().keyPressEvent(e)

    def __repr__(self):
        return utils.get_repr(self)


class _BasePrompt(QWidget):

    """Base class for all prompts."""

    KEY_MODE = usertypes.KeyMode.prompt

    def __init__(self, question, parent=None):
        super().__init__(parent)
        self.question = question
        self._vbox = QVBoxLayout(self)
        self._vbox.setSpacing(15)
        self._key_grid = None

    def __repr__(self):
        return utils.get_repr(self, question=self.question, constructor=True)

    def _init_texts(self, question):
        assert question.title is not None, question
        title = '<font size="4"><b>{}</b></font>'.format(
            html.escape(question.title))
        title_label = QLabel(title, self)
        self._vbox.addWidget(title_label)
        if question.text is not None:
            # Not doing any HTML escaping here as the text can be formatted
            text_label = QLabel(question.text)
            text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self._vbox.addWidget(text_label)

    def _init_key_label(self):
        assert self._key_grid is None, self._key_grid
        self._key_grid = QGridLayout()
        self._key_grid.setVerticalSpacing(0)

        all_bindings = config.key_instance.get_reverse_bindings_for(
            self.KEY_MODE.name)
        labels = []

        for cmd, text in self._allowed_commands():
            bindings = all_bindings.get(cmd, [])
            if bindings:
                binding = None
                preferred = ['<enter>', '<escape>']
                for pref in preferred:
                    if pref in bindings:
                        binding = pref
                if binding is None:
                    binding = bindings[0]
                key_label = QLabel('<b>{}</b>'.format(html.escape(binding)))
                text_label = QLabel(text)
                labels.append((key_label, text_label))

        for i, (key_label, text_label) in enumerate(labels):
            self._key_grid.addWidget(key_label, i, 0)
            self._key_grid.addWidget(text_label, i, 1)

        spacer = QSpacerItem(0, 0, QSizePolicy.Expanding)
        self._key_grid.addItem(spacer, 0, 2)

        self._vbox.addLayout(self._key_grid)

    def _check_save_support(self, save):
        if save:
            raise UnsupportedOperationError("Saving answers is only possible "
                                            "with yes/no prompts.")

    def accept(self, value=None, save=False):
        raise NotImplementedError

    def download_open(self, cmdline, pdfjs):
        """Open the download directly if this is a download prompt."""
        utils.unused(cmdline)
        utils.unused(pdfjs)
        raise UnsupportedOperationError

    def item_focus(self, _which):
        """Switch to next file item if this is a filename prompt.."""
        raise UnsupportedOperationError

    def _allowed_commands(self):
        """Get the commands we could run as response to this message."""
        raise NotImplementedError


class LineEditPrompt(_BasePrompt):

    """A prompt for a single text value."""

    def __init__(self, question, parent=None):
        super().__init__(question, parent)
        self._lineedit = LineEdit(self)
        self._init_texts(question)
        self._vbox.addWidget(self._lineedit)
        if question.default:
            self._lineedit.setText(question.default)
        self.setFocusProxy(self._lineedit)
        self._init_key_label()

    def accept(self, value=None, save=False):
        self._check_save_support(save)
        text = value if value is not None else self._lineedit.text()
        self.question.answer = text
        return True

    def _allowed_commands(self):
        return [('prompt-accept', 'Accept'), ('leave-mode', 'Abort')]


class FilenamePrompt(_BasePrompt):

    """A prompt for a filename."""

    def __init__(self, question, parent=None):
        super().__init__(question, parent)
        self._init_texts(question)
        self._init_key_label()

        self._lineedit = LineEdit(self)
        if question.default:
            self._lineedit.setText(question.default)
        self._lineedit.textEdited.connect(self._set_fileview_root)
        self._vbox.addWidget(self._lineedit)

        self.setFocusProxy(self._lineedit)

        self._init_fileview()
        self._set_fileview_root(question.default)

        if config.val.prompt.filebrowser:
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self._to_complete = ''

    @pyqtSlot(str)
    def _set_fileview_root(self, path, *, tabbed=False):
        """Set the root path for the file display."""
        separators = os.sep
        if os.altsep is not None:
            separators += os.altsep

        dirname = os.path.dirname(path)
        basename = os.path.basename(path)
        if not tabbed:
            self._to_complete = ''

        try:
            if not path:
                pass
            elif path in separators and os.path.isdir(path):
                # Input "/" -> don't strip anything
                pass
            elif path[-1] in separators and os.path.isdir(path):
                # Input like /foo/bar/ -> show /foo/bar/ contents
                path = path.rstrip(separators)
            elif os.path.isdir(dirname) and not tabbed:
                # Input like /foo/ba -> show /foo contents
                path = dirname
                self._to_complete = basename
            else:
                return
        except OSError:
            log.prompt.exception("Failed to get directory information")
            return

        root = self._file_model.setRootPath(path)
        self._file_view.setRootIndex(root)

    @pyqtSlot(QModelIndex)
    def _insert_path(self, index, *, clicked=True):
        """Handle an element selection.

        Args:
            index: The QModelIndex of the selected element.
            clicked: Whether the element was clicked.
        """
        if index == QModelIndex():
            path = os.path.join(self._file_model.rootPath(), self._to_complete)
        else:
            path = os.path.normpath(self._file_model.filePath(index))

        if clicked:
            path += os.sep
        else:
            # On Windows, when we have C:\foo and tab over .., we get C:\
            path = path.rstrip(os.sep)

        log.prompt.debug('Inserting path {}'.format(path))
        self._lineedit.setText(path)
        self._lineedit.setFocus()
        self._set_fileview_root(path, tabbed=True)
        if clicked:
            # Avoid having a ..-subtree highlighted
            self._file_view.setCurrentIndex(QModelIndex())

    def _init_fileview(self):
        self._file_view = QTreeView(self)
        self._file_model = QFileSystemModel(self)
        self._file_view.setModel(self._file_model)
        self._file_view.clicked.connect(self._insert_path)

        if config.val.prompt.filebrowser:
            self._vbox.addWidget(self._file_view)
        else:
            self._file_view.hide()

        # Only show name
        self._file_view.setHeaderHidden(True)
        for col in range(1, 4):
            self._file_view.setColumnHidden(col, True)
        # Nothing selected initially
        self._file_view.setCurrentIndex(QModelIndex())
        # The model needs to be sorted so we get the correct first/last index
        self._file_model.directoryLoaded.connect(
            lambda: self._file_model.sort(0))

    def accept(self, value=None, save=False):
        self._check_save_support(save)
        text = value if value is not None else self._lineedit.text()
        text = downloads.transform_path(text)
        if text is None:
            message.error("Invalid filename")
            return False
        self.question.answer = text
        return True

    def item_focus(self, which):
        # This duplicates some completion code, but I don't see a nicer way...
        assert which in ['prev', 'next'], which
        selmodel = self._file_view.selectionModel()

        parent = self._file_view.rootIndex()
        first_index = self._file_model.index(0, 0, parent)
        row = self._file_model.rowCount(parent) - 1
        last_index = self._file_model.index(row, 0, parent)

        if not first_index.isValid():
            # No entries
            return

        assert last_index.isValid()

        idx = selmodel.currentIndex()

        if not idx.isValid():
            # No item selected yet
            idx = last_index if which == 'prev' else first_index
        elif which == 'prev':
            idx = self._file_view.indexAbove(idx)
        else:
            assert which == 'next', which
            idx = self._file_view.indexBelow(idx)

        # wrap around if we arrived at beginning/end
        if not idx.isValid():
            idx = last_index if which == 'prev' else first_index

        idx = self._do_completion(idx, which)

        selmodel.setCurrentIndex(
            idx,
            QItemSelectionModel.ClearAndSelect |  # type: ignore[arg-type]
            QItemSelectionModel.Rows)
        self._insert_path(idx, clicked=False)

    def _do_completion(self, idx, which):
        filename = self._file_model.fileName(idx)
        while not filename.startswith(self._to_complete) and idx.isValid():
            if which == 'prev':
                idx = self._file_view.indexAbove(idx)
            else:
                assert which == 'next', which
                idx = self._file_view.indexBelow(idx)
            filename = self._file_model.fileName(idx)

        return idx

    def _allowed_commands(self):
        return [('prompt-accept', 'Accept'), ('leave-mode', 'Abort')]


class DownloadFilenamePrompt(FilenamePrompt):

    """A prompt for a filename for downloads."""

    def __init__(self, question, parent=None):
        super().__init__(question, parent)
        self._file_model.setFilter(
            QDir.AllDirs | QDir.Drives | QDir.NoDot)  # type: ignore[arg-type]

    def accept(self, value=None, save=False):
        done = super().accept(value, save)
        answer = self.question.answer
        if answer is not None:
            self.question.answer = downloads.FileDownloadTarget(answer)
        return done

    def download_open(self, cmdline, pdfjs):
        if pdfjs:
            target = downloads.PDFJSDownloadTarget(
            )  # type: downloads._DownloadTarget
        else:
            target = downloads.OpenFileDownloadTarget(cmdline)

        self.question.answer = target
        self.question.done()
        message.global_bridge.prompt_done.emit(self.KEY_MODE)

    def _allowed_commands(self):
        cmds = [
            ('prompt-accept', 'Accept'),
            ('leave-mode', 'Abort'),
            ('prompt-open-download', "Open download"),
            ('prompt-open-download --pdfjs', "Open download via PDF.js"),
            ('prompt-yank', "Yank URL"),
        ]
        return cmds


class AuthenticationPrompt(_BasePrompt):

    """A prompt for username/password."""

    def __init__(self, question, parent=None):
        super().__init__(question, parent)
        self._init_texts(question)

        user_label = QLabel("Username:", self)
        self._user_lineedit = LineEdit(self)

        password_label = QLabel("Password:", self)
        self._password_lineedit = LineEdit(self)
        self._password_lineedit.setEchoMode(QLineEdit.Password)

        grid = QGridLayout()
        grid.addWidget(user_label, 1, 0)
        grid.addWidget(self._user_lineedit, 1, 1)
        grid.addWidget(password_label, 2, 0)
        grid.addWidget(self._password_lineedit, 2, 1)
        self._vbox.addLayout(grid)
        self._init_key_label()

        assert not question.default, question.default
        self.setFocusProxy(self._user_lineedit)

    def accept(self, value=None, save=False):
        self._check_save_support(save)
        if value is not None:
            if ':' not in value:
                raise Error("Value needs to be in the format "
                            "username:password, but {} was given".format(
                                value))
            username, password = value.split(':', maxsplit=1)
            self.question.answer = AuthInfo(username, password)
            return True
        elif self._user_lineedit.hasFocus():
            # Earlier, tab was bound to :prompt-accept, so to still support
            # that we simply switch the focus when tab was pressed.
            self._password_lineedit.setFocus()
            return False
        else:
            self.question.answer = AuthInfo(self._user_lineedit.text(),
                                            self._password_lineedit.text())
            return True

    def item_focus(self, which):
        """Support switching between fields with tab."""
        assert which in ['prev', 'next'], which
        if which == 'next' and self._user_lineedit.hasFocus():
            self._password_lineedit.setFocus()
        elif which == 'prev' and self._password_lineedit.hasFocus():
            self._user_lineedit.setFocus()

    def _allowed_commands(self):
        return [('prompt-accept', "Accept"),
                ('leave-mode', "Abort")]


class YesNoPrompt(_BasePrompt):

    """A prompt with yes/no answers."""

    KEY_MODE = usertypes.KeyMode.yesno

    def __init__(self, question, parent=None):
        super().__init__(question, parent)
        self._init_texts(question)
        self._init_key_label()

    def _check_save_support(self, save):
        if save and self.question.option is None:
            raise Error("No setting available to save the answer for this "
                        "question.")

    def accept(self, value=None, save=False):
        self._check_save_support(save)

        if value is None:
            if self.question.default is None:
                raise Error("No default value was set for this question!")
            self.question.answer = self.question.default
        elif value == 'yes':
            self.question.answer = True
        elif value == 'no':
            self.question.answer = False
        else:
            raise Error("Invalid value {} - expected yes/no!".format(value))

        if save:
            opt = config.instance.get_opt(self.question.option)
            assert isinstance(opt.typ, configtypes.Bool)
            pattern = urlmatch.UrlPattern(self.question.url)

            try:
                config.instance.set_obj(opt.name, self.question.answer,
                                        pattern=pattern, save_yaml=True)
            except configexc.Error as e:
                raise Error(str(e))

        return True

    def _allowed_commands(self):
        cmds = []

        cmds.append(('prompt-accept yes', "Yes"))
        if self.question.option is not None:
            cmds.append(('prompt-accept --save yes', "Always"))

        cmds.append(('prompt-accept no', "No"))
        if self.question.option is not None:
            cmds.append(('prompt-accept --save no', "Never"))

        if self.question.default is not None:
            assert self.question.default in [True, False]
            default = 'yes' if self.question.default else 'no'
            cmds.append(('prompt-accept', "Use default ({})".format(default)))

        cmds.append(('leave-mode', "Abort"))
        cmds.append(('prompt-yank', "Yank URL"))
        return cmds


class AlertPrompt(_BasePrompt):

    """A prompt without any answer possibility."""

    def __init__(self, question, parent=None):
        super().__init__(question, parent)
        self._init_texts(question)
        self._init_key_label()

    def accept(self, value=None, save=False):
        self._check_save_support(save)
        if value is not None:
            raise Error("No value is permitted with alert prompts!")
        # Simply mark prompt as done without setting self.question.answer
        return True

    def _allowed_commands(self):
        return [('prompt-accept', "Hide")]


def init():
    """Initialize global prompt objects."""
    global prompt_queue
    prompt_queue = PromptQueue()
    message.global_bridge.ask_question.connect(  # type: ignore[call-arg]
        prompt_queue.ask_question, Qt.DirectConnection)
