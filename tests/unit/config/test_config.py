# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# Copyright 2014-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Tests for qutebrowser.config.config."""

import sys
import copy
import types
import logging
import unittest.mock

import pytest
from PyQt5.QtCore import QObject, QUrl
from PyQt5.QtGui import QColor

from qutebrowser import qutebrowser
from qutebrowser.commands import cmdexc
from qutebrowser.config import config, configdata, configexc, configfiles
from qutebrowser.utils import objreg, usertypes
from qutebrowser.misc import objects


@pytest.fixture(autouse=True)
def configdata_init():
    """Initialize configdata if needed."""
    if configdata.DATA is None:
        configdata.init()


@pytest.fixture
def keyconf(config_stub):
    config_stub.val.aliases = {}
    return config.KeyConfig(config_stub)


class TestChangeFilter:

    @pytest.fixture(autouse=True)
    def cleanup_globals(self, monkeypatch):
        """Make sure config._change_filters is cleaned up."""
        monkeypatch.setattr(config, '_change_filters', [])

    @pytest.mark.parametrize('option', ['foobar', 'tab', 'tabss', 'tabs.'])
    def test_unknown_option(self, option):
        cf = config.change_filter(option)
        with pytest.raises(configexc.NoOptionError):
            cf.validate()

    @pytest.mark.parametrize('option', ['confirm_quit', 'tabs', 'tabs.show'])
    def test_validate(self, option):
        cf = config.change_filter(option)
        cf.validate()
        assert cf in config._change_filters

    @pytest.mark.parametrize('method', [True, False])
    @pytest.mark.parametrize('option, changed, matches', [
        ('confirm_quit', 'confirm_quit', True),
        ('tabs', 'tabs.show', True),
        ('tabs.show', 'tabs.show', True),
        ('tabs', None, True),
        ('tabs', 'colors.tabs.bar.bg', False),
    ])
    def test_call(self, method, option, changed, matches):
        was_called = False
        if method:

            class Foo:

                @config.change_filter(option)
                def meth(self):
                    nonlocal was_called
                    was_called = True

            foo = Foo()
            foo.meth(changed)  # pylint: disable=too-many-function-args

        else:

            @config.change_filter(option, function=True)
            def func():
                nonlocal was_called
                was_called = True

            func(changed)  # pylint: disable=too-many-function-args

        assert was_called == matches


class TestKeyConfig:

    @pytest.fixture
    def keyconf(self, config_stub):
        config_stub.val.aliases = {}
        return config.KeyConfig(config_stub)

    @pytest.fixture
    def no_bindings(self):
        """Get a dict with no bindings."""
        return {'normal': {}}

    @pytest.mark.parametrize('key, expected', [
        ('A', 'A'),
        ('<Ctrl-X>', '<ctrl+x>'),
    ])
    def test_prepare_valid(self, keyconf, key, expected):
        """Make sure prepare normalizes the key."""
        assert keyconf._prepare(key, 'normal') == expected

    def test_prepare_invalid(self, keyconf):
        """Make sure prepare checks the mode."""
        with pytest.raises(configexc.KeybindingError):
            assert keyconf._prepare('x', 'abnormal')

    @pytest.mark.parametrize('commands, expected', [
        # Unbinding default key
        ({'a': None}, {'b': 'message-info bar'}),
        # Additional binding
        ({'c': 'message-info baz'},
         {'a': 'message-info foo', 'b': 'message-info bar',
          'c': 'message-info baz'}),
        # Unbinding unknown key
        ({'x': None}, {'a': 'message-info foo', 'b': 'message-info bar'}),
    ])
    def test_get_bindings_for_and_get_command(self, keyconf, config_stub,
                                              commands, expected):
        orig_default_bindings = {'normal': {'a': 'message-info foo',
                                            'b': 'message-info bar'},
                                 'insert': {},
                                 'hint': {},
                                 'passthrough': {},
                                 'command': {},
                                 'prompt': {},
                                 'caret': {},
                                 'register': {}}
        config_stub.val.bindings.default = copy.deepcopy(orig_default_bindings)
        config_stub.val.bindings.commands = {'normal': commands}
        bindings = keyconf.get_bindings_for('normal')

        # Make sure the code creates a copy and doesn't modify the setting
        assert config_stub.val.bindings.default == orig_default_bindings
        assert bindings == expected
        for key, command in expected.items():
            assert keyconf.get_command(key, 'normal') == command

    def test_get_command_unbound(self, keyconf, config_stub, no_bindings):
        config_stub.val.bindings.default = no_bindings
        config_stub.val.bindings.commands = no_bindings
        assert keyconf.get_command('foobar', 'normal') is None

    @pytest.mark.parametrize('bindings, expected', [
        # Simple
        ({'a': 'message-info foo', 'b': 'message-info bar'},
         {'message-info foo': ['a'], 'message-info bar': ['b']}),
        # Multiple bindings
        ({'a': 'message-info foo', 'b': 'message-info foo'},
         {'message-info foo': ['b', 'a']}),
        # With special keys (should be listed last and normalized)
        ({'a': 'message-info foo', '<Escape>': 'message-info foo'},
         {'message-info foo': ['a', '<escape>']}),
        # Chained command
        ({'a': 'message-info foo ;; message-info bar'},
         {'message-info foo': ['a'], 'message-info bar': ['a']}),
    ])
    def test_get_reverse_bindings_for(self, keyconf, config_stub, no_bindings,
                                      bindings, expected):
        config_stub.val.bindings.default = no_bindings
        config_stub.val.bindings.commands = {'normal': bindings}
        assert keyconf.get_reverse_bindings_for('normal') == expected

    def test_bind_invalid_command(self, keyconf):
        with pytest.raises(configexc.KeybindingError,
                           match='Invalid command: foobar'):
            keyconf.bind('a', 'foobar', mode='normal')

    def test_bind_invalid_mode(self, keyconf):
        with pytest.raises(configexc.KeybindingError,
                           match='completion-item-del: This command is only '
                           'allowed in command mode, not normal.'):
            keyconf.bind('a', 'completion-item-del', mode='normal')

    @pytest.mark.parametrize('force', [True, False])
    @pytest.mark.parametrize('key', ['a', '<Ctrl-X>', 'b'])
    def test_bind_duplicate(self, keyconf, config_stub, force, key):
        config_stub.val.bindings.default = {'normal': {'a': 'nop',
                                                       '<Ctrl+x>': 'nop'}}
        config_stub.val.bindings.commands = {'normal': {'b': 'nop'}}
        if force:
            keyconf.bind(key, 'message-info foo', mode='normal', force=True)
            assert keyconf.get_command(key, 'normal') == 'message-info foo'
        else:
            with pytest.raises(configexc.DuplicateKeyError):
                keyconf.bind(key, 'message-info foo', mode='normal')
            assert keyconf.get_command(key, 'normal') == 'nop'

    @pytest.mark.parametrize('mode', ['normal', 'caret'])
    def test_bind(self, keyconf, config_stub, qtbot, no_bindings, mode):
        config_stub.val.bindings.default = no_bindings
        config_stub.val.bindings.commands = no_bindings

        command = 'message-info foo'

        with qtbot.wait_signal(config_stub.changed):
            keyconf.bind('a', command, mode=mode)

        assert config_stub.val.bindings.commands[mode]['a'] == command
        assert keyconf.get_bindings_for(mode)['a'] == command
        assert keyconf.get_command('a', mode) == command

    @pytest.mark.parametrize('key, normalized', [
        ('a', 'a'),  # default bindings
        ('b', 'b'),  # custom bindings
        ('<Ctrl-X>', '<ctrl+x>')
    ])
    @pytest.mark.parametrize('mode', ['normal', 'caret', 'prompt'])
    def test_unbind(self, keyconf, config_stub, qtbot, key, normalized, mode):
        default_bindings = {
            'normal': {'a': 'nop', '<ctrl+x>': 'nop'},
            'caret': {'a': 'nop', '<ctrl+x>': 'nop'},
            # prompt: a mode which isn't in bindings.commands yet
            'prompt': {'a': 'nop', 'b': 'nop', '<ctrl+x>': 'nop'},
        }
        old_default_bindings = copy.deepcopy(default_bindings)
        config_stub.val.bindings.default = default_bindings
        config_stub.val.bindings.commands = {
            'normal': {'b': 'nop'},
            'caret': {'b': 'nop'},
        }

        with qtbot.wait_signal(config_stub.changed):
            keyconf.unbind(key, mode=mode)

        assert keyconf.get_command(key, mode) is None

        mode_bindings = config_stub.val.bindings.commands[mode]
        if key == 'b' and mode != 'prompt':
            # Custom binding
            assert normalized not in mode_bindings
        else:
            default_bindings = config_stub.val.bindings.default
            assert default_bindings[mode] == old_default_bindings[mode]
            assert mode_bindings[normalized] is None

    def test_unbind_unbound(self, keyconf, config_stub, no_bindings):
        """Try unbinding a key which is not bound."""
        config_stub.val.bindings.default = no_bindings
        config_stub.val.bindings.commands = no_bindings
        with pytest.raises(configexc.KeybindingError,
                           match="Can't find binding 'foobar' in normal mode"):
            keyconf.unbind('foobar', mode='normal')


class TestSetConfigCommand:

    """Tests for :set."""

    @pytest.fixture
    def commands(self, config_stub, keyconf):
        return config.ConfigCommands(config_stub, keyconf)

    @pytest.fixture
    def tabbed_browser(self, stubs, win_registry):
        tb = stubs.TabbedBrowserStub()
        objreg.register('tabbed-browser', tb, scope='window', window=0)
        yield tb
        objreg.delete('tabbed-browser', scope='window', window=0)

    def test_set_no_args(self, commands, tabbed_browser):
        """Run ':set'.

        Should open qute://settings."""
        commands.set(win_id=0)
        assert tabbed_browser.opened_url == QUrl('qute://settings')

    def test_get(self, config_stub, commands, message_mock):
        """Run ':set url.auto_search?'.

        Should show the value.
        """
        config_stub.val.url.auto_search = 'never'
        commands.set(win_id=0, option='url.auto_search?')
        msg = message_mock.getmsg(usertypes.MessageLevel.info)
        assert msg.text == 'url.auto_search = never'

    @pytest.mark.parametrize('temp', [True, False])
    @pytest.mark.parametrize('option, old_value, inp, new_value', [
        ('url.auto_search', 'naive', 'dns', 'dns'),
        # https://github.com/qutebrowser/qutebrowser/issues/2962
        ('editor.command', ['gvim', '-f', '{}'], '[emacs, "{}"]',
         ['emacs', '{}']),
    ])
    def test_set_simple(self, monkeypatch, commands, config_stub,
                        temp, option, old_value, inp, new_value):
        """Run ':set [-t] option value'.

        Should set the setting accordingly.
        """
        monkeypatch.setattr(objects, 'backend', usertypes.Backend.QtWebKit)
        assert config_stub.get(option) == old_value

        commands.set(0, option, inp, temp=temp)

        assert config_stub.get(option) == new_value

        if temp:
            assert option not in config_stub._yaml.values
        else:
            assert config_stub._yaml.values[option] == new_value

    @pytest.mark.parametrize('temp', [True, False])
    def test_set_temp_override(self, commands, config_stub, temp):
        """Invoking :set twice.

        :set url.auto_search dns
        :set -t url.auto_search never

        Should set the setting accordingly.
        """
        assert config_stub.val.url.auto_search == 'naive'
        commands.set(0, 'url.auto_search', 'dns')
        commands.set(0, 'url.auto_search', 'never', temp=True)

        assert config_stub.val.url.auto_search == 'never'
        assert config_stub._yaml.values['url.auto_search'] == 'dns'

    def test_set_print(self, config_stub, commands, message_mock):
        """Run ':set -p url.auto_search never'.

        Should set show the value.
        """
        assert config_stub.val.url.auto_search == 'naive'
        commands.set(0, 'url.auto_search', 'dns', print_=True)

        assert config_stub.val.url.auto_search == 'dns'
        msg = message_mock.getmsg(usertypes.MessageLevel.info)
        assert msg.text == 'url.auto_search = dns'

    def test_set_toggle(self, commands, config_stub):
        """Run ':set auto_save.session!'.

        Should toggle the value.
        """
        assert not config_stub.val.auto_save.session
        commands.set(0, 'auto_save.session!')
        assert config_stub.val.auto_save.session
        assert config_stub._yaml.values['auto_save.session']

    def test_set_toggle_nonbool(self, commands, config_stub):
        """Run ':set url.auto_search!'.

        Should show an error
        """
        assert config_stub.val.url.auto_search == 'naive'
        with pytest.raises(cmdexc.CommandError, match="set: Can't toggle "
                           "non-bool setting url.auto_search"):
            commands.set(0, 'url.auto_search!')
        assert config_stub.val.url.auto_search == 'naive'

    def test_set_toggle_print(self, commands, config_stub, message_mock):
        """Run ':set -p auto_save.session!'.

        Should toggle the value and show the new value.
        """
        commands.set(0, 'auto_save.session!', print_=True)
        msg = message_mock.getmsg(usertypes.MessageLevel.info)
        assert msg.text == 'auto_save.session = true'

    def test_set_invalid_option(self, commands):
        """Run ':set foo bar'.

        Should show an error.
        """
        with pytest.raises(cmdexc.CommandError, match="set: No option 'foo'"):
            commands.set(0, 'foo', 'bar')

    def test_set_invalid_value(self, commands):
        """Run ':set auto_save.session blah'.

        Should show an error.
        """
        with pytest.raises(cmdexc.CommandError,
                           match="set: Invalid value 'blah' - must be a "
                           "boolean!"):
            commands.set(0, 'auto_save.session', 'blah')

    def test_set_wrong_backend(self, commands, monkeypatch):
        monkeypatch.setattr(objects, 'backend', usertypes.Backend.QtWebEngine)
        with pytest.raises(cmdexc.CommandError,
                           match="set: This setting is not available with the "
                           "QtWebEngine backend!"):
            commands.set(0, 'content.cookies.accept', 'all')

    @pytest.mark.parametrize('option', ['?', '!', 'url.auto_search'])
    def test_empty(self, commands, option):
        """Run ':set ?' / ':set !' / ':set url.auto_search'.

        Should show an error.
        See https://github.com/qutebrowser/qutebrowser/issues/1109
        """
        with pytest.raises(cmdexc.CommandError,
                           match="set: The following arguments are required: "
                                 "value"):
            commands.set(win_id=0, option=option)

    @pytest.mark.parametrize('suffix', '?!')
    def test_invalid(self, commands, suffix):
        """Run ':set foo?' / ':set foo!'.

        Should show an error.
        """
        with pytest.raises(cmdexc.CommandError, match="set: No option 'foo'"):
            commands.set(win_id=0, option='foo' + suffix)

    @pytest.mark.parametrize('initial, expected', [
        # Normal cycling
        ('magenta', 'blue'),
        # Through the end of the list
        ('yellow', 'green'),
        # Value which is not in the list
        ('red', 'green'),
    ])
    def test_cycling(self, commands, config_stub, initial, expected):
        """Run ':set' with multiple values."""
        opt = 'colors.statusbar.normal.bg'
        config_stub.set_obj(opt, initial)
        commands.set(0, opt, 'green', 'magenta', 'blue', 'yellow')
        assert config_stub.get(opt) == expected
        assert config_stub._yaml.values[opt] == expected


class TestBindConfigCommand:

    """Tests for :bind and :unbind."""

    @pytest.fixture
    def commands(self, config_stub, keyconf):
        return config.ConfigCommands(config_stub, keyconf)

    @pytest.fixture
    def no_bindings(self):
        """Get a dict with no bindings."""
        return {'normal': {}}

    @pytest.mark.parametrize('command', ['nop', 'nope'])
    def test_bind(self, commands, config_stub, no_bindings, keyconf, command):
        """Simple :bind test (and aliases)."""
        config_stub.val.aliases = {'nope': 'nop'}
        config_stub.val.bindings.default = no_bindings
        config_stub.val.bindings.commands = no_bindings

        commands.bind('a', command)
        assert keyconf.get_command('a', 'normal') == command
        yaml_bindings = config_stub._yaml.values['bindings.commands']['normal']
        assert yaml_bindings['a'] == command

    @pytest.mark.parametrize('key, mode, expected', [
        # Simple
        ('a', 'normal', "a is bound to 'message-info a' in normal mode"),
        # Alias
        ('b', 'normal', "b is bound to 'mib' in normal mode"),
        # Custom binding
        ('c', 'normal', "c is bound to 'message-info c' in normal mode"),
        # Special key
        ('<Ctrl-X>', 'normal',
         "<ctrl+x> is bound to 'message-info C-x' in normal mode"),
        # unbound
        ('x', 'normal', "x is unbound in normal mode"),
        # non-default mode
        ('x', 'caret', "x is bound to 'nop' in caret mode"),
    ])
    def test_bind_print(self, commands, config_stub, message_mock,
                        key, mode, expected):
        """Run ':bind key'.

        Should print the binding.
        """
        config_stub.val.aliases = {'mib': 'message-info b'}
        config_stub.val.bindings.default = {
            'normal': {'a': 'message-info a',
                       'b': 'mib',
                       '<Ctrl+x>': 'message-info C-x'},
            'caret': {'x': 'nop'}
        }
        config_stub.val.bindings.commands = {
            'normal': {'c': 'message-info c'}
        }

        commands.bind(key, mode=mode)

        msg = message_mock.getmsg(usertypes.MessageLevel.info)
        assert msg.text == expected

    @pytest.mark.parametrize('command, mode, expected', [
        ('foobar', 'normal', "bind: Invalid command: foobar"),
        ('completion-item-del', 'normal',
            "bind: completion-item-del: This command is only allowed in "
            "command mode, not normal."),
        ('nop', 'wrongmode', "bind: Invalid mode wrongmode!"),
    ])
    def test_bind_invalid(self, commands, command, mode, expected):
        """Run ':bind a foobar' / ':bind a completion-item-del'.

        Should show an error.
        """
        with pytest.raises(cmdexc.CommandError, match=expected):
            commands.bind('a', command, mode=mode)

    @pytest.mark.parametrize('force', [True, False])
    @pytest.mark.parametrize('key', ['a', 'b', '<Ctrl-X>'])
    def test_bind_duplicate(self, commands, config_stub, keyconf, force, key):
        """Run ':bind' with a key which already has been bound.'.

        Also tests for https://github.com/qutebrowser/qutebrowser/issues/1544
        """
        config_stub.val.bindings.default = {
            'normal': {'a': 'nop', '<Ctrl+x>': 'nop'}
        }
        config_stub.val.bindings.commands = {
            'normal': {'b': 'nop'},
        }

        if force:
            commands.bind(key, 'message-info foo', mode='normal', force=True)
            assert keyconf.get_command(key, 'normal') == 'message-info foo'
        else:
            with pytest.raises(cmdexc.CommandError,
                               match="bind: Duplicate key .* - use --force to "
                               "override"):
                commands.bind(key, 'message-info foo', mode='normal')
            assert keyconf.get_command(key, 'normal') == 'nop'

    @pytest.mark.parametrize('key, normalized', [
        ('a', 'a'),  # default bindings
        ('b', 'b'),  # custom bindings
        ('c', 'c'),  # :bind then :unbind
        ('<Ctrl-X>', '<ctrl+x>')  # normalized special binding
    ])
    def test_unbind(self, commands, keyconf, config_stub, key, normalized):
        config_stub.val.bindings.default = {
            'normal': {'a': 'nop', '<ctrl+x>': 'nop'},
            'caret': {'a': 'nop', '<ctrl+x>': 'nop'},
        }
        config_stub.val.bindings.commands = {
            'normal': {'b': 'nop'},
            'caret': {'b': 'nop'},
        }
        if key == 'c':
            # Test :bind and :unbind
            commands.bind(key, 'nop')

        commands.unbind(key)
        assert keyconf.get_command(key, 'normal') is None

        yaml_bindings = config_stub._yaml.values['bindings.commands']['normal']
        if key in 'bc':
            # Custom binding
            assert normalized not in yaml_bindings
        else:
            assert yaml_bindings[normalized] is None

    @pytest.mark.parametrize('key, mode, expected', [
        ('foobar', 'normal',
         "unbind: Can't find binding 'foobar' in normal mode"),
        ('x', 'wrongmode', "unbind: Invalid mode wrongmode!"),
    ])
    def test_unbind_invalid(self, commands, key, mode, expected):
        """Run ':unbind foobar' / ':unbind x wrongmode'.

        Should show an error.
        """
        with pytest.raises(cmdexc.CommandError, match=expected):
            commands.unbind(key, mode=mode)


class TestConfig:

    @pytest.fixture
    def conf(self, stubs):
        yaml_config = stubs.FakeYamlConfig()
        return config.Config(yaml_config)

    def test_set_value(self, qtbot, conf, caplog):
        opt = conf.get_opt('tabs.show')
        with qtbot.wait_signal(conf.changed) as blocker:
            conf._set_value(opt, 'never')

        assert blocker.args == ['tabs.show']
        assert len(caplog.records) == 1
        expected_message = 'Config option changed: tabs.show = never'
        assert caplog.records[0].message == expected_message

    def test_read_yaml(self, conf):
        assert not conf._yaml.loaded
        conf._yaml.values['content.plugins'] = True

        conf.read_yaml()

        assert conf._yaml.loaded
        assert conf._values['content.plugins'] is True

    def test_read_yaml_invalid(self, conf):
        conf._yaml.values['foo.bar'] = True
        with pytest.raises(configexc.NoOptionError):
            conf.read_yaml()

    def test_get_opt_valid(self, conf):
        assert conf.get_opt('tabs.show') == configdata.DATA['tabs.show']

    def test_get_opt_invalid(self, conf):
        with pytest.raises(configexc.NoOptionError):
            conf.get_opt('tabs')

    def test_get(self, conf):
        """Test conf.get() with a QColor (where get/get_obj is different)."""
        assert conf.get('colors.completion.fg') == QColor('white')

    @pytest.mark.parametrize('value', [{}, {'normal': {'a': 'nop'}}])
    def test_get_bindings(self, config_stub, conf, value):
        """Test conf.get() with bindings which have missing keys."""
        config_stub.val.aliases = {}
        conf._values['bindings.commands'] = value
        assert conf.get('bindings.commands')['prompt'] == {}

    def test_get_mutable(self, conf):
        """Make sure we don't observe everything for mutations."""
        conf.get('content.headers.custom')
        assert not conf._mutables

    def test_get_obj_simple(self, conf):
        assert conf.get_obj('colors.completion.fg') == 'white'

    @pytest.mark.parametrize('option', ['content.headers.custom',
                                        'keyhint.blacklist',
                                        'bindings.commands'])
    @pytest.mark.parametrize('mutable', [True, False])
    @pytest.mark.parametrize('mutated', [True, False])
    def test_get_obj_mutable(self, conf, config_stub, qtbot, caplog,
                             option, mutable, mutated):
        """Make sure mutables are handled correctly.

        When we get a mutable object from the config, some invariants should be
        true:
          - The object we get from the config is always a copy, i.e. mutating
            it doesn't change the internal value (or default) stored in the
            config.
          - If we mutate the object (mutated=True) and the config watches for
            mutables (mutable=True), it should notice that the object changed.
          - With mutable=False, we should always get the old object back.

        We try this with a dict (content.headers.custom) and a list
        (keyhint.blacklist).
        """
        # Setting new value
        obj = conf.get_obj(option, mutable=mutable)
        with qtbot.assert_not_emitted(conf.changed):
            if option == 'content.headers.custom':
                old = {}
                new = {}
                assert obj == old
                if mutated:
                    obj['X-Answer'] = '42'
                    if mutable:
                        new = {'X-Answer': '42'}
                        assert obj == new
            elif option == 'keyhint.blacklist':
                old = []
                new = []
                assert obj == old
                if mutated:
                    obj.append('foo')
                    if mutable:
                        new = ['foo']
                        assert obj == new
            else:
                assert option == 'bindings.commands'
                config_stub.val.aliases = {}
                old = {}
                new = {}
                assert obj == old
                if mutated:
                    obj['prompt'] = {}
                    obj['prompt']['foobar'] = 'nop'
                    if mutable:
                        new = {'prompt': {'foobar': 'nop'}}
                        assert obj == new

        if mutable:
            assert conf._mutables == [(option, old, new)]

        if mutable and mutated:
            # Now let's update
            with qtbot.wait_signal(conf.changed):
                conf.update_mutables()

            expected_log = '{} was mutated, updating'.format(option)
            assert caplog.records[-2].message == expected_log
        else:
            with qtbot.assert_not_emitted(conf.changed):
                conf.update_mutables()

        assert not conf._mutables
        assert conf.get_obj(option) == new

    def test_get_obj_unknown_mutable(self, conf):
        """Make sure we don't have unknown mutable types."""
        conf._values['aliases'] = set()  # This would never happen
        with pytest.raises(AssertionError):
            conf.get_obj('aliases')

    def test_get_str(self, conf):
        assert conf.get_str('content.plugins') == 'false'

    @pytest.mark.parametrize('save_yaml', [True, False])
    @pytest.mark.parametrize('method, value', [
        ('set_obj', True),
        ('set_str', 'true'),
    ])
    def test_set_valid(self, conf, qtbot, save_yaml, method, value):
        option = 'content.plugins'
        meth = getattr(conf, method)
        with qtbot.wait_signal(conf.changed):
            meth(option, value, save_yaml=save_yaml)
        assert conf._values[option] is True
        if save_yaml:
            assert conf._yaml.values[option] is True
        else:
            assert option not in conf._yaml.values

    @pytest.mark.parametrize('method', ['set_obj', 'set_str'])
    def test_set_invalid(self, conf, qtbot, method):
        meth = getattr(conf, method)
        with pytest.raises(configexc.ValidationError):
            with qtbot.assert_not_emitted(conf.changed):
                meth('content.plugins', '42')
        assert 'content.plugins' not in conf._values

    @pytest.mark.parametrize('method', ['set_obj', 'set_str'])
    def test_set_wrong_backend(self, conf, qtbot, monkeypatch, method):
        monkeypatch.setattr(objects, 'backend', usertypes.Backend.QtWebEngine)
        meth = getattr(conf, method)
        with pytest.raises(configexc.BackendError):
            with qtbot.assert_not_emitted(conf.changed):
                meth('content.cookies.accept', 'all')
        assert 'content.cookies.accept' not in conf._values

    def test_dump_userconfig(self, conf):
        conf.set_obj('content.plugins', True)
        conf.set_obj('content.headers.custom', {'X-Foo': 'bar'})
        lines = ['content.headers.custom = {"X-Foo": "bar"}',
                 'content.plugins = true']
        assert conf.dump_userconfig().splitlines() == lines

    def test_dump_userconfig_default(self, conf):
        assert conf.dump_userconfig() == '<Default configuration>'


class TestContainer:

    @pytest.fixture
    def container(self, config_stub):
        return config.ConfigContainer(config_stub)

    def test_getattr_invalid_private(self, container):
        """Make sure an invalid _attribute doesn't try getting a container."""
        with pytest.raises(AttributeError):
            container._foo  # pylint: disable=pointless-statement

    def test_getattr_prefix(self, container):
        new_container = container.tabs
        assert new_container._prefix == 'tabs'
        new_container = new_container.favicons
        assert new_container._prefix == 'tabs.favicons'

    @pytest.mark.parametrize('configapi, expected', [
        (object(), 'rgb'),
        (None, QColor.Rgb),
    ])
    def test_getattr_option(self, container, configapi, expected):
        container._configapi = configapi
        # Use an option with a to_py() so we can check the conversion.
        assert container.colors.downloads.system.fg == expected

    def test_getattr_invalid(self, container):
        with pytest.raises(configexc.NoOptionError) as excinfo:
            container.tabs.foobar  # pylint: disable=pointless-statement
        assert excinfo.value.option == 'tabs.foobar'

    def test_setattr_option(self, config_stub, container):
        container.content.cookies.store = False
        assert config_stub._values['content.cookies.store'] is False

    def test_confapi_errors(self, container):
        configapi = types.SimpleNamespace(errors=[])
        container._configapi = configapi
        container.tabs.foobar  # pylint: disable=pointless-statement

        assert len(configapi.errors) == 1
        error = configapi.errors[0]
        assert error.text == "While getting 'tabs.foobar'"
        assert str(error.exception) == "No option 'tabs.foobar'"


class StyleObj(QObject):

    def __init__(self, stylesheet=None, parent=None):
        super().__init__(parent)
        if stylesheet is not None:
            self.STYLESHEET = stylesheet  # pylint: disable=invalid-name
        self.rendered_stylesheet = None

    def setStyleSheet(self, stylesheet):
        self.rendered_stylesheet = stylesheet


def test_get_stylesheet(config_stub):
    config_stub.val.colors.hints.fg = 'magenta'
    observer = config.StyleSheetObserver(
        StyleObj(), stylesheet="{{ conf.colors.hints.fg }}")
    assert observer._get_stylesheet() == 'magenta'


@pytest.mark.parametrize('delete', [True, False])
@pytest.mark.parametrize('stylesheet_param', [True, False])
@pytest.mark.parametrize('update', [True, False])
def test_set_register_stylesheet(delete, stylesheet_param, update, qtbot,
                                 config_stub, caplog):
    config_stub.val.colors.hints.fg = 'magenta'
    stylesheet = "{{ conf.colors.hints.fg }}"

    with caplog.at_level(9):  # VDEBUG
        if stylesheet_param:
            obj = StyleObj()
            config.set_register_stylesheet(obj, stylesheet=stylesheet,
                                           update=update)
        else:
            obj = StyleObj(stylesheet)
            config.set_register_stylesheet(obj, update=update)

    assert caplog.records[-1].message == 'stylesheet for StyleObj: magenta'

    assert obj.rendered_stylesheet == 'magenta'

    if delete:
        with qtbot.waitSignal(obj.destroyed):
            obj.deleteLater()

    config_stub.val.colors.hints.fg = 'yellow'

    if delete or not update:
        expected = 'magenta'
    else:
        expected = 'yellow'

    assert obj.rendered_stylesheet == expected


@pytest.fixture
def init_patch(qapp, fake_save_manager, monkeypatch, config_tmpdir,
               data_tmpdir):
    monkeypatch.setattr(configdata, 'DATA', None)
    monkeypatch.setattr(configfiles, 'state', None)
    monkeypatch.setattr(config, 'instance', None)
    monkeypatch.setattr(config, 'key_instance', None)
    monkeypatch.setattr(config, '_change_filters', [])
    monkeypatch.setattr(config, '_init_errors', [])
    # Make sure we get no SSL warning
    monkeypatch.setattr(config.earlyinit, 'check_backend_ssl_support',
                        lambda _backend: None)
    yield
    try:
        objreg.delete('config-commands')
    except KeyError:
        pass


@pytest.mark.parametrize('load_autoconfig', [True, False])  # noqa
@pytest.mark.parametrize('config_py', [True, 'error', False])
@pytest.mark.parametrize('invalid_yaml', ['42', 'unknown', False])
# pylint: disable=too-many-branches
def test_early_init(init_patch, config_tmpdir, caplog, fake_args,
                    load_autoconfig, config_py, invalid_yaml):
    # Prepare files
    autoconfig_file = config_tmpdir / 'autoconfig.yml'
    config_py_file = config_tmpdir / 'config.py'

    if invalid_yaml == '42':
        autoconfig_file.write_text('42', 'utf-8', ensure=True)
    elif invalid_yaml == 'unknown':
        autoconfig_file.write_text('global:\n  colors.foobar: magenta\n',
                                   'utf-8', ensure=True)
    else:
        assert not invalid_yaml
        autoconfig_file.write_text('global:\n  colors.hints.fg: magenta\n',
                                   'utf-8', ensure=True)

    if config_py:
        config_py_lines = ['c.colors.hints.bg = "red"']
        if not load_autoconfig:
            config_py_lines.append('config.load_autoconfig = False')
        if config_py == 'error':
            config_py_lines.append('c.foo = 42')
        config_py_file.write_text('\n'.join(config_py_lines),
                                  'utf-8', ensure=True)

    with caplog.at_level(logging.ERROR):
        config.early_init(fake_args)

    # Check error messages
    expected_errors = []
    if config_py == 'error':
        expected_errors.append(
            "Errors occurred while reading config.py:\n"
            "  While setting 'foo': No option 'foo'")
    if invalid_yaml and (load_autoconfig or not config_py):
        error = "Errors occurred while reading autoconfig.yml:\n"
        if invalid_yaml == '42':
            error += "  While loading data: Toplevel object is not a dict"
        elif invalid_yaml == 'unknown':
            error += "  Error: No option 'colors.foobar'"
        else:
            assert False, invalid_yaml
        expected_errors.append(error)

    actual_errors = [str(err) for err in config._init_errors]
    assert actual_errors == expected_errors

    # Make sure things have been init'ed
    objreg.get('config-commands')
    assert isinstance(config.instance, config.Config)
    assert isinstance(config.key_instance, config.KeyConfig)

    # Check config values
    if config_py and load_autoconfig and not invalid_yaml:
        assert config.instance._values == {
            'colors.hints.bg': 'red',
            'colors.hints.fg': 'magenta',
        }
    elif config_py:
        assert config.instance._values == {'colors.hints.bg': 'red'}
    elif invalid_yaml:
        assert config.instance._values == {}
    else:
        assert config.instance._values == {'colors.hints.fg': 'magenta'}


def test_early_init_invalid_change_filter(init_patch, fake_args):
    config.change_filter('foobar')
    with pytest.raises(configexc.NoOptionError):
        config.early_init(fake_args)


@pytest.mark.parametrize('errors', [True, False])
def test_late_init(init_patch, monkeypatch, fake_save_manager, fake_args,
                   mocker, errors):
    config.early_init(fake_args)
    if errors:
        err = configexc.ConfigErrorDesc("Error text", Exception("Exception"))
        errs = configexc.ConfigFileErrors("config.py", [err])
        monkeypatch.setattr(config, '_init_errors', [errs])
    msgbox_mock = mocker.patch('qutebrowser.config.config.msgbox.msgbox',
                               autospec=True)

    config.late_init(fake_save_manager)

    fake_save_manager.add_saveable.assert_any_call(
        'state-config', unittest.mock.ANY)
    fake_save_manager.add_saveable.assert_any_call(
        'yaml-config', unittest.mock.ANY)
    if errors:
        assert len(msgbox_mock.call_args_list) == 1
        _call_posargs, call_kwargs = msgbox_mock.call_args_list[0]
        text = call_kwargs['text'].strip()
        assert text.startswith('Errors occurred while reading config.py:')
        assert '<b>Error text</b>: Exception' in text
    else:
        assert not msgbox_mock.called


class TestQtArgs:

    @pytest.fixture
    def parser(self, mocker):
        """Fixture to provide an argparser.

        Monkey-patches .exit() of the argparser so it doesn't exit on errors.
        """
        parser = qutebrowser.get_argparser()
        mocker.patch.object(parser, 'exit', side_effect=Exception)
        return parser

    @pytest.mark.parametrize('args, expected', [
        # No Qt arguments
        (['--debug'], [sys.argv[0]]),
        # Qt flag
        (['--debug', '--qt-flag', 'reverse'], [sys.argv[0], '--reverse']),
        # Qt argument with value
        (['--qt-arg', 'stylesheet', 'foo'],
         [sys.argv[0], '--stylesheet', 'foo']),
        # --qt-arg given twice
        (['--qt-arg', 'stylesheet', 'foo', '--qt-arg', 'geometry', 'bar'],
         [sys.argv[0], '--stylesheet', 'foo', '--geometry', 'bar']),
        # --qt-flag given twice
        (['--qt-flag', 'foo', '--qt-flag', 'bar'],
         [sys.argv[0], '--foo', '--bar']),
    ])
    def test_qt_args(self, config_stub, args, expected, parser):
        """Test commandline with no Qt arguments given."""
        parsed = parser.parse_args(args)
        assert config.qt_args(parsed) == expected

    def test_qt_both(self, config_stub, parser):
        """Test commandline with a Qt argument and flag."""
        args = parser.parse_args(['--qt-arg', 'stylesheet', 'foobar',
                                  '--qt-flag', 'reverse'])
        qt_args = config.qt_args(args)
        assert qt_args[0] == sys.argv[0]
        assert '--reverse' in qt_args
        assert '--stylesheet' in qt_args
        assert 'foobar' in qt_args

    def test_with_settings(self, config_stub, parser):
        parsed = parser.parse_args(['--qt-flag', 'foo'])
        config_stub.val.qt_args = ['bar']
        assert config.qt_args(parsed) == [sys.argv[0], '--foo', '--bar']
