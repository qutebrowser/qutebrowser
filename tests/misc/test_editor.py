# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for qutebrowser.misc.editor."""

# pylint: disable=protected-access

import os
import os.path
import logging
from unittest import mock

from PyQt5.QtCore import QProcess
import pytest

from qutebrowser.misc import editor


class TestArg:

    """Test argument handling.

    Attributes:
        editor: The ExternalEditor instance to test.
    """

    @pytest.yield_fixture(autouse=True)
    def setup(self, mocker, stubs):
        mocker.patch('qutebrowser.misc.editor.QProcess',
                     new_callable=stubs.FakeQProcess)
        self.config = stubs.ConfigStub()
        mocker.patch('qutebrowser.misc.editor.config', new=self.config)
        self.editor = editor.ExternalEditor(0)
        yield
        self.editor._cleanup()  # pylint: disable=protected-access

    def test_simple_start_args(self):
        """Test starting editor without arguments."""
        self.config.data = {
            'general': {'editor': ['bin'], 'editor-encoding': 'utf-8'}}
        self.editor.edit("")
        self.editor._proc.start.assert_called_with("bin", [])

    def test_start_args(self):
        """Test starting editor with static arguments."""
        self.config.data = {'general': {'editor': ['bin', 'foo', 'bar'],
                                        'editor-encoding': 'utf-8'}}
        self.editor.edit("")
        self.editor._proc.start.assert_called_with("bin", ["foo", "bar"])

    def test_placeholder(self):
        """Test starting editor with placeholder argument."""
        self.config.data = {'general': {'editor': ['bin', 'foo', '{}', 'bar'],
                                        'editor-encoding': 'utf-8'}}
        self.editor.edit("")
        filename = self.editor._filename
        self.editor._proc.start.assert_called_with(
            "bin", ["foo", filename, "bar"])

    def test_in_arg_placeholder(self):
        """Test starting editor with placeholder argument inside argument."""
        self.config.data = {'general': {'editor': ['bin', 'foo{}bar'],
                                        'editor-encoding': 'utf-8'}}
        self.editor.edit("")
        self.editor._proc.start.assert_called_with("bin", ["foo{}bar"])


class TestFileHandling:

    """Test creation/deletion of tempfile.

    Attributes:
        editor: The ExternalEditor instance to test.
    """

    @pytest.fixture(autouse=True)
    def setup(self, mocker, stubs):
        mocker.patch('qutebrowser.misc.editor.message',
                     new=stubs.MessageModule())
        mocker.patch('qutebrowser.misc.editor.QProcess',
                     new_callable=stubs.FakeQProcess)
        mocker.patch('qutebrowser.misc.editor.config',
                     new=stubs.ConfigStub(
                         {'general': {'editor': [''],
                                      'editor-encoding': 'utf-8'}}))
        self.editor = editor.ExternalEditor(0)

    def test_file_handling_closed_ok(self):
        """Test file handling when closing with an exit status == 0."""
        self.editor.edit("")
        filename = self.editor._filename
        assert os.path.exists(filename)
        self.editor.on_proc_closed(0, QProcess.NormalExit)
        assert not os.path.exists(filename)

    def test_file_handling_closed_error(self, caplog):
        """Test file handling when closing with an exit status != 0."""
        self.editor.edit("")
        filename = self.editor._filename
        assert os.path.exists(filename)
        with caplog.atLevel(logging.ERROR):
            self.editor.on_proc_closed(1, QProcess.NormalExit)
            assert len(caplog.records()) == 2
        assert not os.path.exists(filename)

    def test_file_handling_closed_crash(self, caplog):
        """Test file handling when closing with a crash."""
        self.editor.edit("")
        filename = self.editor._filename
        assert os.path.exists(filename)
        with caplog.atLevel(logging.ERROR):
            self.editor.on_proc_error(QProcess.Crashed)
            assert len(caplog.records()) == 2
        self.editor.on_proc_closed(0, QProcess.CrashExit)
        assert not os.path.exists(filename)


class TestModifyTests:

    """Tests to test if the text gets saved/loaded correctly.

    Attributes:
        editor: The ExternalEditor instance to test.
    """

    @pytest.fixture(autouse=True)
    def setup(self, mocker, stubs):
        mocker.patch('qutebrowser.misc.editor.QProcess',
                     new_callable=stubs.FakeQProcess)
        mocker.patch('qutebrowser.misc.editor.config', new=stubs.ConfigStub(
            {'general': {'editor': [''], 'editor-encoding': 'utf-8'}}))
        self.editor = editor.ExternalEditor(0)
        self.editor.editing_finished = mock.Mock()

    def _write(self, text):
        """Write a text to the file opened in the fake editor.

        Args:
            text: The text to write to the file.
        """
        filename = self.editor._filename
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(text)

    def _read(self):
        """Read a text from the file opened in the fake editor.

        Return:
            The text which was read.
        """
        filename = self.editor._filename
        with open(filename, 'r', encoding='utf-8') as f:
            data = f.read()
        return data

    def test_empty_input(self):
        """Test if an empty input gets modified correctly."""
        self.editor.edit("")
        assert self._read() == ""
        self._write("Hello")
        self.editor.on_proc_closed(0, QProcess.NormalExit)
        self.editor.editing_finished.emit.assert_called_with("Hello")

    def test_simple_input(self):
        """Test if an empty input gets modified correctly."""
        self.editor.edit("Hello")
        assert self._read() == "Hello"
        self._write("World")
        self.editor.on_proc_closed(0, QProcess.NormalExit)
        self.editor.editing_finished.emit.assert_called_with("World")

    def test_umlaut(self):
        """Test if umlauts works correctly."""
        self.editor.edit("Hällö Wörld")
        assert self._read() == "Hällö Wörld"
        self._write("Überprüfung")
        self.editor.on_proc_closed(0, QProcess.NormalExit)
        self.editor.editing_finished.emit.assert_called_with("Überprüfung")

    def test_unicode(self):
        """Test if other UTF8 chars work correctly."""
        self.editor.edit("\u2603")  # Unicode snowman
        assert self._read() == "\u2603"
        self._write("\u2601")  # Cloud
        self.editor.on_proc_closed(0, QProcess.NormalExit)
        self.editor.editing_finished.emit.assert_called_with("\u2601")


class TestErrorMessage:

    """Test if statusbar error messages get emitted correctly.

    Attributes:
        editor: The ExternalEditor instance to test.
    """

    @pytest.yield_fixture(autouse=True)
    def setup(self, mocker, stubs):
        mocker.patch('qutebrowser.misc.editor.QProcess',
                     new_callable=stubs.FakeQProcess)
        mocker.patch('qutebrowser.misc.editor.message',
                     new=stubs.MessageModule())
        mocker.patch('qutebrowser.misc.editor.config', new=stubs.ConfigStub(
            {'general': {'editor': [''], 'editor-encoding': 'utf-8'}}))
        self.editor = editor.ExternalEditor(0)
        yield
        self.editor._cleanup()  # pylint: disable=protected-access

    def test_proc_error(self, caplog):
        """Test on_proc_error."""
        self.editor.edit("")
        with caplog.atLevel(logging.ERROR, 'message'):
            self.editor.on_proc_error(QProcess.Crashed)
            assert len(caplog.records()) == 2

    def test_proc_return(self, caplog):
        """Test on_proc_finished with a bad exit status."""
        self.editor.edit("")
        with caplog.atLevel(logging.ERROR, 'message'):
            self.editor.on_proc_closed(1, QProcess.NormalExit)
            assert len(caplog.records()) == 3
