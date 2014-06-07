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

"""Launcher for an external editor."""

import os
from tempfile import mkstemp

from PyQt5.QtCore import pyqtSignal, QProcess, QObject

import qutebrowser.config.config as config
import qutebrowser.utils.message as message
from qutebrowser.utils.log import procs as logger


class ExternalEditor(QObject):

    """Class to simplify editing a text in an external editor."""

    editing_finished = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.text = None
        self.oshandle = None
        self.filename = None
        self.proc = None

    def _cleanup(self):
        """Clean up temporary files after the editor closed."""
        os.close(self.oshandle)
        try:
            os.remove(self.filename)
        except PermissionError:
            # NOTE: Do not replace this with "raise CommandError" as it's
            # executed async.
            message.error("Failed to delete tempfile...")

    def on_proc_closed(self, exitcode, exitstatus):
        """Write the editor text into the form field and clean up tempfile.

        Callback for QProcess when the editor was closed.

        Emit:
            editing_finished: If process exited normally.
        """
        logger.debug("Editor closed")
        if exitstatus != QProcess.NormalExit:
            # No error/cleanup here, since we already handle this in
            # on_proc_error
            return
        try:
            if exitcode != 0:
                # NOTE: Do not replace this with "raise CommandError" as it's
                # executed async.
                message.error("Editor did quit abnormally (status {})!".format(
                    exitcode))
                return
            with open(self.filename, 'r', encoding='utf-8') as f:
                text = ''.join(f.readlines())
            logger.debug("Read back: {}".format(text))
            self.editing_finished.emit(text)
        finally:
            self._cleanup()

    def on_proc_error(self, error):
        """Display an error message and clean up when editor crashed."""
        messages = {
            QProcess.FailedToStart: "The process failed to start.",
            QProcess.Crashed: "The process crashed.",
            QProcess.Timedout: "The last waitFor...() function timed out.",
            QProcess.WriteError: ("An error occurred when attempting to write "
                                  "to the process."),
            QProcess.ReadError: ("An error occurred when attempting to read "
                                 "from the process."),
            QProcess.UnknownError: "An unknown error occurred.",
        }
        # NOTE: Do not replace this with "raise CommandError" as it's
        # executed async.
        message.error("Error while calling editor: {}".format(messages[error]))
        self._cleanup()

    def edit(self, text):
        """Edit a given text.

        Args:
            text: The initial text to edit.

        Emit:
            editing_finished with the new text if editing finshed successfully.
        """
        if self.text is not None:
            raise ValueError("Already editing a file!")
        self.text = text
        self.oshandle, self.filename = mkstemp(text=True)
        if text:
            with open(self.filename, 'w', encoding='utf-8') as f:
                f.write(text)
        self.proc = QProcess(self)
        self.proc.finished.connect(self.on_proc_closed)
        self.proc.error.connect(self.on_proc_error)
        editor = config.get('general', 'editor')
        executable = editor[0]
        args = [self.filename if arg == '{}' else arg for arg in editor[1:]]
        logger.debug("Calling \"{}\" with args {}".format(executable, args))
        self.proc.start(executable, args)
