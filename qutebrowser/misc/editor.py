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

"""Launcher for an external editor."""

import os
import tempfile

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QProcess

from qutebrowser.config import config
from qutebrowser.utils import message, log
from qutebrowser.misc import guiprocess


class ExternalEditor(QObject):

    """Class to simplify editing a text in an external editor.

    Attributes:
        _text: The current text before the editor is opened.
        _file: The file handle as tempfile.NamedTemporaryFile. Note that this
               handle will be closed after the initial file has been created.
        _proc: The GUIProcess of the editor.
    """

    editing_finished = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = None
        self._file = None
        self._proc = None

    def _cleanup(self):
        """Clean up temporary files after the editor closed."""
        if self._file is None:
            # Could not create initial file.
            return
        try:
            if self._proc.exit_status() != QProcess.CrashExit:
                os.remove(self._file.name)
        except OSError as e:
            # NOTE: Do not replace this with "raise CommandError" as it's
            # executed async.
            message.error("Failed to delete tempfile... ({})".format(e))

    @pyqtSlot(int, QProcess.ExitStatus)
    def on_proc_closed(self, exitcode, exitstatus):
        """Write the editor text into the form field and clean up tempfile.

        Callback for QProcess when the editor was closed.
        """
        log.procs.debug("Editor closed")
        if exitstatus != QProcess.NormalExit:
            # No error/cleanup here, since we already handle this in
            # on_proc_error.
            return
        try:
            if exitcode != 0:
                return
            encoding = config.get('general', 'editor-encoding')
            try:
                with open(self._file.name, 'r', encoding=encoding) as f:
                    text = f.read()
            except OSError as e:
                # NOTE: Do not replace this with "raise CommandError" as it's
                # executed async.
                message.error("Failed to read back edited file: {}".format(e))
                return
            log.procs.debug("Read back: {}".format(text))
            self.editing_finished.emit(text)
        finally:
            self._cleanup()

    @pyqtSlot(QProcess.ProcessError)
    def on_proc_error(self, _err):
        self._cleanup()

    def edit(self, text):
        """Edit a given text.

        Args:
            text: The initial text to edit.
        """
        if self._text is not None:
            raise ValueError("Already editing a file!")
        self._text = text
        encoding = config.get('general', 'editor-encoding')
        try:
            # Close while the external process is running, as otherwise systems
            # with exclusive write access (e.g. Windows) may fail to update
            # the file from the external editor, see
            # https://github.com/The-Compiler/qutebrowser/issues/1767
            with tempfile.NamedTemporaryFile(
                    mode='w', prefix='qutebrowser-editor-', encoding=encoding,
                    delete=False) as fobj:
                if text:
                    fobj.write(text)
                self._file = fobj
        except OSError as e:
            message.error("Failed to create initial file: {}".format(e))
            return
        self._proc = guiprocess.GUIProcess(what='editor', parent=self)
        self._proc.finished.connect(self.on_proc_closed)
        self._proc.error.connect(self.on_proc_error)
        editor = config.get('general', 'editor')
        executable = editor[0]
        args = [arg.replace('{}', self._file.name) for arg in editor[1:]]
        log.procs.debug("Calling \"{}\" with args {}".format(executable, args))
        self._proc.start(executable, args)
