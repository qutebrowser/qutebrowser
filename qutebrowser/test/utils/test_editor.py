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

    """Stub for editor.config.

    Attributes:
        editor: The editor to return for general -> editor.
    """

    def __init__(self, editor):
        self.editor = editor

    def get(self, sect, opt):
        if sect == 'general' and opt == 'editor':
            return self.editor
        else:
            raise ValueError("Invalid option {} -> {}".format(sect, opt))


class FakeQProcess:

    """QProcess stub.

    Gets some enum values from the real QProcess and uses mocks for signals.
    """

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
    """Mock some things imported in the editor module."""
    editor.message = Mock()
    editor.logger = Mock()
    editor.QProcess = FakeQProcess


class ArgTests(TestCase):

    """Test argument handling."""

    def setUp(self):
        self.editor = editor.ExternalEditor()

    def test_simple_start_args(self):
        """Test starting editor without arguments."""
        editor.config = ConfigStub(editor=["executable"])
        self.editor.edit("")
        self.editor.proc.start.assert_called_with("executable", [])

    def test_start_args(self):
        """Test starting editor with static arguments."""
        editor.config = ConfigStub(editor=["executable", "foo", "bar"])
        self.editor.edit("")
        self.editor.proc.start.assert_called_with("executable", ["foo", "bar"])

    def test_placeholder(self):
        """Test starting editor with placeholder argument."""
        editor.config = ConfigStub(editor=["executable", "foo", "{}", "bar"])
        self.editor.edit("")
        filename = self.editor.filename
        self.editor.proc.start.assert_called_with(
            "executable", ["foo", filename, "bar"])

    def test_in_arg_placeholder(self):
        """Test starting editor with placeholder argument inside argument."""
        editor.config = ConfigStub(editor=["executable", "foo{}bar"])
        self.editor.edit("")
        filename = self.editor.filename
        self.editor.proc.start.assert_called_with("executable", ["foo{}bar"])

    def tearDown(self):
        self.editor._cleanup()


class FileHandlingTests(TestCase):

    """Test creation/deletion of tempfile."""

    def setUp(self):
        self.editor = editor.ExternalEditor()
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


class TextModifyTests(TestCase):

    """Tests to test if the text gets saved/loaded correctly."""

    def setUp(self):
        self.editor = editor.ExternalEditor()
        self.editor.editing_finished = Mock()
        editor.config = ConfigStub(editor=[""])

    def _write(self, text):
        """Write a text to the file opened in the fake editor."""
        filename = self.editor.filename
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(text)

    def _read(self):
        """Read a text from the file opened in the fake editor."""
        filename = self.editor.filename
        with open(filename, 'r', encoding='utf-8') as f:
            data = f.read()
        return data

    def test_empty_input(self):
        """Test if an empty input gets modified correctly."""
        self.editor.edit("")
        self.assertEqual(self._read(), "")
        self._write("Hello")
        self.editor.on_proc_closed(0, QProcess.NormalExit)
        self.editor.editing_finished.emit.assert_called_with("Hello")

    def test_simple_input(self):
        """Test if an empty input gets modified correctly."""
        self.editor.edit("Hello")
        self.assertEqual(self._read(), "Hello")
        self._write("World")
        self.editor.on_proc_closed(0, QProcess.NormalExit)
        self.editor.editing_finished.emit.assert_called_with("World")

    def test_umlaut(self):
        """Test if umlauts works correctly."""
        self.editor.edit("Hällö Wörld")
        self.assertEqual(self._read(), "Hällö Wörld")
        self._write("Überprüfung")
        self.editor.on_proc_closed(0, QProcess.NormalExit)
        self.editor.editing_finished.emit.assert_called_with("Überprüfung")

    def test_unicode(self):
        """Test if other UTF8 chars work correctly."""
        self.editor.edit("\u2603")  # Unicode snowman
        self.assertEqual(self._read(), "\u2603")
        self._write("\u2601")  # Cloud
        self.editor.on_proc_closed(0, QProcess.NormalExit)
        self.editor.editing_finished.emit.assert_called_with("\u2601")


class ErrorMessageTests(TestCase):

    """Test if statusbar error messages get emitted correctly."""

    def setUp(self):
        self.editor = editor.ExternalEditor()
        editor.config = ConfigStub(editor=[""])

    def test_proc_error(self):
        """Test on_proc_error."""
        self.editor.edit("")
        self.editor.on_proc_error(QProcess.Crashed)
        self.assertTrue(editor.message.error.called)

    def test_proc_return(self):
        """Test on_proc_finished with a bad exit status."""
        self.editor.edit("")
        self.editor.on_proc_closed(1, QProcess.NormalExit)
        self.assertTrue(editor.message.error.called)


if __name__ == '__main__':
    unittest.main()
