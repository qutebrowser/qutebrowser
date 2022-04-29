# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import os

import pytest
from PyQt5.QtCore import Qt

from qutebrowser.mainwindow import prompt as promptmod
from qutebrowser.utils import usertypes


class TestFileCompletion:

    @pytest.fixture
    def get_prompt(self, qtbot, config_stub, key_config_stub):
        """Get a function to display a prompt with a path."""
        config_stub.val.bindings.default = {}

        def _get_prompt_func(path):
            question = usertypes.Question()
            question.title = "test"
            question.default = path

            prompt = promptmod.DownloadFilenamePrompt(question)
            qtbot.add_widget(prompt)
            with qtbot.wait_signal(prompt._file_model.directoryLoaded):
                pass
            assert prompt._lineedit.text() == path

            return prompt
        return _get_prompt_func

    @pytest.mark.parametrize('steps, where, subfolder', [
        (1, 'next', 'a'),
        (1, 'prev', 'c'),
        (2, 'next', 'b'),
        (2, 'prev', 'b'),
    ])
    def test_simple_completion(self, tmp_path, get_prompt, steps, where,
                               subfolder):
        """Simply trying to tab through items."""
        testdir = tmp_path / 'test'
        for directory in 'abc':
            (testdir / directory).mkdir(parents=True)

        prompt = get_prompt(str(testdir) + os.sep)

        for _ in range(steps):
            prompt.item_focus(where)

        assert prompt._lineedit.text() == str((testdir / subfolder).resolve())

    def test_backspacing_path(self, qtbot, tmp_path, get_prompt):
        """When we start deleting a path we want to see the subdir."""
        testdir = tmp_path / 'test'

        for directory in ['bar', 'foo']:
            (testdir / directory).mkdir(parents=True)

        prompt = get_prompt(str(testdir / 'foo') + os.sep)

        # Deleting /f[oo/]
        with qtbot.wait_signal(prompt._file_model.directoryLoaded):
            for _ in range(3):
                qtbot.keyPress(prompt._lineedit, Qt.Key_Backspace)

        # For some reason, this isn't always called when using qtbot.keyPress.
        prompt._set_fileview_root(prompt._lineedit.text())

        # 'foo' should get completed from 'f'
        prompt.item_focus('next')
        assert prompt._lineedit.text() == str(testdir / 'foo')

        # Deleting /[foo]
        for _ in range(3):
            qtbot.keyPress(prompt._lineedit, Qt.Key_Backspace)

        # We should now show / again, so tabbing twice gives us bar -> foo
        prompt.item_focus('next')
        prompt.item_focus('next')
        assert prompt._lineedit.text() == str(testdir / 'foo')

    @pytest.mark.parametrize("keys, expected", [
        ([], ['bar', 'bat', 'foo']),
        ([Qt.Key_F], ['foo']),
        ([Qt.Key_A], ['bar', 'bat']),
    ])
    def test_filtering_path(self, qtbot, tmp_path, get_prompt, keys, expected):
        testdir = tmp_path / 'test'

        for directory in ['bar', 'foo', 'bat']:
            (testdir / directory).mkdir(parents=True)

        prompt = get_prompt(str(testdir) + os.sep)
        for key in keys:
            qtbot.keyPress(prompt._lineedit, key)
        prompt._set_fileview_root(prompt._lineedit.text())

        num_rows = prompt._file_model.rowCount(prompt._file_view.rootIndex())
        visible = []
        for row in range(num_rows):
            parent = prompt._file_model.index(
                os.path.dirname(prompt._lineedit.text()))
            index = prompt._file_model.index(row, 0, parent)
            if not prompt._file_view.isRowHidden(index.row(), index.parent()):
                visible.append(index.data())
        assert visible == expected

    @pytest.mark.linux
    def test_root_path(self, get_prompt):
        """With / as path, show root contents."""
        prompt = get_prompt('/')
        assert prompt._file_model.rootPath() == '/'
