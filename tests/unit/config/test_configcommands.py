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

"""Tests for qutebrowser.config.configcommands."""

import logging
import unittest.mock

import pytest
from PyQt5.QtCore import QUrl, QProcess

from qutebrowser.config import configcommands
from qutebrowser.commands import cmdexc
from qutebrowser.utils import usertypes
from qutebrowser.misc import objects


@pytest.fixture
def commands(config_stub, key_config_stub):
    return configcommands.ConfigCommands(config_stub, key_config_stub)


class TestSet:

    """Tests for :set."""

    def test_set_no_args(self, commands, tabbed_browser_stubs):
        """Run ':set'.

        Should open qute://settings."""
        commands.set(win_id=0)
        assert tabbed_browser_stubs[0].opened_url == QUrl('qute://settings')

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
        ('editor.command',
         ['gvim', '-f', '{file}', '-c', 'normal {line}G{column0}l'],
         '[emacs, "{}"]', ['emacs', '{}']),
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
            assert option not in config_stub._yaml
        else:
            assert config_stub._yaml[option] == new_value

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
        assert config_stub._yaml['url.auto_search'] == 'dns'

    def test_set_print(self, config_stub, commands, message_mock):
        """Run ':set -p url.auto_search never'.

        Should set show the value.
        """
        assert config_stub.val.url.auto_search == 'naive'
        commands.set(0, 'url.auto_search', 'dns', print_=True)

        assert config_stub.val.url.auto_search == 'dns'
        msg = message_mock.getmsg(usertypes.MessageLevel.info)
        assert msg.text == 'url.auto_search = dns'

    def test_set_invalid_option(self, commands):
        """Run ':set foo bar'.

        Should show an error.
        """
        with pytest.raises(cmdexc.CommandError, match="No option 'foo'"):
            commands.set(0, 'foo', 'bar')

    def test_set_invalid_value(self, commands):
        """Run ':set auto_save.session blah'.

        Should show an error.
        """
        with pytest.raises(cmdexc.CommandError,
                           match="Invalid value 'blah' - must be a boolean!"):
            commands.set(0, 'auto_save.session', 'blah')

    def test_set_wrong_backend(self, commands, monkeypatch):
        monkeypatch.setattr(objects, 'backend', usertypes.Backend.QtWebEngine)
        with pytest.raises(cmdexc.CommandError,
                           match="The content.cookies.accept setting is not "
                           "available with the QtWebEngine backend!"):
            commands.set(0, 'content.cookies.accept', 'all')

    @pytest.mark.parametrize('option', ['?', 'url.auto_search'])
    def test_empty(self, commands, option):
        """Run ':set ?' / ':set url.auto_search'.

        Should show an error.
        See https://github.com/qutebrowser/qutebrowser/issues/1109
        """
        with pytest.raises(cmdexc.CommandError,
                           match="The following arguments are required: "
                                 "value"):
            commands.set(win_id=0, option=option)

    def test_toggle(self, commands):
        """Try toggling a value.

        Should show an nicer error.
        """
        with pytest.raises(cmdexc.CommandError,
                           match="Toggling values was moved to the "
                                 ":config-cycle command"):
            commands.set(win_id=0, option='javascript.enabled!')

    def test_invalid(self, commands):
        """Run ':set foo?'.

        Should show an error.
        """
        with pytest.raises(cmdexc.CommandError, match="No option 'foo'"):
            commands.set(win_id=0, option='foo?')


class TestCycle:

    """Test :config-cycle."""

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
        commands.config_cycle(opt, 'green', 'magenta', 'blue', 'yellow')
        assert config_stub.get(opt) == expected
        assert config_stub._yaml[opt] == expected

    def test_different_representation(self, commands, config_stub):
        """When using a different representation, cycling should work.

        For example, we use [foo] which is represented as ["foo"].
        """
        opt = 'qt.args'
        config_stub.set_obj(opt, ['foo'])
        commands.config_cycle(opt, '[foo]', '[bar]')
        assert config_stub.get(opt) == ['bar']
        commands.config_cycle(opt, '[foo]', '[bar]')
        assert config_stub.get(opt) == ['foo']

    def test_toggle(self, commands, config_stub):
        """Run ':config-cycle auto_save.session'.

        Should toggle the value.
        """
        assert not config_stub.val.auto_save.session
        commands.config_cycle('auto_save.session')
        assert config_stub.val.auto_save.session
        assert config_stub._yaml['auto_save.session']

    @pytest.mark.parametrize('args', [
        ['url.auto_search'], ['url.auto_search', 'foo']
    ])
    def test_toggle_nonbool(self, commands, config_stub, args):
        """Run :config-cycle without a bool and 0/1 value.

        :config-cycle url.auto_search
        :config-cycle url.auto_search foo

        Should show an error.
        """
        assert config_stub.val.url.auto_search == 'naive'
        with pytest.raises(cmdexc.CommandError, match="Need at least "
                           "two values for non-boolean settings."):
            commands.config_cycle(*args)
        assert config_stub.val.url.auto_search == 'naive'

    def test_set_toggle_print(self, commands, config_stub, message_mock):
        """Run ':config-cycle -p auto_save.session'.

        Should toggle the value and show the new value.
        """
        commands.config_cycle('auto_save.session', print_=True)
        msg = message_mock.getmsg(usertypes.MessageLevel.info)
        assert msg.text == 'auto_save.session = true'


class TestUnsetAndClear:

    """Test :config-unset and :config-clear."""

    @pytest.mark.parametrize('temp', [True, False])
    def test_unset(self, commands, config_stub, temp):
        name = 'tabs.show'
        config_stub.set_obj(name, 'never', save_yaml=True)

        commands.config_unset(name, temp=temp)

        assert config_stub.get(name) == 'always'
        if temp:
            assert config_stub._yaml[name] == 'never'
        else:
            assert name not in config_stub._yaml

    def test_unset_unknown_option(self, commands):
        with pytest.raises(cmdexc.CommandError, match="No option 'tabs'"):
            commands.config_unset('tabs')

    @pytest.mark.parametrize('save', [True, False])
    def test_clear(self, commands, config_stub, save):
        name = 'tabs.show'
        config_stub.set_obj(name, 'never', save_yaml=True)

        commands.config_clear(save=save)

        assert config_stub.get(name) == 'always'
        if save:
            assert name not in config_stub._yaml
        else:
            assert config_stub._yaml[name] == 'never'


class TestSource:

    """Test :config-source."""

    pytestmark = pytest.mark.usefixtures('config_tmpdir', 'data_tmpdir',
                                         'config_stub', 'key_config_stub')

    @pytest.mark.parametrize('use_default_dir', [True, False])
    @pytest.mark.parametrize('clear', [True, False])
    def test_config_source(self, tmpdir, commands, config_stub, config_tmpdir,
                           use_default_dir, clear):
        assert config_stub.val.content.javascript.enabled
        config_stub.val.search.ignore_case = 'always'

        if use_default_dir:
            pyfile = config_tmpdir / 'config.py'
            arg = None
        else:
            pyfile = tmpdir / 'sourced.py'
            arg = str(pyfile)
        pyfile.write_text('c.content.javascript.enabled = False\n',
                          encoding='utf-8')

        commands.config_source(arg, clear=clear)

        assert not config_stub.val.content.javascript.enabled
        ignore_case = config_stub.val.search.ignore_case
        assert ignore_case == ('smart' if clear else 'always')

    def test_errors(self, commands, config_tmpdir):
        pyfile = config_tmpdir / 'config.py'
        pyfile.write_text('c.foo = 42', encoding='utf-8')

        with pytest.raises(cmdexc.CommandError) as excinfo:
            commands.config_source()

        expected = ("Errors occurred while reading config.py:\n"
                    "  While setting 'foo': No option 'foo'")
        assert str(excinfo.value) == expected


class TestEdit:

    """Tests for :config-edit."""

    pytestmark = pytest.mark.usefixtures('config_tmpdir', 'data_tmpdir',
                                         'config_stub', 'key_config_stub')

    def test_no_source(self, commands, mocker):
        mock = mocker.patch('qutebrowser.config.configcommands.editor.'
                            'ExternalEditor._start_editor', autospec=True)
        commands.config_edit(no_source=True)
        mock.assert_called_once_with(unittest.mock.ANY)

    @pytest.fixture
    def patch_editor(self, mocker):
        """Write a config.py file."""
        def do_patch(text):
            def _write_file(editor_self):
                with open(editor_self._filename, 'w', encoding='utf-8') as f:
                    f.write(text)
                editor_self.on_proc_closed(0, QProcess.NormalExit)

            return mocker.patch('qutebrowser.config.configcommands.editor.'
                                'ExternalEditor._start_editor', autospec=True,
                                side_effect=_write_file)

        return do_patch

    def test_with_sourcing(self, commands, config_stub, patch_editor):
        assert config_stub.val.content.javascript.enabled
        mock = patch_editor('c.content.javascript.enabled = False')

        commands.config_edit()

        mock.assert_called_once_with(unittest.mock.ANY)
        assert not config_stub.val.content.javascript.enabled

    def test_error(self, commands, config_stub, patch_editor, message_mock,
                   caplog):
        patch_editor('c.foo = 42')

        with caplog.at_level(logging.ERROR):
            commands.config_edit()

        msg = message_mock.getmsg()
        expected = ("Errors occurred while reading config.py:\n"
                    "  While setting 'foo': No option 'foo'")
        assert msg.text == expected


class TestWritePy:

    """Tests for :config-write-py."""

    def test_custom(self, commands, config_stub, key_config_stub, tmpdir):
        confpy = tmpdir / 'config.py'
        config_stub.val.content.javascript.enabled = True
        key_config_stub.bind(',x', 'message-info foo', mode='normal')

        commands.config_write_py(str(confpy))

        lines = confpy.read_text('utf-8').splitlines()
        assert "c.content.javascript.enabled = True" in lines
        assert "config.bind(',x', 'message-info foo')" in lines

    def test_defaults(self, commands, tmpdir):
        confpy = tmpdir / 'config.py'
        commands.config_write_py(str(confpy), defaults=True)

        lines = confpy.read_text('utf-8').splitlines()
        assert "# c.content.javascript.enabled = True" in lines
        assert "# config.bind('H', 'back')" in lines

    def test_default_location(self, commands, config_tmpdir):
        confpy = config_tmpdir / 'config.py'
        commands.config_write_py()
        lines = confpy.read_text('utf-8').splitlines()
        assert '# Autogenerated config.py' in lines

    def test_relative_path(self, commands, config_tmpdir):
        confpy = config_tmpdir / 'config2.py'
        commands.config_write_py('config2.py')
        lines = confpy.read_text('utf-8').splitlines()
        assert '# Autogenerated config.py' in lines

    def test_existing_file(self, commands, tmpdir):
        confpy = tmpdir / 'config.py'
        confpy.ensure()

        with pytest.raises(cmdexc.CommandError) as excinfo:
            commands.config_write_py(str(confpy))

        expected = " already exists - use --force to overwrite!"
        assert str(excinfo.value).endswith(expected)

    def test_existing_file_force(self, commands, tmpdir):
        confpy = tmpdir / 'config.py'
        confpy.ensure()

        commands.config_write_py(str(confpy), force=True)

        lines = confpy.read_text('utf-8').splitlines()
        assert '# Autogenerated config.py' in lines

    def test_oserror(self, commands, tmpdir):
        """Test writing to a directory which does not exist."""
        with pytest.raises(cmdexc.CommandError):
            commands.config_write_py(str(tmpdir / 'foo' / 'config.py'))


class TestBind:

    """Tests for :bind and :unbind."""

    @pytest.fixture
    def no_bindings(self):
        """Get a dict with no bindings."""
        return {'normal': {}}

    @pytest.mark.parametrize('command', ['nop', 'nope'])
    def test_bind(self, commands, config_stub, no_bindings, key_config_stub,
                  command):
        """Simple :bind test (and aliases)."""
        config_stub.val.aliases = {'nope': 'nop'}
        config_stub.val.bindings.default = no_bindings
        config_stub.val.bindings.commands = no_bindings

        commands.bind('a', command)
        assert key_config_stub.get_command('a', 'normal') == command
        yaml_bindings = config_stub._yaml['bindings.commands']['normal']
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

    def test_bind_invalid_mode(self, commands):
        """Run ':bind --mode=wrongmode a nop'.

        Should show an error.
        """
        with pytest.raises(cmdexc.CommandError,
                           match='Invalid mode wrongmode!'):
            commands.bind('a', 'nop', mode='wrongmode')

    def test_bind_print_invalid_mode(self, commands):
        """Run ':bind --mode=wrongmode a'.

        Should show an error.
        """
        with pytest.raises(cmdexc.CommandError,
                           match='Invalid mode wrongmode!'):
            commands.bind('a', mode='wrongmode')

    @pytest.mark.parametrize('key', ['a', 'b', '<Ctrl-X>'])
    def test_bind_duplicate(self, commands, config_stub, key_config_stub, key):
        """Run ':bind' with a key which already has been bound.'.

        Also tests for https://github.com/qutebrowser/qutebrowser/issues/1544
        """
        config_stub.val.bindings.default = {
            'normal': {'a': 'nop', '<Ctrl+x>': 'nop'}
        }
        config_stub.val.bindings.commands = {
            'normal': {'b': 'nop'},
        }

        commands.bind(key, 'message-info foo', mode='normal')
        assert key_config_stub.get_command(key, 'normal') == 'message-info foo'

    def test_bind_none(self, commands, config_stub):
        config_stub.val.bindings.commands = None
        commands.bind(',x', 'nop')

    def test_bind_default(self, commands, key_config_stub, config_stub):
        """Bind a key to its default."""
        default_cmd = 'message-info default'
        bound_cmd = 'message-info bound'
        config_stub.val.bindings.default = {'normal': {'a': default_cmd}}
        config_stub.val.bindings.commands = {'normal': {'a': bound_cmd}}
        assert key_config_stub.get_command('a', mode='normal') == bound_cmd

        commands.bind('a', mode='normal', default=True)

        assert key_config_stub.get_command('a', mode='normal') == default_cmd

    @pytest.mark.parametrize('key, mode, expected', [
        ('foobar', 'normal', "Can't find binding 'foobar' in normal mode"),
        ('x', 'wrongmode', "Invalid mode wrongmode!"),
    ])
    def test_bind_default_invalid(self, commands, key, mode, expected):
        """Run ':bind --default foobar' / ':bind --default x wrongmode'.

        Should show an error.
        """
        with pytest.raises(cmdexc.CommandError, match=expected):
            commands.bind(key, mode=mode, default=True)

    def test_unbind_none(self, commands, config_stub):
        config_stub.val.bindings.commands = None
        commands.unbind('H')

    @pytest.mark.parametrize('key, normalized', [
        ('a', 'a'),  # default bindings
        ('b', 'b'),  # custom bindings
        ('c', 'c'),  # :bind then :unbind
        ('<Ctrl-X>', '<ctrl+x>')  # normalized special binding
    ])
    def test_unbind(self, commands, key_config_stub, config_stub,
                    key, normalized):
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
        assert key_config_stub.get_command(key, 'normal') is None

        yaml_bindings = config_stub._yaml['bindings.commands']['normal']
        if key in 'bc':
            # Custom binding
            assert normalized not in yaml_bindings
        else:
            assert yaml_bindings[normalized] is None

    @pytest.mark.parametrize('key, mode, expected', [
        ('foobar', 'normal', "Can't find binding 'foobar' in normal mode"),
        ('x', 'wrongmode', "Invalid mode wrongmode!"),
    ])
    def test_unbind_invalid(self, commands, key, mode, expected):
        """Run ':unbind foobar' / ':unbind x wrongmode'.

        Should show an error.
        """
        with pytest.raises(cmdexc.CommandError, match=expected):
            commands.unbind(key, mode=mode)
