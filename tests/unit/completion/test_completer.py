# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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
from qutebrowser.commands import command
from qutebrowser.api import cmdutils


class FakeCompletionModel(QStandardItemModel):

    """Stub for a completion model."""

    def __init__(self, kind, *pos_args, info, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.pos_args = list(pos_args)
        self.info = info


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
    monkeypatch.setattr(completer, 'QTimer', stubs.InstaTimer)
    config_stub.val.completion.show = 'auto'
    return completer.Completer(cmd=status_command_stub, win_id=0,
                               parent=completion_widget_stub)


@pytest.fixture(autouse=True)
def miscmodels_patch(mocker):
    """Patch the miscmodels module to provide fake completion functions.

    Technically some of these are not part of miscmodels, but rolling them into
    one module is easier and sufficient for mocking. The only one referenced
    directly by Completer is miscmodels.command.
    """
    m = mocker.patch('qutebrowser.completion.completer.miscmodels',
                     autospec=True)

    def func(name):
        return lambda *args, info: FakeCompletionModel(name, *args, info=info)

    m.command = func('command')
    m.helptopic = func('helptopic')
    m.quickmark = func('quickmark')
    m.bookmark = func('bookmark')
    m.session = func('session')
    m.buffer = func('buffer')
    m.bind = func('bind')
    m.url = func('url')
    m.section = func('section')
    m.option = func('option')
    m.value = func('value')
    return m


@pytest.fixture(autouse=True)
def cmdutils_patch(monkeypatch, stubs, miscmodels_patch):
    """Patch the cmdutils module to provide fake commands."""
    @cmdutils.argument('section_', completion=miscmodels_patch.section)
    @cmdutils.argument('option', completion=miscmodels_patch.option)
    @cmdutils.argument('value', completion=miscmodels_patch.value)
    def set_command(section_=None, option=None, value=None):
        """docstring."""

    @cmdutils.argument('topic', completion=miscmodels_patch.helptopic)
    def show_help(tab=False, bg=False, window=False, topic=None):
        """docstring."""

    @cmdutils.argument('url', completion=miscmodels_patch.url)
    @cmdutils.argument('count', value=cmdutils.Value.count)
    def openurl(url=None, related=False, bg=False, tab=False, window=False,
                count=None):
        """docstring."""

    @cmdutils.argument('win_id', value=cmdutils.Value.win_id)
    @cmdutils.argument('command', completion=miscmodels_patch.command)
    def bind(key, win_id, command=None, *, mode='normal'):
        """docstring."""

    def tab_give():
        """docstring."""

    @cmdutils.argument('option', completion=miscmodels_patch.option)
    @cmdutils.argument('values', completion=miscmodels_patch.value)
    def config_cycle(option, *values):
        """For testing varargs."""

    commands = {
        'set': command.Command(name='set', handler=set_command),
        'help': command.Command(name='help', handler=show_help),
        'open': command.Command(name='open', handler=openurl, maxsplit=0),
        'bind': command.Command(name='bind', handler=bind),
        'tab-give': command.Command(name='tab-give', handler=tab_give),
        'config-cycle': command.Command(name='config-cycle',
                                        handler=config_cycle),
    }
    monkeypatch.setattr(completer.objects, 'commands', commands)


def _set_cmd_prompt(cmd, txt):
    """Set the command prompt's text and cursor position.

    Args:
        cmd: The command prompt object.
        txt: The prompt text, using | as a placeholder for the cursor position.
    """
    cmd.setText(txt.replace('|', ''))
    cmd.setCursorPosition(txt.index('|'))


@pytest.mark.parametrize('txt, kind, pattern, pos_args', [
    (':nope|', 'command', 'nope', []),
    (':nope |', None, '', []),
    (':set |', 'section', '', []),
    (':set gen|', 'section', 'gen', []),
    (':set general |', 'option', '', ['general']),
    (':set what |', 'option', '', ['what']),
    (':set general editor |', 'value', '', ['general', 'editor']),
    (':set general editor gv|', 'value', 'gv', ['general', 'editor']),
    (':set general editor "gvim -f"|', 'value', 'gvim -f',
     ['general', 'editor']),
    (':set general editor "gvim |', 'value', 'gvim', ['general', 'editor']),
    (':set general huh |', 'value', '', ['general', 'huh']),
    (':help |', 'helptopic', '', []),
    (':help     |', 'helptopic', '', []),
    (':open |', 'url', '', []),
    (':bind |', None, '', []),
    (':bind <c-x> |', 'command', '', ['<c-x>']),
    (':bind <c-x> foo|', 'command', 'foo', ['<c-x>']),
    (':bind <c-x>| foo', None, '<c-x>', []),
    (':set| general ', 'command', 'set', []),
    (':|set general ', 'command', 'set', []),
    (':set gene|ral ignore-case', 'section', 'general', []),
    (':|', 'command', '', []),
    (':   |', 'command', '', []),
    ('/|', None, '', []),
    (':open -t|', None, '', []),
    (':open --tab|', None, '', []),
    (':open -t |', 'url', '', []),
    (':open --tab |', 'url', '', []),
    (':open | -t', 'url', '', []),
    (':tab-give |', None, '', []),
    (':bind --mode=caret <c-x> |', 'command', '', ['<c-x>']),
    pytest.param(':bind --mode caret <c-x> |', 'command', '', [],
                 marks=pytest.mark.xfail(reason='issue #74')),
    (':set -t -p |', 'section', '', []),
    (':open -- |', None, '', []),
    (':gibberish nonesense |', None, '', []),
    ('/:help|', None, '', []),
    ('::bind|', 'command', ':bind', []),
    (':-w open |', None, '', []),
    # varargs
    (':config-cycle option |', 'value', '', ['option']),
    (':config-cycle option one |', 'value', '', ['option', 'one']),
    (':config-cycle option one two |', 'value', '', ['option', 'one', 'two']),
])
def test_update_completion(txt, kind, pattern, pos_args, status_command_stub,
                           completer_obj, completion_widget_stub, config_stub,
                           key_config_stub):
    """Test setting the completion widget's model based on command text."""
    # this test uses | as a placeholder for the current cursor position
    _set_cmd_prompt(status_command_stub, txt)
    completer_obj.schedule_completion_update()
    if kind is None:
        assert not completion_widget_stub.set_pattern.called
    else:
        assert completion_widget_stub.set_model.call_count == 1
        model = completion_widget_stub.set_model.call_args[0][0]
        assert model.kind == kind
        assert model.pos_args == pos_args
        assert model.info.config == config_stub
        assert model.info.keyconf == key_config_stub
        completion_widget_stub.set_pattern.assert_called_once_with(pattern)


@pytest.mark.parametrize('txt1, txt2, regen', [
    (':config-cycle |', ':config-cycle a|', False),
    (':config-cycle abc|', ':config-cycle abc |', True),
    (':config-cycle abc |', ':config-cycle abc d|', False),
    (':config-cycle abc def|', ':config-cycle abc def |', True),
    # open has maxsplit=0, so all args just set the pattern, not the model
    (':open |', ':open a|', False),
    (':open abc|', ':open abc |', False),
    (':open abc |', ':open abc d|', False),
    (':open abc def|', ':open abc def |', False),
])
def test_regen_completion(txt1, txt2, regen, status_command_stub,
                          completer_obj, completion_widget_stub, config_stub,
                          key_config_stub):
    """Test that the completion function is only called as needed."""
    # set the initial state
    _set_cmd_prompt(status_command_stub, txt1)
    completer_obj.schedule_completion_update()
    completion_widget_stub.set_model.reset_mock()

    # "move" the cursor and check if the completion function was called
    _set_cmd_prompt(status_command_stub, txt2)
    completer_obj.schedule_completion_update()
    assert completion_widget_stub.set_model.called == regen


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
    # Make sure " is quoted properly
    (':set url.start_pages \'["https://www.|example.com"]\'',
     '["https://www.example.org"]',
     ':set url.start_pages \'["https://www.example.org"]\'|'),
    # open has maxsplit=0, so treat the last two tokens as one and don't quote
    (':open foo bar|', 'baz', ':open baz|'),
    (':open foo| bar', 'baz', ':open baz|'),
])
def test_on_selection_changed(before, newtxt, after, completer_obj,
                              config_stub, status_command_stub,
                              completion_widget_stub):
    """Test that on_selection_changed modifies the cmd text properly.

    The | represents the current cursor position in the cmd prompt.
    If quick is True and there is only 1 completion (count == 1),
    then we expect a space to be appended after the current word.
    """
    model = unittest.mock.Mock()
    completion_widget_stub.model.return_value = model

    def check(quick, count, expected_txt, expected_pos):
        config_stub.val.completion.quick = quick
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
    # a trailing space if at the end of the cmd string, unless the command has
    # maxsplit < len(before) (such as :open in these tests)
    if after_txt.startswith(':open'):
        return

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
    config_stub.val.completion.quick = True

    _set_cmd_prompt(status_command_stub, ':open |')
    completer_obj.schedule_completion_update()
    assert completion_widget_stub.set_model.called
    completion_widget_stub.set_model.reset_mock()

    # selecting a completion should not re-set the model
    completer_obj.on_selection_changed('http://example.com')
    completer_obj.schedule_completion_update()
    assert not completion_widget_stub.set_model.called


def test_min_chars(status_command_stub, completer_obj, completion_widget_stub,
                   config_stub, key_config_stub):
    """Test that an update is delayed until min_chars characters are input."""
    config_stub.val.completion.min_chars = 3

    # Test #3635, where min_chars could crash the first update
    _set_cmd_prompt(status_command_stub, ':set c|')
    completer_obj.schedule_completion_update()
    assert not completion_widget_stub.set_model.called

    _set_cmd_prompt(status_command_stub, ':set co|')
    completer_obj.schedule_completion_update()
    assert not completion_widget_stub.set_model.called

    _set_cmd_prompt(status_command_stub, ':set com|')
    completer_obj.schedule_completion_update()
    assert completion_widget_stub.set_model.call_count == 1
