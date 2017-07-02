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

import copy

import pytest
from PyQt5.QtCore import QObject, QUrl

import qutebrowser.app  # To register commands
from qutebrowser.commands import cmdexc
from qutebrowser.config import config, configdata, configexc
from qutebrowser.utils import objreg, usertypes


@pytest.fixture(autouse=True)
def configdata_init():
    """Initialize configdata if needed."""
    if configdata.DATA is None:
        configdata.init()


class TestChangeFilter:

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
            foo.meth(changed)

        else:

            @config.change_filter(option, function=True)
            def func():
                nonlocal was_called
                was_called = True

            func(changed)

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
         {'a': 'message-info foo', 'b': 'message-info bar', 'c': 'message-info baz'}),
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

    @pytest.mark.parametrize('as_default', [True, False])
    @pytest.mark.parametrize('force', [True, False])
    @pytest.mark.parametrize('key', ['a', '<Ctrl-X>'])
    def test_bind_duplicate(self, keyconf, config_stub, no_bindings,
                            as_default, force, key):
        bindings = {'normal': {'a': 'nop', '<Ctrl+x>': 'nop'}}
        if as_default:
            config_stub.val.bindings.default = bindings
            config_stub.val.bindings.commands = no_bindings
        else:
            config_stub.val.bindings.default = no_bindings
            config_stub.val.bindings.commands = bindings

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

    @pytest.mark.parametrize('as_default', [True, False])
    @pytest.mark.parametrize('key, normalized', [
        ('a', 'a'),
        ('<Ctrl-X>', '<ctrl+x>')
    ])
    @pytest.mark.parametrize('mode', ['normal', 'caret'])
    def test_unbind(self, keyconf, config_stub, qtbot, no_bindings,
                    as_default, key, normalized, mode):
        bindings = {
            'normal': {'a': 'nop', '<ctrl+x>': 'nop'},
            'caret': {'a': 'nop', '<ctrl+x>': 'nop'},
        }
        if as_default:
            config_stub.val.bindings.default = bindings
            config_stub.val.bindings.commands = no_bindings
        else:
            config_stub.val.bindings.default = no_bindings
            config_stub.val.bindings.commands = bindings

        with qtbot.wait_signal(config_stub.changed):
            keyconf.unbind(key, mode=mode)

        assert keyconf.get_command(key, mode) is None

        mode_bindings = config_stub.val.bindings.commands[mode]
        if as_default:
            default_bindings = config_stub.val.bindings.default
            assert default_bindings[mode] == bindings[mode]
            assert mode_bindings[normalized] is None
        else:
            assert normalized not in mode_bindings

    def test_unbind_unbound(self, keyconf, config_stub, no_bindings):
        """Try unbinding a key which is not bound."""
        config_stub.val.bindings.default = no_bindings
        config_stub.val.bindings.commands = no_bindings
        with pytest.raises(configexc.KeybindingError,
                           match="Can't find binding 'foobar' in normal mode"):
            keyconf.unbind('foobar', mode='normal')


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


class TestConfigCommands:

    @pytest.fixture
    def commands(self, config_stub):
        return config.ConfigCommands(config_stub)

    @pytest.fixture
    def tabbed_browser(self, stubs, win_registry):
        tb = stubs.TabbedBrowserStub()
        objreg.register('tabbed-browser', tb, scope='window', window=0)
        yield tb
        objreg.delete('tabbed-browser', scope='window', window=0)

    def test_set_no_args(self, commands, tabbed_browser):
        """:set

        Should open qute://settings."""
        commands.set(win_id=0)
        assert tabbed_browser.opened_url == QUrl('qute://settings')

    def test_get(self, config_stub, commands, message_mock):
        """:set url.auto_search?

        Should show the value.
        """
        config_stub.val.url.auto_search = 'never'
        commands.set(win_id=0, option='url.auto_search?')
        msg = message_mock.getmsg(usertypes.MessageLevel.info)
        assert msg.text == 'url.auto_search = never'

    @pytest.mark.parametrize('temp', [True, False])
    def test_set_simple(self, commands, config_stub, temp):
        """:set [-t] url.auto_search dns

        Should set the setting accordingly.
        """
        assert config_stub.val.url.auto_search == 'naive'
        commands.set(0, 'url.auto_search', 'dns', temp=temp)

        assert config_stub.val.url.auto_search == 'dns'

        if temp:
            assert 'url.auto_search' not in config_stub._yaml.values
        else:
            assert config_stub._yaml.values['url.auto_search'] == 'dns'

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
        """:set -p url.auto_search never

        Should set show the value.
        """
        assert config_stub.val.url.auto_search == 'naive'
        commands.set(0, 'url.auto_search', 'dns', print_=True)

        assert config_stub.val.url.auto_search == 'dns'
        msg = message_mock.getmsg(usertypes.MessageLevel.info)
        assert msg.text == 'url.auto_search = dns'

    def test_set_toggle(self, commands, config_stub):
        """:set auto_save.config!

        Should toggle the value.
        """
        assert config_stub.val.auto_save.config
        commands.set(0, 'auto_save.config!')
        assert not config_stub.val.auto_save.config
        assert not config_stub._yaml.values['auto_save.config']

    def test_set_toggle_nonbool(self, commands, config_stub):
        """:set url.auto_search!

        Should show an error
        """
        assert config_stub.val.url.auto_search == 'naive'
        with pytest.raises(cmdexc.CommandError, match="set: Can't toggle "
                           "non-bool setting url.auto_search"):
            commands.set(0, 'url.auto_search!')
        assert config_stub.val.url.auto_search == 'naive'

    def test_set_toggle_print(self, commands, config_stub, message_mock):
        """:set -p auto_save.config!

        Should toggle the value and show the new value.
        """
        commands.set(0, 'auto_save.config!', print_=True)
        msg = message_mock.getmsg(usertypes.MessageLevel.info)
        assert msg.text == 'auto_save.config = false'

    def test_set_invalid_option(self, commands):
        """:set foo bar

        Should show an error.
        """
        with pytest.raises(cmdexc.CommandError, match="set: No option 'foo'"):
            commands.set(0, 'foo', 'bar')

    def test_set_invalid_value(self, commands):
        """:set auto_save.config blah

        Should show an error.
        """
        with pytest.raises(cmdexc.CommandError,
                           match="set: Invalid value 'blah' - must be a "
                           "boolean!"):
            commands.set(0, 'auto_save.config', 'blah')

    @pytest.mark.parametrize('option', ['?', '!', 'url.auto_search'])
    def test_empty(self, commands, option):
        """:set ? / :set ! / :set url.auto_search

        Should show an error.
        See https://github.com/qutebrowser/qutebrowser/issues/1109
        """
        with pytest.raises(cmdexc.CommandError,
                           match="set: The following arguments are required: "
                                 "value"):
            commands.set(win_id=0, option=option)

    @pytest.mark.parametrize('suffix', '?!')
    def test_invalid(self, commands, suffix):
        """:set foo? / :set foo!

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
        """:set with multiple values."""
        opt = 'colors.statusbar.normal.bg'
        config_stub.set_obj(opt, initial)
        commands.set(0, opt, 'green', 'magenta', 'blue', 'yellow')
        assert config_stub.get(opt) == expected
        assert config_stub._yaml.values[opt] == expected
