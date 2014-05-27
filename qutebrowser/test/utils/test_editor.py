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

"""Tests for qutebrowser.utils.editor."""

import os
import os.path
import logging
import unittest
from unittest import TestCase
from unittest.mock import Mock

from PyQt5.QtCore import QProcess

import qutebrowser.utils.editor as editor


class ConfigStub:

    """Stub for editor.config."""

    def __init__(self, editor):
        self.editor = editor

    def get(self, sect, opt):
        if sect == 'general' and opt == 'editor':
            return self.editor
        else:
            raise ValueError("Invalid option {} -> {}".format(sect, opt))


class FakeQProcess:

    NormalExit = QProcess.NormalExit
    CrashExit = QProcess.CrashExit

    FailedToStart = QProcess.FailedToStart
    Crashed = QProcess.Crashed
    Timedout = QProcess.Timedout
    WriteError = QProcess.WriteError
    ReadError = QProcess.ReadError
    UnknownError = QProcess.UnknownError

    def __init__(self, parent=None):
        self.finished = Mock()
        self.error = Mock()
        self.start = Mock()


def setUpModule():
    editor.message = Mock()
    editor.logger = Mock()
    editor.QProcess = FakeQProcess


class FileHandlingTests(TestCase):

    """Test creation/deletion of tempfile."""

    def setUp(self):
        self.editor = editor.ExternalEditor()
        self.editor.editing_finished = Mock()
        editor.config = ConfigStub(editor=[""])

    def test_file_handling_closed_ok(self):
        """Test file handling when closing with an exitstatus == 0."""
        self.editor.edit("")
        filename = self.editor.filename
        self.assertTrue(os.path.exists(filename))
        self.editor.on_proc_closed(0, QProcess.NormalExit)
        self.assertFalse(os.path.exists(filename))

    def test_file_handling_closed_error(self):
        """Test file handling when closing with an exitstatus != 0."""
        self.editor.edit("")
        filename = self.editor.filename
        self.assertTrue(os.path.exists(filename))
        self.editor.on_proc_closed(1, QProcess.NormalExit)
        self.assertFalse(os.path.exists(filename))

    def test_file_handling_closed_crash(self):
        """Test file handling when closing with a crash."""
        self.editor.edit("")
        filename = self.editor.filename
        self.assertTrue(os.path.exists(filename))
        self.editor.on_proc_error(QProcess.Crashed)
        self.editor.on_proc_closed(0, QProcess.CrashExit)
        self.assertFalse(os.path.exists(filename))


if __name__ == '__main__':
    unittest.main()
