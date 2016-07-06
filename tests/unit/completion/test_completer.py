# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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

"""Tests for the Completer Object."""

import unittest.mock

import pytest
from PyQt5.QtGui import QStandardItemModel

from qutebrowser.completion import completer
from qutebrowser.utils import usertypes


class FakeCompletionModel(QStandardItemModel):

    """Stub for a completion model."""

    DUMB_SORT = None

    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind = kind


@pytest.fixture
def cmd(stubs, qtbot):
    """Create the statusbar command prompt the completer uses."""
    cmd = stubs.FakeStatusbarCommand()
    qtbot.addWidget(cmd)
    return cmd


@pytest.fixture
def completer_obj(qtbot, cmd, config_stub):
    """Create the completer used for testing."""
    config_stub.data = {'completion': {'auto-open': False}}
    return completer.Completer(cmd, 0)


@pytest.fixture(autouse=True)
def instances(monkeypatch):
    """Mock the instances module so get returns a fake completion model."""
    # populate a model for each completion type, with a nested structure for
    # option and value completion
    instances = {kind: FakeCompletionModel(kind)
                 for kind in usertypes.Completion}
    instances[usertypes.Completion.option] = {
        'general': FakeCompletionModel(usertypes.Completion.option),
    }
    instances[usertypes.Completion.value] = {
        'general': {
            'ignore-case': FakeCompletionModel(usertypes.Completion.value),
        }
    }
    monkeypatch.setattr('qutebrowser.completion.completer.instances',
                        instances)


@pytest.fixture(autouse=True)
def cmdutils_patch(monkeypatch, stubs):
    """Patch the cmdutils module to provide fake commands."""
    cmds = {
        'set': [usertypes.Completion.section, usertypes.Completion.option,
                usertypes.Completion.value],
        'help': [usertypes.Completion.helptopic],
        'quickmark-load': [usertypes.Completion.quickmark_by_name],
        'bookmark-load': [usertypes.Completion.bookmark_by_url],
        'open': [usertypes.Completion.url],
        'buffer': [usertypes.Completion.tab],
        'session-load': [usertypes.Completion.sessions],
        'bind': [usertypes.Completion.empty, usertypes.Completion.command],
        'tab-detach': None,
    }
    cmd_utils = stubs.FakeCmdUtils({
        name: stubs.FakeCommand(completion=compl)
        for name, compl in cmds.items()
    })
    monkeypatch.setattr('qutebrowser.completion.completer.cmdutils',
                        cmd_utils)


def _set_cmd_prompt(cmd, txt):
    """Set the command prompt's text and cursor position.

    Args:
        cmd: The command prompt object.
        txt: The prompt text, using | as a placeholder for the cursor position.
    """
    cmd.setText(txt.replace('|', ''))
    cmd.setCursorPosition(txt.index('|'))


def _validate_cmd_prompt(cmd, txt):
    """Interpret fake command prompt text using | as the cursor placeholder.

    Args:
        cmd: The command prompt object.
        txt: The prompt text, using | as a placeholder for the cursor position.
    """
    assert cmd.cursorPosition() == txt.index('|')
    assert cmd.text() == txt.replace('|', '')


@pytest.mark.parametrize('txt, expected', [
    (':nope|', usertypes.Completion.command),
    (':nope |', None),
    (':set |', usertypes.Completion.section),
    (':set gen|', usertypes.Completion.section),
    (':set general |', usertypes.Completion.option),
    (':set what |', None),
    (':set general ignore-case |', usertypes.Completion.value),
    (':set general huh |', None),
    (':help |', usertypes.Completion.helptopic),
    (':quickmark-load |', usertypes.Completion.quickmark_by_name),
    (':bookmark-load |', usertypes.Completion.bookmark_by_url),
    (':open |', usertypes.Completion.url),
    (':buffer |', usertypes.Completion.tab),
    (':session-load |', usertypes.Completion.sessions),
    (':bind |', usertypes.Completion.empty),
    (':bind <c-x> |', usertypes.Completion.command),
    (':bind <c-x> foo|', usertypes.Completion.command),
    (':bind <c-x>| foo', usertypes.Completion.empty),
    (':set| general ', usertypes.Completion.command),
    (':|set general ', usertypes.Completion.command),
    (':set gene|ral ignore-case', usertypes.Completion.section),
    (':|', usertypes.Completion.command),
    (':   |', usertypes.Completion.command),
    (':bookmark-load      |', usertypes.Completion.bookmark_by_url),
    ('/|', None),
    (':open -t|', None),
    (':open --tab|', None),
    (':open -t |', usertypes.Completion.url),
    (':open --tab |', usertypes.Completion.url),
    (':open | -t', usertypes.Completion.url),
    (':--foo --bar |', None),
    (':tab-detach |', None),
    (':bind --mode=caret <c-x> |', usertypes.Completion.command),
    pytest.mark.xfail(reason='issue #74')((':bind --mode caret <c-x> |',
                                           usertypes.Completion.command)),
    (':set -t -p |', usertypes.Completion.section),
    (':open -- |', None),
])
def test_update_completion(txt, expected, cmd, completer_obj,
                           completion_widget_stub):
    """Test setting the completion widget's model based on command text."""
    # this test uses | as a placeholder for the current cursor position
    _set_cmd_prompt(cmd, txt)
    completer_obj.update_completion()
    if expected is None:
        assert not completion_widget_stub.set_model.called
    else:
        assert completion_widget_stub.set_model.call_count == 1
        arg = completion_widget_stub.set_model.call_args[0][0]
        # the outer model is just for sorting; srcmodel is the completion model
        assert arg.srcmodel.kind == expected


def test_completion_item_prev(completer_obj, cmd, completion_widget_stub,
                              config_stub, qtbot):
    """Test that completion_item_prev emits next_prev_item."""
    cmd.setText(':')
    with qtbot.waitSignal(completer_obj.next_prev_item) as blocker:
        completer_obj.completion_item_prev()
    assert blocker.args == [True]


def test_completion_item_next(completer_obj, cmd, completion_widget_stub,
                              config_stub, qtbot):
    """Test that completion_item_next emits next_prev_item."""
    cmd.setText(':')
    with qtbot.waitSignal(completer_obj.next_prev_item) as blocker:
        completer_obj.completion_item_next()
    assert blocker.args == [False]


@pytest.mark.parametrize('before, newtxt, quick_complete, count, after', [
    (':foo |', 'bar', False, 1, ':foo bar|'),
    (':foo |', 'bar', True, 2, ':foo bar|'),
    (':foo |', 'bar', True, 1, ':foo bar |'),
    (':foo | bar', 'baz', False, 1, ':foo baz| bar'),
    (':foo |', 'bar baz', True, 1, ":foo 'bar baz' |"),
    (':foo |', '', True, 1, ":foo '' |"),
    (':foo |', None, True, 1, ":foo |"),
])
def test_selection_changed(before, newtxt, count, quick_complete, after,
                           completer_obj, cmd, completion_widget_stub,
                           config_stub):
    """Test that change_completed_part modifies the cmd text properly.

    The | represents the current cursor position in the cmd prompt.
    If quick-complete is True and there is only 1 completion (count == 1),
    then we expect a space to be appended after the current word.
    """
    config_stub.data['completion']['quick-complete'] = quick_complete
    model = unittest.mock.Mock()
    model.data = unittest.mock.Mock(return_value=newtxt)
    model.count = unittest.mock.Mock(return_value=count)
    indexes = [unittest.mock.Mock()]
    selection = unittest.mock.Mock()
    selection.indexes = unittest.mock.Mock(return_value=indexes)
    completion_widget_stub.model = unittest.mock.Mock(return_value=model)
    _set_cmd_prompt(cmd, before)
    completer_obj.update_cursor_part()
    completer_obj.selection_changed(selection, None)
    model.data.assert_called_with(indexes[0])
    _validate_cmd_prompt(cmd, after)
