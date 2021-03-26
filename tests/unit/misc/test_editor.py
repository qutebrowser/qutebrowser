# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Tests for qutebrowser.misc.editor."""

import time
import pathlib
import os
import logging

import pytest
from PyQt5.QtCore import QProcess

from qutebrowser.misc import editor as editormod
from qutebrowser.utils import usertypes


@pytest.fixture(autouse=True)
def patch_fake_process(config_stub, monkeypatch, stubs):
    monkeypatch.setattr(editormod.guiprocess, 'QProcess', stubs.FakeProcess)


@pytest.fixture(params=[True, False])
def editor(caplog, qtbot, request):
    ed = editormod.ExternalEditor(watch=request.param)
    yield ed
    with caplog.at_level(logging.ERROR):
        ed._remove_file = True
        ed._cleanup(successful=True)


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
        filename = pathlib.Path(editor._filename)
        assert filename.exists()
        assert filename.name.startswith('qutebrowser-editor-')
        editor._proc._proc.finished.emit(0, QProcess.NormalExit)
        assert not filename.exists()

    @pytest.mark.parametrize('touch', [True, False])
    def test_with_filename(self, editor, tmp_path, touch):
        """Test editing a file with an explicit path."""
        path = tmp_path / 'foo.txt'
        if touch:
            path.touch()

        editor.edit_file(str(path))
        editor._proc._proc.finished.emit(0, QProcess.NormalExit)

        assert path.exists()

    def test_error(self, editor, caplog):
        """Test file handling when closing with an exit status != 0."""
        editor.edit("")
        filename = pathlib.Path(editor._filename)
        assert filename.exists()

        with caplog.at_level(logging.ERROR):
            editor._proc._proc.finished.emit(1, QProcess.NormalExit)

        assert filename.exists()

        filename.unlink()

    def test_crash(self, editor, caplog):
        """Test file handling when closing with a crash."""
        editor.edit("")
        filename = pathlib.Path(editor._filename)
        assert filename.exists()

        editor._proc.error.emit(QProcess.Crashed)
        with caplog.at_level(logging.ERROR):
            editor._proc._proc.finished.emit(0, QProcess.CrashExit)

        assert filename.exists()
        filename.unlink()

    def test_unreadable(self, message_mock, editor, caplog, qtbot):
        """Test file handling when closing with an unreadable file."""
        editor.edit("")
        filename = pathlib.Path(editor._filename)
        assert filename.exists()
        filename.chmod(0o277)
        if os.access(str(filename), os.R_OK):
            # Docker container or similar
            pytest.skip("File was still readable")

        with caplog.at_level(logging.ERROR):
            editor._proc._proc.finished.emit(0, QProcess.NormalExit)
        assert not filename.exists()
        msg = message_mock.getmsg(usertypes.MessageLevel.error)
        assert msg.text.startswith("Failed to read back edited file: ")

    def test_unwritable(self, monkeypatch, message_mock, editor,
                        unwritable_tmp_path, caplog):
        """Test file handling when the initial file is not writable."""
        monkeypatch.setattr(editormod.tempfile, 'tempdir',
                            str(unwritable_tmp_path))

        with caplog.at_level(logging.ERROR):
            editor.edit("")

        msg = message_mock.getmsg(usertypes.MessageLevel.error)
        assert msg.text.startswith("Failed to create initial file: ")
        assert editor._proc is None

    def test_double_edit(self, editor):
        editor.edit("")
        with pytest.raises(ValueError):
            editor.edit("")

    def test_backup(self, qtbot, message_mock):
        editor = editormod.ExternalEditor(watch=True)
        editor.edit('foo')
        with qtbot.wait_signal(editor.file_updated, timeout=5000):
            _update_file(editor._filename, 'bar')

        editor.backup()

        msg = message_mock.getmsg(usertypes.MessageLevel.info)
        prefix = 'Editor backup at '
        assert msg.text.startswith(prefix)
        fname = msg.text[len(prefix):]

        with qtbot.wait_signal(editor.editing_finished):
            editor._proc._proc.finished.emit(0, QProcess.NormalExit)

        with open(fname, 'r', encoding='utf-8') as f:
            assert f.read() == 'bar'

    def test_backup_no_content(self, qtbot, message_mock):
        editor = editormod.ExternalEditor(watch=True)
        editor.edit('foo')
        editor.backup()
        # content has not changed, so no backup should be created
        assert not message_mock.messages

    def test_backup_error(self, qtbot, message_mock, mocker, caplog):
        editor = editormod.ExternalEditor(watch=True)
        editor.edit('foo')
        with qtbot.wait_signal(editor.file_updated):
            _update_file(editor._filename, 'bar')

        mocker.patch('tempfile.NamedTemporaryFile', side_effect=OSError)
        with caplog.at_level(logging.ERROR):
            editor.backup()

        msg = message_mock.getmsg(usertypes.MessageLevel.error)
        assert msg.text.startswith('Failed to create editor backup:')


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

    with qtbot.wait_signal(editor.file_updated) as blocker:
        editor._proc._proc.finished.emit(0, QProcess.NormalExit)

    assert blocker.args == [edited_text]


def _update_file(filename, contents):
    """Update the given file and make sure its mtime changed.

    This might write the file multiple times, but different systems have
    different mtime's, so we can't be sure how long to wait otherwise.
    """
    file_path = pathlib.Path(filename)
    old_mtime = new_mtime = file_path.stat().st_mtime
    while old_mtime == new_mtime:
        time.sleep(0.1)
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(contents)
        new_mtime = file_path.stat().st_mtime


def test_modify_watch(qtbot):
    """Test that saving triggers file_updated when watch=True."""
    editor = editormod.ExternalEditor(watch=True)
    editor.edit('foo')

    with qtbot.wait_signal(editor.file_updated, timeout=3000) as blocker:
        _update_file(editor._filename, 'bar')
    assert blocker.args == ['bar']

    with qtbot.wait_signal(editor.file_updated) as blocker:
        _update_file(editor._filename, 'baz')
    assert blocker.args == ['baz']

    with qtbot.assert_not_emitted(editor.file_updated):
        editor._proc._proc.finished.emit(0, QProcess.NormalExit)


def test_failing_watch(qtbot, caplog, monkeypatch):
    """When watching failed, an error should be logged.

    Also, updating should still work when closing the process.
    """
    editor = editormod.ExternalEditor(watch=True)
    monkeypatch.setattr(editor._watcher, 'addPath', lambda _path: False)

    with caplog.at_level(logging.ERROR):
        editor.edit('foo')

    with qtbot.assert_not_emitted(editor.file_updated):
        _update_file(editor._filename, 'bar')

    with qtbot.wait_signal(editor.file_updated) as blocker:
        editor._proc._proc.finished.emit(0, QProcess.NormalExit)
    assert blocker.args == ['bar']

    message = 'Failed to watch path: {}'.format(editor._filename)
    assert caplog.messages[0] == message


def test_failing_unwatch(qtbot, caplog, monkeypatch):
    """When unwatching failed, an error should be logged."""
    editor = editormod.ExternalEditor(watch=True)
    monkeypatch.setattr(editor._watcher, 'addPath', lambda _path: True)
    monkeypatch.setattr(editor._watcher, 'files', lambda: [editor._filename])
    monkeypatch.setattr(editor._watcher, 'removePaths', lambda paths: paths)

    editor.edit('foo')

    with caplog.at_level(logging.ERROR):
        editor._proc._proc.finished.emit(0, QProcess.NormalExit)

    message = 'Failed to unwatch paths: [{!r}]'.format(editor._filename)
    assert caplog.messages[-1] == message


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
