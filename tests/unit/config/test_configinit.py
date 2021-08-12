# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# Copyright 2017-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Tests for qutebrowser.config.configinit."""

import builtins
import logging
import unittest.mock

import pytest

from qutebrowser.config import (config, configexc, configfiles, configinit,
                                configdata, configtypes)
from qutebrowser.utils import objreg, usertypes


@pytest.fixture
def init_patch(qapp, fake_save_manager, monkeypatch, config_tmpdir,
               data_tmpdir):
    monkeypatch.setattr(configfiles, 'state', None)
    monkeypatch.setattr(config, 'instance', None)
    monkeypatch.setattr(config, 'key_instance', None)
    monkeypatch.setattr(config, 'change_filters', [])
    monkeypatch.setattr(configinit, '_init_errors', None)
    monkeypatch.setattr(configtypes.FontBase, 'default_family', None)
    monkeypatch.setattr(configtypes.FontBase, 'default_size', None)
    yield
    try:
        objreg.delete('config-commands')
    except KeyError:
        pass


@pytest.fixture
def args(fake_args):
    """Arguments needed for the config to init."""
    fake_args.temp_settings = []
    fake_args.config_py = None
    return fake_args


@pytest.fixture(autouse=True)
def configdata_init(monkeypatch):
    """Make sure configdata is init'ed and no test re-init's it."""
    if not configdata.DATA:
        configdata.init()
    monkeypatch.setattr(configdata, 'init', lambda: None)


class TestEarlyInit:

    def test_config_py_path(self, args, init_patch, config_py_arg):
        config_py_arg.write('\n'.join(['config.load_autoconfig()',
                                       'c.colors.hints.bg = "red"']))
        configinit.early_init(args)
        expected = 'colors.hints.bg = red'
        assert config.instance.dump_userconfig() == expected

    @pytest.mark.parametrize('config_py', [True, 'error', False])
    def test_config_py(self, init_patch, config_tmpdir, caplog, args,
                       config_py):
        """Test loading with only a config.py."""
        config_py_file = config_tmpdir / 'config.py'

        if config_py:
            config_py_lines = ['c.colors.hints.bg = "red"',
                               'config.load_autoconfig(False)']
            if config_py == 'error':
                config_py_lines.append('c.foo = 42')
            config_py_file.write_text('\n'.join(config_py_lines),
                                      'utf-8', ensure=True)

        with caplog.at_level(logging.ERROR):
            configinit.early_init(args)

        # Check error messages
        expected_errors = []
        if config_py == 'error':
            expected_errors.append("While setting 'foo': No option 'foo'")

        if configinit._init_errors is None:
            actual_errors = []
        else:
            actual_errors = [str(err)
                             for err in configinit._init_errors.errors]

        assert actual_errors == expected_errors

        # Make sure things have been init'ed
        assert isinstance(config.instance, config.Config)
        assert isinstance(config.key_instance, config.KeyConfig)

        # Check config values
        if config_py:
            expected = 'colors.hints.bg = red'
        else:
            expected = '<Default configuration>'
        assert config.instance.dump_userconfig() == expected

    @pytest.mark.parametrize('load_autoconfig', [True, False])
    @pytest.mark.parametrize('config_py', [True, 'error', False])
    @pytest.mark.parametrize('invalid_yaml', ['42', 'list', 'unknown',
                                              'wrong-type', False])
    def test_autoconfig_yml(self, init_patch, config_tmpdir,  # noqa: C901
                            caplog, args,
                            load_autoconfig, config_py, invalid_yaml):
        """Test interaction between config.py and autoconfig.yml."""
        # Prepare files
        autoconfig_file = config_tmpdir / 'autoconfig.yml'
        config_py_file = config_tmpdir / 'config.py'

        yaml_lines = {
            '42': '42',
            'list': '[1, 2]',
            'unknown': [
                'settings:',
                '  colors.foobar:',
                '    global: magenta',
                'config_version: 2',
            ],
            'wrong-type': [
                'settings:',
                '  tabs.position:',
                '    global: true',
                'config_version: 2',
            ],
            False: [
                'settings:',
                '  colors.hints.fg:',
                '    global: magenta',
                'config_version: 2',
            ],
        }
        text = '\n'.join(yaml_lines[invalid_yaml])
        autoconfig_file.write_text(text, 'utf-8', ensure=True)

        if config_py:
            config_py_lines = ['c.colors.hints.bg = "red"']
            config_py_lines.append('config.load_autoconfig({})'.format(load_autoconfig))
            if config_py == 'error':
                config_py_lines.append('c.foo = 42')
            config_py_file.write_text('\n'.join(config_py_lines),
                                      'utf-8', ensure=True)

        with caplog.at_level(logging.ERROR):
            configinit.early_init(args)

        # Check error messages
        expected_errors = []

        if load_autoconfig or not config_py:
            suffix = ' (autoconfig.yml)' if config_py else ''
            if invalid_yaml in ['42', 'list']:
                error = ("While loading data{}: Toplevel object is not a dict"
                         .format(suffix))
                expected_errors.append(error)
            elif invalid_yaml == 'wrong-type':
                error = ("Error{}: Invalid value 'True' - expected a value of "
                         "type str but got bool.".format(suffix))
                expected_errors.append(error)
            elif invalid_yaml == 'unknown':
                error = ("While loading options{}: Unknown option "
                         "colors.foobar".format(suffix))
                expected_errors.append(error)
        if config_py == 'error':
            expected_errors.append("While setting 'foo': No option 'foo'")

        if configinit._init_errors is None:
            actual_errors = []
        else:
            actual_errors = [str(err)
                             for err in configinit._init_errors.errors]

        assert actual_errors == expected_errors

        # Check config values
        dump = config.instance.dump_userconfig()

        if config_py and load_autoconfig and not invalid_yaml:
            expected = [
                'colors.hints.bg = red',
                'colors.hints.fg = magenta',
            ]
        elif config_py:
            expected = ['colors.hints.bg = red']
        elif invalid_yaml:
            expected = ['<Default configuration>']
        else:
            expected = ['colors.hints.fg = magenta']

        assert dump == '\n'.join(expected)

    def test_autoconfig_warning(self, init_patch, args, config_tmpdir, caplog):
        """Test the warning shown for missing autoconfig loading."""
        config_py_file = config_tmpdir / 'config.py'
        config_py_file.ensure()

        with caplog.at_level(logging.ERROR):
            configinit.early_init(args)

        # Check error messages
        assert len(configinit._init_errors.errors) == 1
        error = configinit._init_errors.errors[0]
        assert str(error).startswith("autoconfig loading not specified")

    def test_autoconfig_warning_custom(self, init_patch, args, tmp_path, monkeypatch):
        """Make sure there is no autoconfig warning with --config-py."""
        config_py_path = tmp_path / 'config.py'
        config_py_path.touch()

        args.config_py = str(config_py_path)
        monkeypatch.setattr(configinit.standarddir, 'config_py',
                            lambda: str(config_py_path))

        configinit.early_init(args)

    def test_custom_non_existing_file(self, init_patch, args, tmp_path,
                                      caplog, monkeypatch):
        """Make sure --config-py with a non-existent file doesn't fall back silently."""
        config_py_path = tmp_path / 'config.py'
        assert not config_py_path.exists()

        args.config_py = str(config_py_path)
        monkeypatch.setattr(configinit.standarddir, 'config_py',
                            lambda: str(config_py_path))

        with caplog.at_level(logging.ERROR):
            configinit.early_init(args)

        assert len(configinit._init_errors.errors) == 1
        error = configinit._init_errors.errors[0]
        assert isinstance(error.exception, FileNotFoundError)

    @pytest.mark.parametrize('byte', [
        b'\x00',  # configparser.Error
        b'\xda',  # UnicodeDecodeError
    ])
    def test_state_init_errors(self, init_patch, args, data_tmpdir, byte):
        state_file = data_tmpdir / 'state'
        state_file.write_binary(byte)
        configinit.early_init(args)
        assert configinit._init_errors.errors

    def test_invalid_change_filter(self, init_patch, args):
        config.change_filter('foobar')
        with pytest.raises(configexc.NoOptionError):
            configinit.early_init(args)

    def test_temp_settings_valid(self, init_patch, args):
        args.temp_settings = [('colors.completion.fg', 'magenta')]
        configinit.early_init(args)
        assert config.instance.get_obj('colors.completion.fg') == 'magenta'

    def test_temp_settings_invalid(self, caplog, init_patch, message_mock,
                                   args):
        """Invalid temp settings should show an error."""
        args.temp_settings = [('foo', 'bar')]

        with caplog.at_level(logging.ERROR):
            configinit.early_init(args)

        msg = message_mock.getmsg()
        assert msg.level == usertypes.MessageLevel.error
        assert msg.text == "set: NoOptionError - No option 'foo'"


class TestLateInit:

    @pytest.mark.parametrize('errors', [True, 'fatal', False])
    def test_late_init(self, init_patch, monkeypatch, fake_save_manager, args,
                       mocker, errors):
        configinit.early_init(args)

        if errors:
            err = configexc.ConfigErrorDesc("Error text",
                                            Exception("Exception"))
            errs = configexc.ConfigFileErrors("config.py", [err])
            if errors == 'fatal':
                errs.fatal = True

            monkeypatch.setattr(configinit, '_init_errors', errs)

        msgbox_mock = mocker.patch(
            'qutebrowser.config.configinit.msgbox.msgbox', autospec=True)
        exit_mock = mocker.patch(
            'qutebrowser.config.configinit.sys.exit', autospec=True)

        configinit.late_init(fake_save_manager)

        fake_save_manager.add_saveable.assert_any_call(
            'state-config', unittest.mock.ANY)
        fake_save_manager.add_saveable.assert_any_call(
            'yaml-config', unittest.mock.ANY, unittest.mock.ANY)

        if errors:
            assert len(msgbox_mock.call_args_list) == 1
            _call_posargs, call_kwargs = msgbox_mock.call_args_list[0]
            text = call_kwargs['text'].strip()
            assert text.startswith('Errors occurred while reading config.py:')
            assert '<b>Error text</b>: Exception' in text

            assert exit_mock.called == (errors == 'fatal')
        else:
            assert not msgbox_mock.called

    @pytest.mark.parametrize('settings, size, family', [
        # Only fonts.default_family customized
        ([('fonts.default_family', 'Comic Sans MS')], 10, 'Comic Sans MS'),
        # default_family and default_size
        ([('fonts.default_family', 'Comic Sans MS'),
          ('fonts.default_size', '23pt')], 23, 'Comic Sans MS'),
        # fonts.default_family and font settings customized
        # https://github.com/qutebrowser/qutebrowser/issues/3096
        ([('fonts.default_family', 'Comic Sans MS'),
          ('fonts.keyhint', '12pt default_family')], 12, 'Comic Sans MS'),
        # as above, but with default_size
        ([('fonts.default_family', 'Comic Sans MS'),
          ('fonts.default_size', '23pt'),
          ('fonts.keyhint', 'default_size default_family')],
         23, 'Comic Sans MS'),
    ])
    @pytest.mark.parametrize('method', ['temp', 'auto', 'py'])
    def test_fonts_defaults_init(self, init_patch, args, config_tmpdir,
                                 fake_save_manager, method,
                                 settings, size, family):
        """Ensure setting fonts.default_family at init works properly.

        See https://github.com/qutebrowser/qutebrowser/issues/2973
        and https://github.com/qutebrowser/qutebrowser/issues/5223
        """
        if method == 'temp':
            args.temp_settings = settings
        elif method == 'auto':
            autoconfig_file = config_tmpdir / 'autoconfig.yml'
            lines = (["config_version: 2", "settings:"] +
                     ["  {}:\n    global:\n      '{}'".format(k, v)
                      for k, v in settings])
            autoconfig_file.write_text('\n'.join(lines), 'utf-8', ensure=True)
        elif method == 'py':
            config_py_file = config_tmpdir / 'config.py'
            lines = ["c.{} = '{}'".format(k, v) for k, v in settings]
            lines.append("config.load_autoconfig(False)")
            config_py_file.write_text('\n'.join(lines), 'utf-8', ensure=True)

        configinit.early_init(args)
        configinit.late_init(fake_save_manager)

        # Font
        expected = '{}pt "{}"'.format(size, family)
        assert config.instance.get('fonts.keyhint') == expected

    @pytest.fixture
    def run_configinit(self, init_patch, fake_save_manager, args):
        """Run configinit.early_init() and .late_init()."""
        configinit.early_init(args)
        configinit.late_init(fake_save_manager)

    def test_fonts_defaults_later(self, run_configinit):
        """Ensure setting fonts.default_family/size after init works properly.

        See https://github.com/qutebrowser/qutebrowser/issues/2973
        """
        changed_options = []
        config.instance.changed.connect(changed_options.append)

        config.instance.set_obj('fonts.default_family', 'Comic Sans MS')
        config.instance.set_obj('fonts.default_size', '23pt')

        assert 'fonts.keyhint' in changed_options  # Font
        assert config.instance.get('fonts.keyhint') == '23pt "Comic Sans MS"'

        # Font subclass, but doesn't end with "default_family"
        assert 'fonts.web.family.standard' not in changed_options

    def test_setting_fonts_defaults_family(self, run_configinit):
        """Make sure setting fonts.default_family/size after a family works.

        See https://github.com/qutebrowser/qutebrowser/issues/3130
        """
        config.instance.set_str('fonts.web.family.standard', '')
        config.instance.set_str('fonts.default_family', 'Terminus')
        config.instance.set_str('fonts.default_size', '10pt')

    def test_default_size_hints(self, run_configinit):
        """Make sure default_size applies to the hints font.

        See https://github.com/qutebrowser/qutebrowser/issues/5214
        """
        config.instance.set_obj('fonts.default_family', 'SomeFamily')
        config.instance.set_obj('fonts.default_size', '23pt')
        assert config.instance.get('fonts.hints') == 'bold 23pt SomeFamily'

    def test_default_size_hints_changed(self, run_configinit):
        config.instance.set_obj('fonts.hints', 'bold default_size SomeFamily')

        changed_options = []
        config.instance.changed.connect(changed_options.append)
        config.instance.set_obj('fonts.default_size', '23pt')

        assert config.instance.get('fonts.hints') == 'bold 23pt SomeFamily'
        assert 'fonts.hints' in changed_options


@pytest.mark.parametrize('arg, confval, used', [
    # overridden by commandline arg
    ('webkit', 'webengine', usertypes.Backend.QtWebKit),
    # set in  config
    (None, 'webkit', usertypes.Backend.QtWebKit),
])
def test_get_backend(monkeypatch, args, config_stub,
                     arg, confval, used):
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name != 'PyQt5.QtWebKit':
            return real_import(name, *args, **kwargs)
        raise ImportError

    args.backend = arg
    config_stub.val.backend = confval
    monkeypatch.setattr(builtins, '__import__', fake_import)

    assert configinit.get_backend(args) == used
