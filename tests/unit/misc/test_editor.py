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

import os
import os.path
import logging
from unittest import mock

from PyQt5.QtCore import QProcess
import pytest

from qutebrowser.misc import editor as editormod


@pytest.fixture(autouse=True)
def patch_things(config_stub, message_mock, monkeypatch, stubs):
    message_mock.patch('qutebrowser.misc.editor.message')
    monkeypatch.setattr('qutebrowser.misc.editor.guiprocess.QProcess',
                        stubs.fake_qprocess())
    config_stub.data = {
        'general': {'editor': [''], 'editor-encoding': 'utf-8'},
        'input': {},
    }
    monkeypatch.setattr('qutebrowser.misc.editor.config', config_stub)


@pytest.yield_fixture
def editor():
    ed = editormod.ExternalEditor(0)
    ed.editing_finished = mock.Mock()
    yield ed
    ed._cleanup()


class TestArg:

    """Test argument handling.

    Attributes:
        editor: The ExternalEditor instance to test.
    """

    @pytest.mark.parametrize('args', [[], ['foo', 'bar'], ['foo{}bar']])
    def test_start_no_placeholder(self, config_stub, editor, args):
        """Test starting editor without arguments."""
        config_stub.data['general']['editor'] = ['bin'] + args
        editor.edit("")
        editor._proc._proc.start.assert_called_with("bin", args)

    def test_placeholder(self, config_stub, editor):
        """Test starting editor with placeholder argument."""
        config_stub.data['general']['editor'] = ['bin', 'foo', '{}', 'bar']
        editor.edit("")
        editor._proc._proc.start.assert_called_with(
            "bin", ["foo", editor._filename, "bar"])


class TestFileHandling:

    """Test creation/deletion of tempfile."""

    def test_ok(self, editor):
        """Test file handling when closing with an exit status == 0."""
        editor.edit("")
        filename = editor._filename
        assert os.path.exists(filename)
        editor._proc.finished.emit(0, QProcess.NormalExit)
        assert not os.path.exists(filename)

    def test_error(self, caplog, editor):
        """Test file handling when closing with an exit status != 0."""
        editor.edit("")
        filename = editor._filename
        assert os.path.exists(filename)
        with caplog.atLevel(logging.ERROR):
            editor._proc.finished.emit(1, QProcess.NormalExit)
            assert len(caplog.records()) == 2
        assert not os.path.exists(filename)

    def test_crash(self, caplog, editor):
        """Test file handling when closing with a crash."""
        editor.edit("")
        filename = editor._filename
        assert os.path.exists(filename)
        with caplog.atLevel(logging.ERROR):
            editor._proc.error.emit(QProcess.Crashed)
            assert len(caplog.records()) == 2
        editor._proc.finished.emit(0, QProcess.CrashExit)
        assert not os.path.exists(filename)


@pytest.mark.parametrize('initial_text, edited_text', [
    ('', 'Hello'),
    ('Hello', 'World'),
    ('Hällö Wörld', 'Überprüfung'),
    ('\u2603', '\u2601')  # Unicode snowman -> cloud
])
def test_modify(editor, initial_text, edited_text):
    """Test if inputs get modified correctly."""
    editor.edit(initial_text)

    with open(editor._filename, 'r', encoding='utf-8') as f:
        assert f.read() == initial_text

    with open(editor._filename, 'w', encoding='utf-8') as f:
        f.write(edited_text)

    editor._proc.finished.emit(0, QProcess.NormalExit)
    editor.editing_finished.emit.assert_called_with(edited_text)


def test_proc_error(caplog, editor):
    """Test on_proc_error."""
    editor.edit("")
    with caplog.atLevel(logging.ERROR):
        editor.on_proc_error(QProcess.Crashed)
        assert len(caplog.records()) == 2


def test_proc_return(caplog, editor):
    """Test on_proc_finished with a bad exit status."""
    editor.edit("")
    with caplog.atLevel(logging.ERROR):
        editor.on_proc_closed(1, QProcess.NormalExit)
        assert len(caplog.records()) == 2
