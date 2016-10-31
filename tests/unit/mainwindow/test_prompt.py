# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import pytest

from qutebrowser.mainwindow import prompt as promptmod
from qutebrowser.utils import usertypes


@pytest.fixture(autouse=True)
def setup(qapp, key_config_stub):
    key_config_stub.set_bindings_for('prompt', {})


@pytest.mark.parametrize('steps, where, subfolder', [
    (1, 'next', '..'),
    (1, 'prev', 'c'),
    (2, 'next', 'a'),
    (2, 'prev', 'b'),
])
def test_file_completion(tmpdir, qtbot, steps, where, subfolder):
    for directory in 'abc':
        (tmpdir / directory).ensure(dir=True)
    question = usertypes.Question()
    question.title = "test"
    question.default = str(tmpdir) + '/'

    prompt = promptmod.DownloadFilenamePrompt(question)
    qtbot.add_widget(prompt)
    with qtbot.wait_signal(prompt._file_model.directoryLoaded):
        pass
    assert prompt._lineedit.text() == str(tmpdir) + '/'

    for _ in range(steps):
        prompt.item_focus(where)

    assert prompt._lineedit.text() == str(tmpdir / subfolder)
