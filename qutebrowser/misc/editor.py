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
import itertools


class ExternalEditor(QObject):

    """Class to simplify editing a text in an external editor.

    Attributes:
        _text: The current text before the editor is opened.
        _oshandle: The OS level handle to the tmpfile.
        _filehandle: The file handle to the tmpfile.
        _proc: The GUIProcess of the editor.
        _win_id: The window ID the ExternalEditor is associated with.
    """

    editing_finished = pyqtSignal(str)

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        self._text = None
        self._oshandle = None
        self._filename = None
        self._proc = None
        self._win_id = win_id

    def _cleanup(self):
        """Clean up temporary files after the editor closed."""
        if self._oshandle is None or self._filename is None:
            # Could not create initial file.
            return
        try:
            os.close(self._oshandle)
            if self._proc.exit_status() != QProcess.CrashExit:
                os.remove(self._filename)
        except OSError as e:
            # NOTE: Do not replace this with "raise CommandError" as it's
            # executed async.
            message.error(self._win_id,
                          "Failed to delete tempfile... ({})".format(e))

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
                with open(self._filename, 'r', encoding=encoding) as f:
                    self._text = f.read()
            except OSError as e:
                # NOTE: Do not replace this with "raise CommandError" as it's
                # executed async.
                message.error(self._win_id, "Failed to read back edited file: "
                                            "{}".format(e))
                return
            log.procs.debug("Read back: {}".format(self._text))
            self.editing_finished.emit(self._text)

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
        try:
            self._oshandle, self._filename = tempfile.mkstemp(
                text=True, prefix='qutebrowser-editor-')
            if text:
                encoding = config.get('general', 'editor-encoding')
                with open(self._filename, 'w', encoding=encoding) as f:
                    f.write(text)
        except OSError as e:
            message.error(self._win_id, "Failed to create initial file: "
                                        "{}".format(e))
            return
        self._proc = guiprocess.GUIProcess(self._win_id, what='editor',
                                           parent=self)
        self._proc.finished.connect(self.on_proc_closed)
        self._proc.error.connect(self.on_proc_error)
        editor = config.get('general', 'editor')
        executable = editor[0]
        args = [arg.replace('{}', self._filename) for arg in editor[1:]]
        log.procs.debug("Calling \"{}\" with args {}".format(executable, args))
        self._proc.start(executable, args)

    def emergency_save(self):
        """Save the current text to a (permanent) temp file.

        This can be used to make a backup if the result of editing cannot be
        used as intended. Outputs an error message telling the user where to
        find this backup file.
        """
        output_file = self._mk_emergency_filename()

        encoding = config.get('general', 'editor-encoding')
        with open(output_file, 'w', encoding=encoding) as f:
            f.write(self._text)

        msg = ("Failed to set externally edited "
               "text. Backup saved to %s" % output_file)
        message.error(self._win_id, msg)

    def _mk_emergency_filename(self):
        for file_id in itertools.count():
            emergency_filename = os.path.join(
                tempfile.gettempdir(),
                'qutebrowser-editor-backup-%d.txt' % file_id
            )

            if not os.path.exists(emergency_filename):
                return emergency_filename
