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

"""Test Prompt widget."""

import sip

import pytest

from qutebrowser.mainwindow.statusbar.prompt import Prompt
from qutebrowser.utils import objreg


@pytest.yield_fixture
def prompt(qtbot, win_registry):
    prompt = Prompt(0)
    qtbot.addWidget(prompt)

    yield prompt

    # If we don't clean up here, this test will remove 'prompter' from the
    # objreg at some point in the future, which will cause some other test to
    # fail.
    sip.delete(prompt)


def test_prompt(prompt):
    prompt.show()
    objreg.get('prompt', scope='window', window=0)
    objreg.get('prompter', scope='window', window=0)


@pytest.mark.xfail(reason="This test is broken and I don't get why")
def test_resizing(fake_statusbar, prompt):
    fake_statusbar.hbox.addWidget(prompt)

    prompt.txt.setText("Blah?")
    old_width = prompt.lineedit.width()

    prompt.lineedit.setText("Hello World" * 100)
    assert prompt.lineedit.width() > old_width
