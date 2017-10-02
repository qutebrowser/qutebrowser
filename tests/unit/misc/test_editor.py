# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import os
import os.path
import logging
from unittest import mock

from PyQt5.QtCore import QProcess
import pytest

from qutebrowser.misc import editor as editormod
from qutebrowser.utils import usertypes


@pytest.fixture(autouse=True)
def patch_things(config_stub, monkeypatch, stubs):
    monkeypatch.setattr(editormod.guiprocess, 'QProcess',
                        stubs.fake_qprocess())


@pytest.fixture
def editor(caplog):
    ed = editormod.ExternalEditor()
    ed.editing_finished = mock.Mock()
    yield ed
    with caplog.at_level(logging.ERROR):
        ed._cleanup()


class TestArg:

    """Test argument handling.

    Attributes:
        editor: The ExternalEditor instance to test.
    """

    def test_placeholder(self, config_stub, editor):
        """Test starting editor with placeholder argument."""
        config_stub.val.editor.command = ['bin', 'foo', '{}', 'bar']
        editor.edit("")
        editor._proc._proc.start.assert_called_with(
            "bin", ["foo", editor._file.name, "bar"])

    def test_placeholder_inline(self, config_stub, editor):
        """Test starting editor with placeholder arg inside of another arg."""
        config_stub.val.editor.command = ['bin', 'foo{}', 'bar']
        editor.edit("")
        editor._proc._proc.start.assert_called_with(
            "bin", ["foo" + editor._file.name, "bar"])


class TestFileHandling:

    """Test creation/deletion of tempfile."""

    def test_ok(self, editor):
        """Test file handling when closing with an exit status == 0."""
        editor.edit("")
        filename = editor._file.name
        assert os.path.exists(filename)
        assert os.path.basename(filename).startswith('qutebrowser-editor-')
        editor._proc.finished.emit(0, QProcess.NormalExit)
        assert not os.path.exists(filename)

    def test_error(self, editor):
        """Test file handling when closing with an exit status != 0."""
        editor.edit("")
        filename = editor._file.name
        assert os.path.exists(filename)

        editor._proc._proc.exitStatus = mock.Mock(
            return_value=QProcess.CrashExit)
        editor._proc.finished.emit(1, QProcess.NormalExit)

        assert os.path.exists(filename)

        os.remove(filename)

    def test_crash(self, editor):
        """Test file handling when closing with a crash."""
        editor.edit("")
        filename = editor._file.name
        assert os.path.exists(filename)

        editor._proc._proc.exitStatus = mock.Mock(
            return_value=QProcess.CrashExit)
        editor._proc.error.emit(QProcess.Crashed)

        editor._proc.finished.emit(0, QProcess.CrashExit)
        assert os.path.exists(filename)

        os.remove(filename)

    def test_unreadable(self, message_mock, editor, caplog):
        """Test file handling when closing with an unreadable file."""
        editor.edit("")
        filename = editor._file.name
        assert os.path.exists(filename)
        os.chmod(filename, 0o077)
        if os.access(filename, os.R_OK):
            # Docker container or similar
            pytest.skip("File was still readable")

        with caplog.at_level(logging.ERROR):
            editor._proc.finished.emit(0, QProcess.NormalExit)
        assert not os.path.exists(filename)
        msg = message_mock.getmsg(usertypes.MessageLevel.error)
        assert msg.text.startswith("Failed to read back edited file: ")

    def test_unwritable(self, monkeypatch, message_mock, editor, tmpdir,
                        caplog):
        """Test file handling when the initial file is not writable."""
        tmpdir.chmod(0)
        if os.access(str(tmpdir), os.W_OK):
            # Docker container or similar
            pytest.skip("File was still writable")

        monkeypatch.setattr(editormod.tempfile, 'tempdir', str(tmpdir))

        with caplog.at_level(logging.ERROR):
            editor.edit("")

        msg = message_mock.getmsg(usertypes.MessageLevel.error)
        assert msg.text.startswith("Failed to create initial file: ")
        assert editor._proc is None

    def test_double_edit(self, editor):
        editor.edit("")
        with pytest.raises(ValueError):
            editor.edit("")


@pytest.mark.parametrize('initial_text, edited_text', [
    ('', 'Hello'),
    ('Hello', 'World'),
    ('Hällö Wörld', 'Überprüfung'),
    ('\u2603', '\u2601')  # Unicode snowman -> cloud
])
def test_modify(editor, initial_text, edited_text):
    """Test if inputs get modified correctly."""
    editor.edit(initial_text)

    with open(editor._file.name, 'r', encoding='utf-8') as f:
        assert f.read() == initial_text

    with open(editor._file.name, 'w', encoding='utf-8') as f:
        f.write(edited_text)

    editor._proc.finished.emit(0, QProcess.NormalExit)
    editor.editing_finished.emit.assert_called_with(edited_text)
