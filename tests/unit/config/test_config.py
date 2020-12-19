# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

import types
import unittest.mock
import functools

import pytest
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QColor

from qutebrowser.config import config, configdata, configexc
from qutebrowser.utils import usertypes, urlmatch
from qutebrowser.misc import objects
from qutebrowser.keyinput import keyutils


@pytest.fixture(autouse=True)
def configdata_init():
    """Initialize configdata if needed."""
    if configdata.DATA is None:
        configdata.init()


# Alias because we need this a lot in here.
def keyseq(s):
    return keyutils.KeySequence.parse(s)


class TestChangeFilter:

    @pytest.fixture(autouse=True)
    def cleanup_globals(self, monkeypatch):
        """Make sure config.change_filters is cleaned up."""
        monkeypatch.setattr(config, 'change_filters', [])

    @pytest.mark.parametrize('option', ['foobar', 'tab', 'tabss', 'tabs.'])
    def test_unknown_option(self, option):
        cf = config.change_filter(option)
        with pytest.raises(configexc.NoOptionError):
            cf.validate()

    @pytest.mark.parametrize('option', ['confirm_quit', 'tabs', 'tabs.show'])
    def test_validate(self, option):
        cf = config.change_filter(option)
        cf.validate()
        assert cf in config.change_filters

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
    def no_bindings(self):
        """Get a dict with no bindings."""
        return {'normal': {}}

    def test_validate_invalid_mode(self, key_config_stub):
        with pytest.raises(configexc.KeybindingError):
            assert key_config_stub._validate(keyseq('x'), 'abnormal')

    def test_validate_invalid_type(self, key_config_stub):
        with pytest.raises(AssertionError):
            assert key_config_stub._validate('x', 'normal')

    @pytest.mark.parametrize('commands, expected', [
        # Unbinding default key
        ({'a': None}, {keyseq('b'): 'message-info bar'}),
        # Additional binding
        ({'c': 'message-info baz'},
         {keyseq('a'): 'message-info foo',
          keyseq('b'): 'message-info bar',
          keyseq('c'): 'message-info baz'}),
        # Unbinding unknown key
        ({'x': None}, {keyseq('a'): 'message-info foo',
                       keyseq('b'): 'message-info bar'}),
    ])
    def test_get_bindings_for_and_get_command(self, key_config_stub,
                                              config_stub,
                                              commands, expected):
        orig_default_bindings = {
            'normal': {'a': 'message-info foo',
                       'b': 'message-info bar'},
            'insert': {},
            'hint': {},
            'passthrough': {},
            'command': {},
            'prompt': {},
            'caret': {},
            'register': {},
            'yesno': {}
        }
        expected_default_bindings = {
            'normal': {keyseq('a'): 'message-info foo',
                       keyseq('b'): 'message-info bar'},
            'insert': {},
            'hint': {},
            'passthrough': {},
            'command': {},
            'prompt': {},
            'caret': {},
            'register': {},
            'yesno': {}
        }

        config_stub.val.bindings.default = orig_default_bindings
        config_stub.val.bindings.commands = {'normal': commands}
        bindings = key_config_stub.get_bindings_for('normal')

        # Make sure the code creates a copy and doesn't modify the setting
        assert config_stub.val.bindings.default == expected_default_bindings
        assert bindings == expected
        for key, command in expected.items():
            assert key_config_stub.get_command(key, 'normal') == command

    def test_get_bindings_for_empty_command(self, key_config_stub,
                                            config_stub):
        config_stub.val.bindings.commands = {'normal': {',x': ''}}
        bindings = key_config_stub.get_bindings_for('normal')
        assert keyseq(',x') not in bindings

    def test_get_command_unbound(self, key_config_stub, config_stub,
                                 no_bindings):
        config_stub.val.bindings.default = no_bindings
        config_stub.val.bindings.commands = no_bindings
        command = key_config_stub.get_command(keyseq('foobar'),
                                              'normal')
        assert command is None

    def test_get_command_default(self, key_config_stub, config_stub):
        config_stub.val.bindings.default = {
            'normal': {'x': 'message-info default'}}
        config_stub.val.bindings.commands = {
            'normal': {'x': 'message-info custom'}}
        command = key_config_stub.get_command(keyseq('x'), 'normal',
                                              default=True)
        assert command == 'message-info default'

    @pytest.mark.parametrize('bindings, expected', [
        # Simple
        ({'a': 'message-info foo', 'b': 'message-info bar'},
         {'message-info foo': ['a'], 'message-info bar': ['b']}),
        # Multiple bindings
        ({'a': 'message-info foo', 'b': 'message-info foo'},
         {'message-info foo': ['b', 'a']}),
        # With modifier keys (should be listed last and normalized)
        ({'a': 'message-info foo', '<ctrl-a>': 'message-info foo'},
         {'message-info foo': ['a', '<Ctrl+a>']}),
        # Chained command
        ({'a': 'message-info foo ;; message-info bar'},
         {'message-info foo': ['a'], 'message-info bar': ['a']}),
    ])
    def test_get_reverse_bindings_for(self, key_config_stub, config_stub,
                                      no_bindings, bindings, expected):
        config_stub.val.bindings.default = no_bindings
        config_stub.val.bindings.commands = {'normal': bindings}
        assert key_config_stub.get_reverse_bindings_for('normal') == expected

    @pytest.mark.parametrize('key', ['a', '<Ctrl-X>', 'b'])
    def test_bind_duplicate(self, key_config_stub, config_stub, key):
        seq = keyseq(key)
        config_stub.val.bindings.default = {'normal': {'a': 'nop',
                                                       '<Ctrl+x>': 'nop'}}
        config_stub.val.bindings.commands = {'normal': {'b': 'nop'}}
        key_config_stub.bind(seq, 'message-info foo', mode='normal')

        command = key_config_stub.get_command(seq, 'normal')
        assert command == 'message-info foo'

    @pytest.mark.parametrize('mode', ['normal', 'caret'])
    @pytest.mark.parametrize('command', [
        'message-info foo',
        'nop ;; wq',  # https://github.com/qutebrowser/qutebrowser/issues/3002
    ])
    def test_bind(self, key_config_stub, config_stub, qtbot, no_bindings,
                  mode, command):
        config_stub.val.bindings.default = no_bindings
        config_stub.val.bindings.commands = no_bindings
        seq = keyseq('a')

        with qtbot.wait_signal(config_stub.changed):
            key_config_stub.bind(seq, command, mode=mode)

        assert config_stub.val.bindings.commands[mode][seq] == command
        assert key_config_stub.get_bindings_for(mode)[seq] == command
        assert key_config_stub.get_command(seq, mode) == command

    def test_bind_mode_changing(self, key_config_stub, config_stub,
                                no_bindings):
        """Make sure we can bind to a command which changes the mode.

        https://github.com/qutebrowser/qutebrowser/issues/2989
        """
        config_stub.val.bindings.default = no_bindings
        config_stub.val.bindings.commands = no_bindings
        key_config_stub.bind(keyseq('a'),
                             'set-cmd-text :nop ;; rl-beginning-of-line',
                             mode='normal')

    def test_bind_default(self, key_config_stub, config_stub):
        """Bind a key to its default."""
        default_cmd = 'message-info default'
        bound_cmd = 'message-info bound'
        config_stub.val.bindings.default = {'normal': {'a': default_cmd}}
        config_stub.val.bindings.commands = {'normal': {'a': bound_cmd}}
        seq = keyseq('a')

        command = key_config_stub.get_command(seq, mode='normal')
        assert command == bound_cmd

        key_config_stub.bind_default(seq, mode='normal')

        command = key_config_stub.get_command(keyseq('a'), mode='normal')
        assert command == default_cmd

    def test_bind_default_unbound(self, key_config_stub, config_stub,
                                  no_bindings):
        """Try binding a key to default which is not bound."""
        config_stub.val.bindings.default = no_bindings
        config_stub.val.bindings.commands = no_bindings
        with pytest.raises(configexc.KeybindingError,
                           match="Can't find binding 'foobar' in normal mode"):
            key_config_stub.bind_default(keyseq('foobar'), mode='normal')

    @pytest.mark.parametrize('key', [
        'a',  # default bindings
        'b',  # custom bindings
        '<Ctrl-X>',
    ])
    @pytest.mark.parametrize('mode', ['normal', 'caret', 'prompt'])
    def test_unbind(self, key_config_stub, config_stub, qtbot,
                    key, mode):
        default_bindings = {
            'normal': {'a': 'nop', '<ctrl+x>': 'nop'},
            'caret': {'a': 'nop', '<ctrl+x>': 'nop'},
            # prompt: a mode which isn't in bindings.commands yet
            'prompt': {'a': 'nop', 'b': 'nop', '<ctrl+x>': 'nop'},
        }
        expected_default_bindings = {
            'normal': {keyseq('a'): 'nop', keyseq('<ctrl+x>'): 'nop'},
            'caret': {keyseq('a'): 'nop', keyseq('<ctrl+x>'): 'nop'},
            # prompt: a mode which isn't in bindings.commands yet
            'prompt': {keyseq('a'): 'nop',
                       keyseq('b'): 'nop',
                       keyseq('<ctrl+x>'): 'nop'},
        }

        config_stub.val.bindings.default = default_bindings
        config_stub.val.bindings.commands = {
            'normal': {'b': 'nop'},
            'caret': {'b': 'nop'},
        }
        seq = keyseq(key)

        with qtbot.wait_signal(config_stub.changed):
            key_config_stub.unbind(seq, mode=mode)

        assert key_config_stub.get_command(seq, mode) is None

        mode_bindings = config_stub.val.bindings.commands[mode]
        if key == 'b' and mode != 'prompt':
            # Custom binding
            assert seq not in mode_bindings
        else:
            default_bindings = config_stub.val.bindings.default
            assert default_bindings[mode] == expected_default_bindings[mode]
            assert mode_bindings[seq] is None

    def test_unbind_unbound(self, key_config_stub, config_stub, no_bindings):
        """Try unbinding a key which is not bound."""
        config_stub.val.bindings.default = no_bindings
        config_stub.val.bindings.commands = no_bindings
        with pytest.raises(configexc.KeybindingError,
                           match="Can't find binding 'foobar' in normal mode"):
            key_config_stub.unbind(keyseq('foobar'), mode='normal')

    def test_unbound_twice(self, key_config_stub, config_stub, no_bindings):
        """Try unbinding an already-unbound default key.

        For custom-bound keys (in bindings.commands), it's okay to display an
        error, as this isn't something you'd do in e.g a config.py anyways.

        https://github.com/qutebrowser/qutebrowser/issues/3162
        """
        config_stub.val.bindings.default = {'normal': {'a': 'nop'}}
        config_stub.val.bindings.commands = no_bindings
        seq = keyseq('a')

        key_config_stub.unbind(seq)
        assert key_config_stub.get_command(seq, mode='normal') is None
        key_config_stub.unbind(seq)
        assert key_config_stub.get_command(seq, mode='normal') is None

    def test_unbind_old_syntax(self, yaml_config_stub, key_config_stub,
                               config_stub):
        """Test unbinding bindings added before the keybinding refactoring.

        We used to normalize keys differently, so we can have <ctrl+q> in the
        config.

        See https://github.com/qutebrowser/qutebrowser/issues/3699
        """
        bindings = {'normal': {'<ctrl+q>': 'nop'}}
        yaml_config_stub.set_obj('bindings.commands', bindings)
        config_stub.read_yaml()

        key_config_stub.unbind(keyutils.KeySequence.parse('<ctrl+q>'),
                               save_yaml=True)

        assert config.instance.get_obj('bindings.commands') == {'normal': {}}

    def test_empty_command(self, key_config_stub):
        """Try binding a key to an empty command."""
        message = "Can't add binding 'x' with empty command in normal mode"
        with pytest.raises(configexc.KeybindingError, match=message):
            key_config_stub.bind(keyseq('x'), ' ', mode='normal')


class TestConfig:

    @pytest.fixture
    def conf(self, config_stub):
        return config_stub

    @pytest.fixture
    def yaml_value(self, conf):
        """Fixture which provides a getter for a YAML value."""
        def getter(option):
            return conf._yaml._values[option].get_for_url(fallback=False)
        return getter

    def test_init_save_manager(self, conf, fake_save_manager):
        conf.init_save_manager(fake_save_manager)
        fake_save_manager.add_saveable.assert_called_once_with(
            'yaml-config', unittest.mock.ANY, unittest.mock.ANY)

    def test_set_value(self, qtbot, conf, caplog):
        opt = conf.get_opt('tabs.show')
        with qtbot.wait_signal(conf.changed) as blocker:
            conf._set_value(opt, 'never')

        assert blocker.args == ['tabs.show']
        expected_message = 'Config option changed: tabs.show = never'
        assert caplog.messages == [expected_message]

    def test_set_value_no_backend(self, monkeypatch, conf):
        """Make sure setting values when the backend is still unknown works."""
        monkeypatch.setattr(config.objects, 'backend', objects.NoBackend())
        opt = conf.get_opt('tabs.show')
        conf._set_value(opt, 'never')
        assert conf.get_obj('tabs.show') == 'never'

    @pytest.mark.parametrize('save_yaml', [True, False])
    def test_unset(self, conf, qtbot, yaml_value, save_yaml):
        name = 'tabs.show'
        conf.set_obj(name, 'never', save_yaml=True)
        assert conf.get(name) == 'never'

        with qtbot.wait_signal(conf.changed):
            conf.unset(name, save_yaml=save_yaml)

        assert conf.get(name) == 'always'
        if save_yaml:
            assert yaml_value(name) is usertypes.UNSET
        else:
            assert yaml_value(name) == 'never'

    def test_unset_never_set(self, conf, qtbot):
        name = 'tabs.show'
        assert conf.get(name) == 'always'

        with qtbot.assert_not_emitted(conf.changed):
            conf.unset(name)

        assert conf.get(name) == 'always'

    @pytest.mark.parametrize('save_yaml', [True, False])
    def test_clear(self, conf, qtbot, yaml_value, save_yaml):
        name1 = 'tabs.show'
        name2 = 'content.plugins'
        conf.set_obj(name1, 'never', save_yaml=True)
        conf.set_obj(name2, True, save_yaml=True)
        assert conf.get_obj(name1) == 'never'
        assert conf.get_obj(name2) is True

        with qtbot.waitSignals([conf.changed, conf.changed]) as blocker:
            conf.clear(save_yaml=save_yaml)

        options = {e.args[0] for e in blocker.all_signals_and_args}
        assert options == {name1, name2}

        if save_yaml:
            assert yaml_value(name1) is usertypes.UNSET
            assert yaml_value(name2) is usertypes.UNSET
        else:
            assert yaml_value(name1) == 'never'
            assert yaml_value(name2) is True

    def test_read_yaml(self, conf, yaml_value):
        conf._yaml.set_obj('content.plugins', True)
        conf.read_yaml()
        assert conf.get_obj('content.plugins') is True

    def test_get_opt_valid(self, conf):
        assert conf.get_opt('tabs.show') == configdata.DATA['tabs.show']

    @pytest.mark.parametrize('code', [
        lambda c: c.get_opt('tabs'),
        lambda c: c.get('tabs'),
        lambda c: c.get_obj('tabs'),
        lambda c: c.get_obj_for_pattern('tabs', pattern=None),
        lambda c: c.get_mutable_obj('tabs'),
        lambda c: c.get_str('tabs'),

        lambda c: c.set_obj('tabs', 42),
        lambda c: c.set_str('tabs', '42'),
        lambda c: c.unset('tabs'),
    ])
    def test_no_option_error(self, conf, code):
        with pytest.raises(configexc.NoOptionError):
            code(conf)

    def test_get(self, conf):
        """Test conf.get() with a QColor (where get/get_obj is different)."""
        assert conf.get('colors.completion.category.fg') == QColor('white')

    def test_get_for_url(self, conf):
        """Test conf.get() with a URL/pattern."""
        pattern = urlmatch.UrlPattern('*://example.com/')
        name = 'content.javascript.enabled'
        conf.set_obj(name, False, pattern=pattern)
        assert conf.get(name, url=QUrl('https://example.com/')) is False

    @pytest.mark.parametrize('fallback, expected', [
        (True, True),
        (False, usertypes.UNSET)
    ])
    def test_get_for_url_fallback(self, conf, fallback, expected):
        """Test conf.get() with a URL and fallback."""
        value = conf.get('content.javascript.enabled',
                         url=QUrl('https://example.com/'),
                         fallback=fallback)
        assert value is expected

    @pytest.mark.parametrize('value', [{}, {'normal': {'a': 'nop'}}])
    def test_get_bindings(self, config_stub, conf, value):
        """Test conf.get() with bindings which have missing keys."""
        config_stub.val.aliases = {}
        conf.set_obj('bindings.commands', value)
        assert conf.get('bindings.commands')['prompt'] == {}

    def test_get_mutable(self, conf):
        """Make sure we don't observe everything for mutations."""
        conf.get('content.headers.custom')
        assert not conf._mutables

    def test_get_obj_simple(self, conf):
        assert conf.get_obj('colors.completion.category.fg') == 'white'

    @pytest.mark.parametrize('option', ['content.headers.custom',
                                        'keyhint.blacklist',
                                        'bindings.commands'])
    @pytest.mark.parametrize('mutable', [True, False])
    @pytest.mark.parametrize('mutated', [True, False])
    def test_get_obj_mutable(self, conf, qtbot, caplog,
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
        obj = conf.get_mutable_obj(option) if mutable else conf.get_obj(option)
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
            assert conf._mutables[option] == (old, new)

        if mutable and mutated:
            # Now let's update
            with qtbot.wait_signal(conf.changed):
                conf.update_mutables()

            expected_log = '{} was mutated, updating'.format(option)
            assert caplog.messages[-2] == expected_log
        else:
            with qtbot.assert_not_emitted(conf.changed):
                conf.update_mutables()

        assert not conf._mutables
        assert conf.get_obj(option) == new

    def test_get_mutable_twice(self, conf):
        """Get a mutable value twice."""
        option = 'content.headers.custom'
        obj = conf.get_mutable_obj(option)
        obj['X-Foo'] = 'fooval'
        obj2 = conf.get_mutable_obj(option)
        obj2['X-Bar'] = 'barval'

        conf.update_mutables()

        expected = {'X-Foo': 'fooval', 'X-Bar': 'barval'}
        assert conf.get_obj(option) == expected

    def test_get_obj_unknown_mutable(self, conf):
        """Make sure we don't have unknown mutable types."""
        with pytest.raises(AssertionError):
            conf._maybe_copy(set())

    def test_copy_non_mutable(self, conf, mocker):
        """Make sure no copies are done for non-mutable types."""
        spy = mocker.spy(config.copy, 'deepcopy')
        conf.get_mutable_obj('content.plugins')
        assert not spy.called

    def test_copy_mutable(self, conf, mocker):
        """Make sure mutable types are only copied once."""
        spy = mocker.spy(config.copy, 'deepcopy')
        conf.get_mutable_obj('bindings.commands')
        spy.assert_called_once_with(mocker.ANY)

    def test_get_obj_for_pattern(self, conf):
        pattern = urlmatch.UrlPattern('*://example.com')
        name = 'content.javascript.enabled'
        conf.set_obj(name, False, pattern=pattern)
        assert conf.get_obj_for_pattern(name, pattern=pattern) is False

    def test_get_obj_for_pattern_no_match(self, conf):
        pattern = urlmatch.UrlPattern('*://example.com')
        name = 'content.javascript.enabled'
        value = conf.get_obj_for_pattern(name, pattern=pattern)
        assert value is usertypes.UNSET

    def test_get_str(self, conf):
        assert conf.get_str('content.plugins') == 'false'

    @pytest.mark.parametrize('save_yaml', [True, False])
    @pytest.mark.parametrize('method, value', [
        ('set_obj', True),
        ('set_str', 'true'),
    ])
    def test_set_valid(self, conf, qtbot, yaml_value,
                       save_yaml, method, value):
        option = 'content.plugins'
        meth = getattr(conf, method)
        with qtbot.wait_signal(conf.changed):
            meth(option, value, save_yaml=save_yaml)
        assert conf.get_obj(option) is True
        if save_yaml:
            assert yaml_value(option) is True
        else:
            assert yaml_value(option) is usertypes.UNSET

    @pytest.mark.parametrize('method', ['set_obj', 'set_str'])
    def test_set_invalid(self, conf, qtbot, method):
        meth = getattr(conf, method)
        with pytest.raises(configexc.ValidationError):
            with qtbot.assert_not_emitted(conf.changed):
                meth('content.plugins', '42')
        assert not conf._values['content.plugins']

    @pytest.mark.parametrize('method', ['set_obj', 'set_str'])
    def test_set_wrong_backend(self, conf, qtbot, monkeypatch, method):
        monkeypatch.setattr(objects, 'backend', usertypes.Backend.QtWebEngine)
        meth = getattr(conf, method)
        with pytest.raises(configexc.BackendError):
            with qtbot.assert_not_emitted(conf.changed):
                meth('hints.find_implementation', 'javascript')
        assert not conf._values['hints.find_implementation']

    @pytest.mark.parametrize('method, value', [
        ('set_obj', {}),
        ('set_str', '{}'),
    ])
    def test_set_no_autoconfig_save(self, conf, qtbot, yaml_value,
                                    method, value):
        meth = getattr(conf, method)
        option = 'bindings.default'
        with pytest.raises(configexc.NoAutoconfigError):
            with qtbot.assert_not_emitted(conf.changed):
                meth(option, value, save_yaml=True)

        assert not conf._values[option]
        assert yaml_value(option) is usertypes.UNSET

    @pytest.mark.parametrize('method, value', [
        ('set_obj', {}),
        ('set_str', '{}'),
    ])
    def test_set_no_autoconfig_no_save(self, conf, qtbot, yaml_value,
                                       method, value):
        meth = getattr(conf, method)
        option = 'bindings.default'
        with qtbot.wait_signal(conf.changed):
            meth(option, value)

        assert conf._values[option]

    @pytest.mark.parametrize('method', ['set_obj', 'set_str'])
    def test_set_no_pattern(self, conf, method, qtbot):
        meth = getattr(conf, method)
        pattern = urlmatch.UrlPattern('https://www.example.com/')
        with pytest.raises(configexc.NoPatternError):
            with qtbot.assert_not_emitted(conf.changed):
                meth('colors.statusbar.normal.bg', '#abcdef', pattern=pattern)

    def test_dump_userconfig(self, conf):
        conf.set_obj('content.plugins', True)
        conf.set_obj('content.headers.custom', {'X-Foo': 'bar'})
        lines = ['content.headers.custom = {"X-Foo": "bar"}',
                 'content.plugins = true']
        assert conf.dump_userconfig().splitlines() == lines

    def test_dump_userconfig_default(self, conf):
        assert conf.dump_userconfig() == '<Default configuration>'

    @pytest.mark.parametrize('case', range(3))
    def test_get_str_benchmark(self, conf, qtbot, benchmark, case):
        strings = ['true',
                   ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML'
                    ', like Gecko) QtWebEngine/5.7.1 Chrome/49.0.2623.111 '
                    'Safari/537.36'),
                   "a" * 10000]
        conf.set_obj('content.headers.user_agent', strings[case])
        benchmark(functools.partial(conf.get, 'content.headers.user_agent'))

    def test_get_dict_benchmark(self, conf, qtbot, benchmark):
        benchmark(functools.partial(conf.get, 'bindings.default'))


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
        assert config_stub.get_obj('content.cookies.store') is False

    def test_confapi_errors(self, container):
        configapi = types.SimpleNamespace(errors=[])
        container._configapi = configapi
        container.tabs.foobar  # pylint: disable=pointless-statement

        assert len(configapi.errors) == 1
        error = configapi.errors[0]
        assert error.text == "While getting 'tabs.foobar'"
        assert str(error.exception) == "No option 'tabs.foobar'"

    def test_pattern_no_configapi(self, config_stub):
        pattern = urlmatch.UrlPattern('https://example.com/')
        with pytest.raises(TypeError,
                           match="Can't use pattern without configapi!"):
            config.ConfigContainer(config_stub, pattern=pattern)
