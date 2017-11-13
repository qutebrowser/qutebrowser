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
    yield ed
    with caplog.at_level(logging.ERROR):
        ed._remove_file = True
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
            "bin", ["foo", editor._filename, "bar"])

    def test_placeholder_inline(self, config_stub, editor):
        """Test starting editor with placeholder arg inside of another arg."""
        config_stub.val.editor.command = ['bin', 'foo{}', 'bar']
        editor.edit("")
        editor._proc._proc.start.assert_called_with(
            "bin", ["foo" + editor._filename, "bar"])


class TestFileHandling:

    """Test creation/deletion of tempfile."""

    def test_ok(self, editor):
        """Test file handling when closing with an exit status == 0."""
        editor.edit("")
        filename = editor._filename
        assert os.path.exists(filename)
        assert os.path.basename(filename).startswith('qutebrowser-editor-')
        editor._proc.finished.emit(0, QProcess.NormalExit)
        assert not os.path.exists(filename)

    def test_existing_file(self, editor, tmpdir):
        """Test editing an existing file."""
        path = tmpdir / 'foo.txt'
        path.ensure()

        editor.edit_file(str(path))
        editor._proc.finished.emit(0, QProcess.NormalExit)

        assert path.exists()

    def test_error(self, editor):
        """Test file handling when closing with an exit status != 0."""
        editor.edit("")
        filename = editor._filename
        assert os.path.exists(filename)

        editor._proc._proc.exitStatus = lambda: QProcess.CrashExit
        editor._proc.finished.emit(1, QProcess.NormalExit)

        assert os.path.exists(filename)

        os.remove(filename)

    def test_crash(self, editor):
        """Test file handling when closing with a crash."""
        editor.edit("")
        filename = editor._filename
        assert os.path.exists(filename)

        editor._proc._proc.exitStatus = lambda: QProcess.CrashExit
        editor._proc.error.emit(QProcess.Crashed)

        editor._proc.finished.emit(0, QProcess.CrashExit)
        assert os.path.exists(filename)

        os.remove(filename)

    def test_unreadable(self, message_mock, editor, caplog):
        """Test file handling when closing with an unreadable file."""
        editor.edit("")
        filename = editor._filename
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
def test_modify(qtbot, editor, initial_text, edited_text):
    """Test if inputs get modified correctly."""
    editor.edit(initial_text)

    with open(editor._filename, 'r', encoding='utf-8') as f:
        assert f.read() == initial_text

    with open(editor._filename, 'w', encoding='utf-8') as f:
        f.write(edited_text)

    with qtbot.wait_signal(editor.editing_finished) as blocker:
        editor._proc.finished.emit(0, QProcess.NormalExit)

    assert blocker.args == [edited_text]


@pytest.mark.parametrize('text, caret_position, result', [
    ('', 0, (1, 1)),
    ('a', 0, (1, 1)),
    ('a\nb', 1, (1, 2)),
    ('a\nb', 2, (2, 1)),
    ('a\nb', 3, (2, 2)),
    ('a\nbb\nccc', 4, (2, 3)),
    ('a\nbb\nccc', 5, (3, 1)),
    ('a\nbb\nccc', 8, (3, 4)),
    ('', None, (1, 1)),
])
def test_calculation(editor, text, caret_position, result):
    """Test calculation for line and column given text and caret_position."""
    assert editor._calc_line_and_column(text, caret_position) == result
