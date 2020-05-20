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

"""Tests for qutebrowser.config.configcommands."""

import logging
import functools
import unittest.mock

import pytest
from PyQt5.QtCore import QUrl

from qutebrowser.config import configcommands
from qutebrowser.api import cmdutils
from qutebrowser.utils import usertypes, urlmatch
from qutebrowser.keyinput import keyutils
from qutebrowser.misc import objects


# Alias because we need this a lot in here.
def keyseq(s):
    return keyutils.KeySequence.parse(s)


@pytest.fixture
def commands(config_stub, key_config_stub):
    return configcommands.ConfigCommands(config_stub, key_config_stub)


@pytest.fixture
def yaml_value(config_stub):
    """Fixture which provides a getter for a YAML value."""
    def getter(option):
        return config_stub._yaml._values[option].get_for_url(fallback=False)
    return getter


class TestSet:

    """Tests for :set."""

    def test_set_no_args(self, commands, tabbed_browser_stubs):
        """Run ':set'.

        Should open qute://settings."""
        commands.set(win_id=0)
        assert tabbed_browser_stubs[0].loaded_url == QUrl('qute://settings')

    @pytest.mark.parametrize('option', ['url.auto_search?', 'url.auto_search'])
    def test_get(self, config_stub, commands, message_mock, option):
        """Run ':set url.auto_search?' / ':set url.auto_search'.

        Should show the value.
        """
        config_stub.val.url.auto_search = 'never'
        commands.set(win_id=0, option=option)
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
    def test_set_simple(self, monkeypatch, commands, config_stub, yaml_value,
                        temp, option, old_value, inp, new_value):
        """Run ':set [-t] option value'.

        Should set the setting accordingly.
        """
        monkeypatch.setattr(objects, 'backend', usertypes.Backend.QtWebKit)
        assert config_stub.get(option) == old_value

        commands.set(0, option, inp, temp=temp)

        assert config_stub.get(option) == new_value
        assert yaml_value(option) == (usertypes.UNSET if temp else new_value)

    def test_set_with_pattern(self, monkeypatch, commands, config_stub):
        monkeypatch.setattr(objects, 'backend', usertypes.Backend.QtWebKit)
        option = 'content.javascript.enabled'

        commands.set(0, option, 'false', pattern='*://example.com')
        pattern = urlmatch.UrlPattern('*://example.com')

        assert config_stub.get(option)
        assert not config_stub.get_obj_for_pattern(option, pattern=pattern)

    def test_set_invalid_pattern(self, monkeypatch, commands):
        monkeypatch.setattr(objects, 'backend', usertypes.Backend.QtWebKit)
        option = 'content.javascript.enabled'

        with pytest.raises(cmdutils.CommandError,
                           match=('Error while parsing http://: Pattern '
                                  'without host')):
            commands.set(0, option, 'false', pattern='http://')

    def test_set_no_pattern(self, monkeypatch, commands):
        """Run ':set --pattern=*://* colors.statusbar.normal.bg #abcdef.

        Should show an error as patterns are unsupported.
        """
        with pytest.raises(cmdutils.CommandError,
                           match='does not support URL patterns'):
            commands.set(0, 'colors.statusbar.normal.bg', '#abcdef',
                         pattern='*://*')

    @pytest.mark.parametrize('temp', [True, False])
    def test_set_temp_override(self, commands, config_stub, yaml_value, temp):
        """Invoking :set twice.

        :set url.auto_search dns
        :set -t url.auto_search never

        Should set the setting accordingly.
        """
        assert config_stub.val.url.auto_search == 'naive'
        commands.set(0, 'url.auto_search', 'dns')
        commands.set(0, 'url.auto_search', 'never', temp=True)

        assert config_stub.val.url.auto_search == 'never'
        assert yaml_value('url.auto_search') == 'dns'

    @pytest.mark.parametrize('pattern', [None, '*://example.com'])
    def test_set_print(self, config_stub, commands, message_mock, pattern):
        """Run ':set -p [-u *://example.com] content.javascript.enabled false'.

        Should set show the value.
        """
        assert config_stub.val.content.javascript.enabled
        commands.set(0, 'content.javascript.enabled', 'false', print_=True,
                     pattern=pattern)

        value = config_stub.get_obj_for_pattern(
            'content.javascript.enabled',
            pattern=None if pattern is None else urlmatch.UrlPattern(pattern))
        assert not value

        expected = 'content.javascript.enabled = false'
        if pattern is not None:
            expected += ' for {}'.format(pattern)
        msg = message_mock.getmsg(usertypes.MessageLevel.info)
        assert msg.text == expected

    def test_set_invalid_option(self, commands):
        """Run ':set foo bar'.

        Should show an error.
        """
        with pytest.raises(cmdutils.CommandError, match="No option 'foo'"):
            commands.set(0, 'foo', 'bar')

    def test_set_invalid_value(self, commands):
        """Run ':set auto_save.session blah'.

        Should show an error.
        """
        with pytest.raises(cmdutils.CommandError,
                           match="Invalid value 'blah' - must be a boolean!"):
            commands.set(0, 'auto_save.session', 'blah')

    def test_set_wrong_backend(self, commands, monkeypatch):
        monkeypatch.setattr(objects, 'backend', usertypes.Backend.QtWebEngine)
        with pytest.raises(cmdutils.CommandError,
                           match="The hints.find_implementation setting is "
                           "not available with the QtWebEngine backend!"):
            commands.set(0, 'hints.find_implementation', 'javascript')

    def test_empty(self, commands):
        """Run ':set ?'.

        Should show an error.
        See https://github.com/qutebrowser/qutebrowser/issues/1109
        """
        with pytest.raises(cmdutils.CommandError, match="No option '?'"):
            commands.set(win_id=0, option='?')

    def test_toggle(self, commands):
        """Try toggling a value.

        Should show an nicer error.
        """
        with pytest.raises(cmdutils.CommandError,
                           match="Toggling values was moved to the "
                                 ":config-cycle command"):
            commands.set(win_id=0, option='javascript.enabled!')

    def test_invalid(self, commands):
        """Run ':set foo?'.

        Should show an error.
        """
        with pytest.raises(cmdutils.CommandError, match="No option 'foo'"):
            commands.set(win_id=0, option='foo?')


@pytest.mark.parametrize('old', [True, False])
def test_diff(commands, tabbed_browser_stubs, old):
    """Run ':config-diff'.

    Should open qute://configdiff."""
    commands.config_diff(win_id=0, old=old)
    url = QUrl('qute://configdiff/old') if old else QUrl('qute://configdiff')
    assert tabbed_browser_stubs[0].loaded_url == url


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
    def test_cycling(self, commands, config_stub, yaml_value,
                     initial, expected):
        """Run ':set' with multiple values."""
        opt = 'colors.statusbar.normal.bg'
        config_stub.set_obj(opt, initial)
        commands.config_cycle(opt, 'green', 'magenta', 'blue', 'yellow')
        assert config_stub.get(opt) == expected
        assert yaml_value(opt) == expected

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

    def test_toggle(self, commands, config_stub, yaml_value):
        """Run ':config-cycle auto_save.session'.

        Should toggle the value.
        """
        assert not config_stub.val.auto_save.session
        commands.config_cycle('auto_save.session')
        assert config_stub.val.auto_save.session
        assert yaml_value('auto_save.session')

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
        with pytest.raises(cmdutils.CommandError, match="Need at least "
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


class TestAdd:

    """Test :config-list-add and :config-dict-add."""

    @pytest.mark.parametrize('temp', [True, False])
    @pytest.mark.parametrize('value', ['test1', 'test2'])
    def test_list_add(self, commands, config_stub, yaml_value, temp, value):
        name = 'content.host_blocking.whitelist'

        commands.config_list_add(name, value, temp=temp)

        assert str(config_stub.get(name)[-1]) == value
        if temp:
            assert yaml_value(name) == usertypes.UNSET
        else:
            assert yaml_value(name)[-1] == value

    def test_list_add_invalid_option(self, commands):
        with pytest.raises(
                cmdutils.CommandError,
                match="No option 'nonexistent'"):
            commands.config_list_add('nonexistent', 'value')

    def test_list_add_non_list(self, commands):
        with pytest.raises(
                cmdutils.CommandError,
                match=":config-list-add can only be used for lists"):
            commands.config_list_add('history_gap_interval', 'value')

    @pytest.mark.parametrize('value', ['', None, 42])
    def test_list_add_invalid_values(self, commands, value):
        with pytest.raises(
                cmdutils.CommandError,
                match="Invalid value '{}'".format(value)):
            commands.config_list_add('content.host_blocking.whitelist', value)

    @pytest.mark.parametrize('value', ['test1', 'test2'])
    @pytest.mark.parametrize('temp', [True, False])
    def test_dict_add(self, commands, config_stub, yaml_value, value, temp):
        name = 'aliases'
        key = 'missingkey'

        commands.config_dict_add(name, key, value, temp=temp)

        assert str(config_stub.get(name)[key]) == value
        if temp:
            assert yaml_value(name) == usertypes.UNSET
        else:
            assert yaml_value(name)[key] == value

    @pytest.mark.parametrize('replace', [True, False])
    def test_dict_add_replace(self, commands, config_stub, replace):
        name = 'aliases'
        key = 'w'
        value = 'anything'

        if replace:
            commands.config_dict_add(name, key, value, replace=True)
            assert str(config_stub.get(name)[key]) == value
        else:
            with pytest.raises(
                    cmdutils.CommandError,
                    match="w already exists in aliases - use --replace to "
                          "overwrite!"):
                commands.config_dict_add(name, key, value, replace=False)

    def test_dict_add_invalid_option(self, commands):
        with pytest.raises(
                cmdutils.CommandError,
                match="No option 'nonexistent'"):
            commands.config_dict_add('nonexistent', 'key', 'value')

    def test_dict_add_non_dict(self, commands):
        with pytest.raises(
                cmdutils.CommandError,
                match=":config-dict-add can only be used for dicts"):
            commands.config_dict_add('history_gap_interval', 'key', 'value')

    @pytest.mark.parametrize('value', ['', None, 42])
    def test_dict_add_invalid_values(self, commands, value):
        with pytest.raises(cmdutils.CommandError,
                           match="Invalid value '{}'".format(value)):
            commands.config_dict_add('aliases', 'missingkey', value)


class TestRemove:

    """Test :config-list-remove and :config-dict-remove."""

    @pytest.mark.parametrize('value', ['25%', '50%'])
    @pytest.mark.parametrize('temp', [True, False])
    def test_list_remove(self, commands, config_stub, yaml_value, value, temp):
        name = 'zoom.levels'
        commands.config_list_remove(name, value, temp=temp)

        assert value not in config_stub.get(name)
        if temp:
            assert yaml_value(name) == usertypes.UNSET
        else:
            assert value not in yaml_value(name)

    def test_list_remove_invalid_option(self, commands):
        with pytest.raises(
                cmdutils.CommandError,
                match="No option 'nonexistent'"):
            commands.config_list_remove('nonexistent', 'value')

    def test_list_remove_non_list(self, commands):
        with pytest.raises(
                cmdutils.CommandError,
                match=":config-list-remove can only be used for lists"):
            commands.config_list_remove('content.javascript.enabled',
                                        'never')

    def test_list_remove_no_value(self, commands):
        with pytest.raises(
                cmdutils.CommandError,
                match="never is not in colors.completion.fg!"):
            commands.config_list_remove('colors.completion.fg', 'never')

    @pytest.mark.parametrize('key', ['w', 'q'])
    @pytest.mark.parametrize('temp', [True, False])
    def test_dict_remove(self, commands, config_stub, yaml_value, key, temp):
        name = 'aliases'
        commands.config_dict_remove(name, key, temp=temp)

        assert key not in config_stub.get(name)
        if temp:
            assert yaml_value(name) == usertypes.UNSET
        else:
            assert key not in yaml_value(name)

    def test_dict_remove_invalid_option(self, commands):
        with pytest.raises(
                cmdutils.CommandError,
                match="No option 'nonexistent'"):
            commands.config_dict_remove('nonexistent', 'key')

    def test_dict_remove_non_dict(self, commands):
        with pytest.raises(
                cmdutils.CommandError,
                match=":config-dict-remove can only be used for dicts"):
            commands.config_dict_remove('content.javascript.enabled',
                                        'never')

    def test_dict_remove_no_value(self, commands):
        with pytest.raises(
                cmdutils.CommandError,
                match="never is not in aliases!"):
            commands.config_dict_remove('aliases', 'never')


class TestUnsetAndClear:

    """Test :config-unset and :config-clear."""

    @pytest.mark.parametrize('temp', [True, False])
    def test_unset(self, commands, config_stub, yaml_value, temp):
        name = 'tabs.show'
        config_stub.set_obj(name, 'never', save_yaml=True)

        commands.config_unset(name, temp=temp)

        assert config_stub.get(name) == 'always'
        assert yaml_value(name) == ('never' if temp else usertypes.UNSET)

    def test_unset_unknown_option(self, commands):
        with pytest.raises(cmdutils.CommandError, match="No option 'tabs'"):
            commands.config_unset('tabs')

    @pytest.mark.parametrize('save', [True, False])
    def test_clear(self, commands, config_stub, yaml_value, save):
        name = 'tabs.show'
        config_stub.set_obj(name, 'never', save_yaml=True)

        commands.config_clear(save=save)

        assert config_stub.get(name) == 'always'
        assert yaml_value(name) == (usertypes.UNSET if save else 'never')


class TestSource:

    """Test :config-source."""

    pytestmark = pytest.mark.usefixtures('config_tmpdir', 'data_tmpdir',
                                         'config_stub', 'key_config_stub')

    @pytest.mark.parametrize('location', ['default', 'absolute', 'relative'])
    @pytest.mark.parametrize('clear', [True, False])
    def test_config_source(self, tmpdir, commands, config_stub, config_tmpdir,
                           location, clear):
        assert config_stub.val.content.javascript.enabled
        config_stub.val.search.ignore_case = 'always'

        if location == 'default':
            pyfile = config_tmpdir / 'config.py'
            arg = None
        elif location == 'absolute':
            pyfile = tmpdir / 'sourced.py'
            arg = str(pyfile)
        elif location == 'relative':
            pyfile = config_tmpdir / 'sourced.py'
            arg = 'sourced.py'
        else:
            assert False, location

        pyfile.write_text('c.content.javascript.enabled = False\n',
                          encoding='utf-8')

        commands.config_source(arg, clear=clear)

        assert not config_stub.val.content.javascript.enabled
        ignore_case = config_stub.val.search.ignore_case
        assert ignore_case == (usertypes.IgnoreCase.smart if clear
                               else usertypes.IgnoreCase.always)

    def test_config_py_arg_source(self, commands, config_py_arg, config_stub):
        assert config_stub.val.content.javascript.enabled
        config_py_arg.write_text('c.content.javascript.enabled = False\n',
                                 encoding='utf-8')
        commands.config_source()
        assert not config_stub.val.content.javascript.enabled

    def test_errors(self, commands, config_tmpdir):
        pyfile = config_tmpdir / 'config.py'
        pyfile.write_text('c.foo = 42', encoding='utf-8')

        with pytest.raises(cmdutils.CommandError) as excinfo:
            commands.config_source()

        expected = ("Errors occurred while reading config.py:\n"
                    "  While setting 'foo': No option 'foo'")
        assert str(excinfo.value) == expected

    def test_invalid_source(self, commands, config_tmpdir):
        pyfile = config_tmpdir / 'config.py'
        pyfile.write_text('1/0', encoding='utf-8')

        with pytest.raises(cmdutils.CommandError) as excinfo:
            commands.config_source()

        expected = ("Errors occurred while reading config.py:\n"
                    "  Unhandled exception - ZeroDivisionError:"
                    " division by zero")
        assert str(excinfo.value) == expected


class TestEdit:

    """Tests for :config-edit."""

    pytestmark = pytest.mark.usefixtures('config_tmpdir', 'data_tmpdir',
                                         'config_stub', 'key_config_stub',
                                         'qapp')

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
                editor_self.file_updated.emit(text)

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

    def test_config_py_with_sourcing(self, commands, config_stub, patch_editor, config_py_arg):
        assert config_stub.val.content.javascript.enabled
        conf = 'c.content.javascript.enabled = False'
        mock = patch_editor(conf)
        commands.config_edit()
        mock.assert_called_once_with(unittest.mock.ANY)
        assert not config_stub.val.content.javascript.enabled
        assert config_py_arg.read_text('utf-8').splitlines() == [conf]

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
        key_config_stub.bind(keyseq(',x'), 'message-info foo', mode='normal')

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

        with pytest.raises(cmdutils.CommandError) as excinfo:
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
        with pytest.raises(cmdutils.CommandError):
            commands.config_write_py(str(tmpdir / 'foo' / 'config.py'))

    def test_config_py_arg(self, commands, config_py_arg):
        config_py_arg.ensure()
        commands.config_write_py(str(config_py_arg), force=True)
        lines = config_py_arg.read_text('utf-8').splitlines()
        assert '# Autogenerated config.py' in lines


class TestBind:

    """Tests for :bind and :unbind."""

    @pytest.fixture
    def no_bindings(self):
        """Get a dict with no bindings."""
        return {'normal': {}}

    def test_bind_no_args(self, commands, config_stub, no_bindings,
                          tabbed_browser_stubs):
        """Run ':bind'.

        Should open qute://bindings."""
        config_stub.val.bindings.default = no_bindings
        config_stub.val.bindings.commands = no_bindings
        commands.bind(win_id=0)
        assert tabbed_browser_stubs[0].loaded_url == QUrl('qute://bindings')

    @pytest.mark.parametrize('command', ['nop', 'nope'])
    def test_bind(self, commands, config_stub, no_bindings, key_config_stub,
                  yaml_value, command):
        """Simple :bind test (and aliases)."""
        config_stub.val.aliases = {'nope': 'nop'}
        config_stub.val.bindings.default = no_bindings
        config_stub.val.bindings.commands = no_bindings

        commands.bind(0, 'a', command)
        assert key_config_stub.get_command(keyseq('a'), 'normal') == command
        yaml_bindings = yaml_value('bindings.commands')['normal']
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
         "<Ctrl+x> is bound to 'message-info C-x' in normal mode"),
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

        commands.bind(0, key, mode=mode)

        msg = message_mock.getmsg(usertypes.MessageLevel.info)
        assert msg.text == expected

    @pytest.mark.parametrize('command, args, kwargs, expected', [
        # :bind --mode=wrongmode a nop
        ('bind', ['a', 'nop'], {'mode': 'wrongmode'},
         'Invalid mode wrongmode!'),
        # :bind --mode=wrongmode a
        ('bind', ['a'], {'mode': 'wrongmode'},
         'Invalid mode wrongmode!'),
        # :bind --default --mode=wrongmode a
        ('bind', ['a'], {'mode': 'wrongmode', 'default': True},
         'Invalid mode wrongmode!'),
        # :bind --default foobar
        ('bind', ['foobar'], {'default': True},
         "Can't find binding 'foobar' in normal mode"),
        # :bind <blub> nop
        ('bind', ['<blub>', 'nop'], {},
         "Could not parse '<blub>': Got invalid key!"),
        # :unbind foobar
        ('unbind', ['foobar'], {},
         "Can't find binding 'foobar' in normal mode"),
        # :unbind --mode=wrongmode x
        ('unbind', ['x'], {'mode': 'wrongmode'},
         'Invalid mode wrongmode!'),
        # :unbind <blub>
        ('unbind', ['<blub>'], {},
         "Could not parse '<blub>': Got invalid key!"),
    ])
    def test_bind_invalid(self, commands,
                          command, args, kwargs, expected):
        """Run various wrong :bind/:unbind invocations.

        Should show an error.
        """
        if command == 'bind':
            func = functools.partial(commands.bind, 0)
        elif command == 'unbind':
            func = commands.unbind

        with pytest.raises(cmdutils.CommandError, match=expected):
            func(*args, **kwargs)

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

        commands.bind(0, key, 'message-info foo', mode='normal')
        command = key_config_stub.get_command(keyseq(key), 'normal')
        assert command == 'message-info foo'

    def test_bind_none(self, commands, config_stub):
        config_stub.val.bindings.commands = None
        commands.bind(0, ',x', 'nop')

    def test_bind_default(self, commands, key_config_stub, config_stub):
        """Bind a key to its default."""
        default_cmd = 'message-info default'
        bound_cmd = 'message-info bound'
        config_stub.val.bindings.default = {'normal': {'a': default_cmd}}
        config_stub.val.bindings.commands = {'normal': {'a': bound_cmd}}
        command = key_config_stub.get_command(keyseq('a'), mode='normal')
        assert command == bound_cmd

        commands.bind(0, 'a', mode='normal', default=True)

        command = key_config_stub.get_command(keyseq('a'), mode='normal')
        assert command == default_cmd

    def test_unbind_none(self, commands, config_stub):
        config_stub.val.bindings.commands = None
        commands.unbind('H')

    @pytest.mark.parametrize('key, normalized', [
        ('a', 'a'),  # default bindings
        ('b', 'b'),  # custom bindings
        ('c', 'c'),  # :bind then :unbind
        ('<Ctrl-X>', '<Ctrl+x>')  # normalized special binding
    ])
    def test_unbind(self, commands, key_config_stub, config_stub, yaml_value,
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
            commands.bind(0, key, 'nop')

        commands.unbind(key)
        assert key_config_stub.get_command(keyseq(key), 'normal') is None

        yaml_bindings = yaml_value('bindings.commands')['normal']
        if key in 'bc':
            # Custom binding
            assert normalized not in yaml_bindings
        else:
            assert yaml_bindings[normalized] is None
