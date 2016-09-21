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
from PyQt5.QtCore import QObject
from PyQt5.QtGui import QStandardItemModel

from qutebrowser.completion import completer
from qutebrowser.utils import usertypes
from qutebrowser.commands import command, cmdutils


class FakeCompletionModel(QStandardItemModel):

    """Stub for a completion model."""

    DUMB_SORT = None

    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind = kind


class CompletionWidgetStub(QObject):

    """Stub for the CompletionView."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hide = unittest.mock.Mock()
        self.show = unittest.mock.Mock()
        self.set_pattern = unittest.mock.Mock()
        self.model = unittest.mock.Mock()
        self.set_model = unittest.mock.Mock()
        self.enabled = unittest.mock.Mock()


@pytest.fixture
def completion_widget_stub():
    return CompletionWidgetStub()


@pytest.fixture
def completer_obj(qtbot, status_command_stub, config_stub, monkeypatch, stubs,
                  completion_widget_stub):
    """Create the completer used for testing."""
    monkeypatch.setattr('qutebrowser.completion.completer.QTimer',
        stubs.InstaTimer)
    config_stub.data = {'completion': {'show': 'auto'}}
    return completer.Completer(status_command_stub, 0, completion_widget_stub)


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
            'editor': FakeCompletionModel(usertypes.Completion.value),
        }
    }
    monkeypatch.setattr('qutebrowser.completion.completer.instances',
                        instances)


@pytest.fixture(autouse=True)
def cmdutils_patch(monkeypatch, stubs):
    """Patch the cmdutils module to provide fake commands."""
    @cmdutils.argument('section_', completion=usertypes.Completion.section)
    @cmdutils.argument('option', completion=usertypes.Completion.option)
    @cmdutils.argument('value', completion=usertypes.Completion.value)
    def set_command(section_=None, option=None, value=None):
        """docstring."""
        pass

    @cmdutils.argument('topic', completion=usertypes.Completion.helptopic)
    def show_help(tab=False, bg=False, window=False, topic=None):
        """docstring."""
        pass

    @cmdutils.argument('url', completion=usertypes.Completion.url)
    @cmdutils.argument('count', count=True)
    def openurl(url=None, implicit=False, bg=False, tab=False, window=False,
                count=None):
        """docstring."""
        pass

    @cmdutils.argument('win_id', win_id=True)
    @cmdutils.argument('command', completion=usertypes.Completion.command)
    def bind(key, win_id, command=None, *, mode='normal', force=False):
        """docstring."""
        # pylint: disable=unused-variable
        pass

    def tab_detach():
        """docstring."""
        pass

    cmd_utils = stubs.FakeCmdUtils({
        'set': command.Command(name='set', handler=set_command),
        'help': command.Command(name='help', handler=show_help),
        'open': command.Command(name='open', handler=openurl, maxsplit=0),
        'bind': command.Command(name='bind', handler=bind),
        'tab-detach': command.Command(name='tab-detach', handler=tab_detach),
    })
    monkeypatch.setattr('qutebrowser.completion.completer.cmdutils', cmd_utils)


def _set_cmd_prompt(cmd, txt):
    """Set the command prompt's text and cursor position.

    Args:
        cmd: The command prompt object.
        txt: The prompt text, using | as a placeholder for the cursor position.
    """
    cmd.setText(txt.replace('|', ''))
    cmd.setCursorPosition(txt.index('|'))


@pytest.mark.parametrize('txt, kind, pattern', [
    (':nope|', usertypes.Completion.command, 'nope'),
    (':nope |', None, ''),
    (':set |', usertypes.Completion.section, ''),
    (':set gen|', usertypes.Completion.section, 'gen'),
    (':set general |', usertypes.Completion.option, ''),
    (':set what |', None, ''),
    (':set general editor |', usertypes.Completion.value, ''),
    (':set general editor gv|', usertypes.Completion.value, 'gv'),
    (':set general editor "gvim -f"|', usertypes.Completion.value, 'gvim -f'),
    (':set general editor "gvim |', usertypes.Completion.value, 'gvim'),
    (':set general huh |', None, ''),
    (':help |', usertypes.Completion.helptopic, ''),
    (':help     |', usertypes.Completion.helptopic, ''),
    (':open |', usertypes.Completion.url, ''),
    (':bind |', None, ''),
    (':bind <c-x> |', usertypes.Completion.command, ''),
    (':bind <c-x> foo|', usertypes.Completion.command, 'foo'),
    (':bind <c-x>| foo', None, '<c-x>'),
    (':set| general ', usertypes.Completion.command, 'set'),
    (':|set general ', usertypes.Completion.command, 'set'),
    (':set gene|ral ignore-case', usertypes.Completion.section, 'general'),
    (':|', usertypes.Completion.command, ''),
    (':   |', usertypes.Completion.command, ''),
    ('/|', None, ''),
    (':open -t|', None, ''),
    (':open --tab|', None, ''),
    (':open -t |', usertypes.Completion.url, ''),
    (':open --tab |', usertypes.Completion.url, ''),
    (':open | -t', usertypes.Completion.url, ''),
    (':tab-detach |', None, ''),
    (':bind --mode=caret <c-x> |', usertypes.Completion.command, ''),
    pytest.mark.xfail(reason='issue #74')((':bind --mode caret <c-x> |',
                                           usertypes.Completion.command, '')),
    (':set -t -p |', usertypes.Completion.section, ''),
    (':open -- |', None, ''),
    (':gibberish nonesense |', None, ''),
    ('/:help|', None, ''),
])
def test_update_completion(txt, kind, pattern, status_command_stub,
                           completer_obj, completion_widget_stub):
    """Test setting the completion widget's model based on command text."""
    # this test uses | as a placeholder for the current cursor position
    _set_cmd_prompt(status_command_stub, txt)
    completer_obj.schedule_completion_update()
    assert completion_widget_stub.set_model.call_count == 1
    args = completion_widget_stub.set_model.call_args[0]
    # the outer model is just for sorting; srcmodel is the completion model
    if kind is None:
        assert args[0] is None
    else:
        assert args[0].srcmodel.kind == kind
        assert args[1] == pattern


@pytest.mark.parametrize('before, newtxt, after', [
    (':|', 'set', ':set|'),
    (':| ', 'set', ':set|'),
    (': |', 'set', ':set|'),
    (':|set', 'set', ':set|'),
    (':|set ', 'set', ':set|'),
    (':|se', 'set', ':set|'),
    (':|se ', 'set', ':set|'),
    (':s|e', 'set', ':set|'),
    (':se|', 'set', ':set|'),
    (':|se fonts', 'set', ':set| fonts'),
    (':set |', 'fonts', ':set fonts|'),
    (':set  |', 'fonts', ':set fonts|'),
    (':set --temp |', 'fonts', ':set --temp fonts|'),
    (':set |fo', 'fonts', ':set fonts|'),
    (':set f|o', 'fonts', ':set fonts|'),
    (':set fo|', 'fonts', ':set fonts|'),
    (':set fonts |', 'hints', ':set fonts hints|'),
    (':set fonts |nt', 'hints', ':set fonts hints|'),
    (':set fonts n|t', 'hints', ':set fonts hints|'),
    (':set fonts nt|', 'hints', ':set fonts hints|'),
    (':set | hints', 'fonts', ':set fonts| hints'),
    (':set  |  hints', 'fonts', ':set fonts| hints'),
    (':set |fo hints', 'fonts', ':set fonts| hints'),
    (':set f|o hints', 'fonts', ':set fonts| hints'),
    (':set fo| hints', 'fonts', ':set fonts| hints'),
    (':set fonts hints |', 'Comic Sans', ":set fonts hints 'Comic Sans'|"),
    (":set fonts hints 'Comic Sans'|", '12px Hack',
     ":set fonts hints '12px Hack'|"),
    (":set fonts hints 'Comic| Sans'", '12px Hack',
     ":set fonts hints '12px Hack'|"),
    # open has maxsplit=0, so treat the last two tokens as one and don't quote
    (':open foo bar|', 'baz', ':open baz|'),
    (':open foo| bar', 'baz', ':open baz|'),
])
def test_on_selection_changed(before, newtxt, after, completer_obj,
                              config_stub, status_command_stub,
                              completion_widget_stub):
    """Test that on_selection_changed modifies the cmd text properly.

    The | represents the current cursor position in the cmd prompt.
    If quick-complete is True and there is only 1 completion (count == 1),
    then we expect a space to be appended after the current word.
    """
    model = unittest.mock.Mock()
    completion_widget_stub.model.return_value = model

    def check(quick_complete, count, expected_txt, expected_pos):
        config_stub.data['completion']['quick-complete'] = quick_complete
        model.count = lambda: count
        _set_cmd_prompt(status_command_stub, before)
        completer_obj.on_selection_changed(newtxt)
        assert status_command_stub.text() == expected_txt
        assert status_command_stub.cursorPosition() == expected_pos

    after_pos = after.index('|')
    after_txt = after.replace('|', '')
    check(False, 1, after_txt, after_pos)
    check(True, 2, after_txt, after_pos)

    # quick-completing a single item should move the cursor ahead by 1 and add
    # a trailing space if at the end of the cmd string
    after_pos += 1
    if after_pos > len(after_txt):
        after_txt += ' '
    check(True, 1, after_txt, after_pos)


def test_quickcomplete_flicker(status_command_stub, completer_obj,
                               completion_widget_stub, config_stub):
    """Validate fix for #1519: bookmark-load background highlighting quirk.

    For commands like bookmark-load and open with maxsplit=0, a commandline
    that looks like ':open someurl |' is considered to be completing the first
    arg with pattern 'someurl ' (note trailing whitespace). As this matches the
    one completion available, it keeps the completionmenu open.

    This test validates that the completion model is not re-set after we
    quick-complete an entry after maxsplit.
    """
    model = unittest.mock.Mock()
    model.count = unittest.mock.Mock(return_value=1)
    completion_widget_stub.model.return_value = model
    config_stub.data['completion']['quick-complete'] = True

    _set_cmd_prompt(status_command_stub, ':open |')
    completer_obj.on_selection_changed('http://example.com')
    completer_obj.schedule_completion_update()
    assert not completion_widget_stub.set_model.called
