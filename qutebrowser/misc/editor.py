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

"""Launcher for an external editor."""

import os
import tempfile

from PyQt5.QtCore import (pyqtSignal, pyqtSlot, QObject, QProcess,
                          QFileSystemWatcher)

from qutebrowser.config import config
from qutebrowser.utils import message, log
from qutebrowser.misc import guiprocess


class ExternalEditor(QObject):

    """Class to simplify editing a text in an external editor.

    Attributes:
        _text: The current text before the editor is opened.
        _filename: The name of the file to be edited.
        _remove_file: Whether the file should be removed when the editor is
                      closed.
        _proc: The GUIProcess of the editor.
        _watcher: A QFileSystemWatcher to watch the edited file for changes.
                  Only set if watch=True.
        _content: The last-saved text of the editor.

    Signals:
        file_updated: The text in the edited file was updated.
                      arg: The new text.
        editing_finished: The editor process was closed.
    """

    file_updated = pyqtSignal(str)
    editing_finished = pyqtSignal()

    def __init__(self, parent=None, watch=False):
        super().__init__(parent)
        self._filename = None
        self._proc = None
        self._remove_file = None
        self._watcher = QFileSystemWatcher(parent=self) if watch else None
        self._content = None

    def _cleanup(self):
        """Clean up temporary files after the editor closed."""
        assert self._remove_file is not None
        if self._watcher is not None and self._watcher.files():
            failed = self._watcher.removePaths(self._watcher.files())
            if failed:
                log.procs.error("Failed to unwatch paths: {}".format(failed))

        if self._filename is None or not self._remove_file:
            # Could not create initial file.
            return

        assert self._proc is not None

        try:
            if self._proc.exit_status() != QProcess.CrashExit:
                os.remove(self._filename)
        except OSError as e:
            # NOTE: Do not replace this with "raise CommandError" as it's
            # executed async.
            message.error("Failed to delete tempfile... ({})".format(e))

    @pyqtSlot(int, QProcess.ExitStatus)
    def _on_proc_closed(self, _exitcode, exitstatus):
        """Write the editor text into the form field and clean up tempfile.

        Callback for QProcess when the editor was closed.
        """
        log.procs.debug("Editor closed")
        if exitstatus != QProcess.NormalExit:
            # No error/cleanup here, since we already handle this in
            # on_proc_error.
            return
        # do a final read to make sure we don't miss the last signal
        self._on_file_changed(self._filename)
        self.editing_finished.emit()
        self._cleanup()

    @pyqtSlot(QProcess.ProcessError)
    def _on_proc_error(self, _err):
        self._cleanup()

    def edit(self, text, caret_position=None):
        """Edit a given text.

        Args:
            text: The initial text to edit.
            caret_position: The position of the caret in the text.
        """
        if self._filename is not None:
            raise ValueError("Already editing a file!")
        try:
            self._filename = self._create_tempfile(text, 'qutebrowser-editor-')
        except OSError as e:
            message.error("Failed to create initial file: {}".format(e))
            return

        self._remove_file = True

        line, column = self._calc_line_and_column(text, caret_position)
        self._start_editor(line=line, column=column)

    def backup(self):
        """Create a backup if the content has changed from the original."""
        if not self._content:
            return
        try:
            fname = self._create_tempfile(self._content,
                                          'qutebrowser-editor-backup-')
            message.info('Editor backup at {}'.format(fname))
        except OSError as e:
            message.error('Failed to create editor backup: {}'.format(e))

    def _create_tempfile(self, text, prefix):
        # Close while the external process is running, as otherwise systems
        # with exclusive write access (e.g. Windows) may fail to update
        # the file from the external editor, see
        # https://github.com/qutebrowser/qutebrowser/issues/1767
        with tempfile.NamedTemporaryFile(
                mode='w', prefix=prefix,
                encoding=config.val.editor.encoding,
                delete=False) as fobj:
            if text:
                fobj.write(text)
            return fobj.name

    @pyqtSlot(str)
    def _on_file_changed(self, path):
        try:
            with open(path, 'r', encoding=config.val.editor.encoding) as f:
                text = f.read()
        except OSError as e:
            # NOTE: Do not replace this with "raise CommandError" as it's
            # executed async.
            message.error("Failed to read back edited file: {}".format(e))
            return
        log.procs.debug("Read back: {}".format(text))
        if self._content != text:
            self._content = text
            self.file_updated.emit(text)

    def edit_file(self, filename):
        """Edit the file with the given filename."""
        self._filename = filename
        self._remove_file = False
        self._start_editor()

    def _start_editor(self, line=1, column=1):
        """Start the editor with the file opened as self._filename.

        Args:
            line: the line number to pass to the editor
            column: the column number to pass to the editor
        """
        self._proc = guiprocess.GUIProcess(what='editor', parent=self)
        self._proc.finished.connect(self._on_proc_closed)
        self._proc.error.connect(self._on_proc_error)
        editor = config.val.editor.command
        executable = editor[0]

        if self._watcher:
            assert self._filename is not None
            ok = self._watcher.addPath(self._filename)
            if not ok:
                log.procs.error("Failed to watch path: {}"
                                .format(self._filename))
            self._watcher.fileChanged.connect(  # type: ignore[attr-defined]
                self._on_file_changed)

        args = [self._sub_placeholder(arg, line, column) for arg in editor[1:]]
        log.procs.debug("Calling \"{}\" with args {}".format(executable, args))
        self._proc.start(executable, args)

    def _calc_line_and_column(self, text, caret_position):
        r"""Calculate line and column numbers given a text and caret position.

        Both line and column are 1-based indexes, because that's what most
        editors use as line and column starting index.  By "most" we mean at
        least vim, nvim, gvim, emacs, atom, sublimetext, notepad++, brackets,
        visual studio, QtCreator and so on.

        To find the line we just count how many newlines there are before the
        caret and add 1.

        To find the column we calculate the difference between the caret and
        the last newline before the caret.

        For example in the text `aaa\nbb|bbb` (| represents the caret):
        caret_position = 6
        text[:caret_position] = `aaa\nbb`
        text[:caret_position].count('\n') = 1
        caret_position - text[:caret_position].rfind('\n') = 3

        Thus line, column = 2, 3, and the caret is indeed in the second
        line, third column

        Args:
            text: the text for which the numbers must be calculated
            caret_position: the position of the caret in the text, or None

        Return:
            A (line, column) tuple of (int, int)
        """
        if caret_position is None:
            return 1, 1
        line = text[:caret_position].count('\n') + 1
        column = caret_position - text[:caret_position].rfind('\n')
        return line, column

    def _sub_placeholder(self, arg, line, column):
        """Substitute a single placeholder.

        If the `arg` input to this function is a valid placeholder it will
        be substituted with the appropriate value, otherwise it will be left
        unchanged.

        Args:
            arg: an argument of editor.command.
            line: the previously-calculated line number for the text caret.
            column: the previously-calculated column number for the text caret.

        Return:
            The substituted placeholder or the original argument.
        """
        replacements = {
            '{}': self._filename,
            '{file}': self._filename,
            '{line}': str(line),
            '{line0}': str(line-1),
            '{column}': str(column),
            '{column0}': str(column-1)
        }

        for old, new in replacements.items():
            arg = arg.replace(old, new)

        return arg
