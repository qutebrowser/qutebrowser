# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# Copyright 2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Tests for qutebrowser.config.configinit."""

import sys
import logging
import unittest.mock

import pytest

from qutebrowser import qutebrowser
from qutebrowser.config import (config, configdata, configexc, configfiles,
                                configinit)
from qutebrowser.utils import objreg, usertypes


@pytest.fixture
def init_patch(qapp, fake_save_manager, monkeypatch, config_tmpdir,
               data_tmpdir):
    monkeypatch.setattr(configdata, 'DATA', None)
    monkeypatch.setattr(configfiles, 'state', None)
    monkeypatch.setattr(config, 'instance', None)
    monkeypatch.setattr(config, 'key_instance', None)
    monkeypatch.setattr(config, 'change_filters', [])
    monkeypatch.setattr(configinit, '_init_errors', [])
    # Make sure we get no SSL warning
    monkeypatch.setattr(configinit.earlyinit, 'check_backend_ssl_support',
                        lambda _backend: None)
    yield
    try:
        objreg.delete('config-commands')
    except KeyError:
        pass


@pytest.mark.parametrize('load_autoconfig', [True, False])  # noqa
@pytest.mark.parametrize('config_py', [True, 'error', False])
@pytest.mark.parametrize('invalid_yaml',
                         ['42', 'unknown', 'wrong-type', False])
# pylint: disable=too-many-branches
def test_early_init(init_patch, config_tmpdir, caplog, fake_args,
                    load_autoconfig, config_py, invalid_yaml):
    # Prepare files
    autoconfig_file = config_tmpdir / 'autoconfig.yml'
    config_py_file = config_tmpdir / 'config.py'

    if invalid_yaml == '42':
        text = '42'
    elif invalid_yaml == 'unknown':
        text = 'global:\n  colors.foobar: magenta\n'
    elif invalid_yaml == 'wrong-type':
        text = 'global:\n  tabs.position: true\n'
    else:
        assert not invalid_yaml
        text = 'global:\n  colors.hints.fg: magenta\n'
    autoconfig_file.write_text(text, 'utf-8', ensure=True)

    if config_py:
        config_py_lines = ['c.colors.hints.bg = "red"']
        if not load_autoconfig:
            config_py_lines.append('config.load_autoconfig = False')
        if config_py == 'error':
            config_py_lines.append('c.foo = 42')
        config_py_file.write_text('\n'.join(config_py_lines),
                                  'utf-8', ensure=True)

    with caplog.at_level(logging.ERROR):
        configinit.early_init(fake_args)

    # Check error messages
    expected_errors = []
    if config_py == 'error':
        expected_errors.append(
            "Errors occurred while reading config.py:\n"
            "  While setting 'foo': No option 'foo'")
    if load_autoconfig or not config_py:
        error = "Errors occurred while reading autoconfig.yml:\n"
        if invalid_yaml == '42':
            error += "  While loading data: Toplevel object is not a dict"
            expected_errors.append(error)
        elif invalid_yaml == 'wrong-type':
            error += ("  Error: Invalid value 'True' - expected a value of "
                      "type str but got bool.")
            expected_errors.append(error)

    actual_errors = [str(err) for err in configinit._init_errors]
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
        configinit.early_init(fake_args)


@pytest.mark.parametrize('errors', [True, False])
def test_late_init(init_patch, monkeypatch, fake_save_manager, fake_args,
                   mocker, errors):
    configinit.early_init(fake_args)
    if errors:
        err = configexc.ConfigErrorDesc("Error text", Exception("Exception"))
        errs = configexc.ConfigFileErrors("config.py", [err])
        monkeypatch.setattr(configinit, '_init_errors', [errs])
    msgbox_mock = mocker.patch('qutebrowser.config.configinit.msgbox.msgbox',
                               autospec=True)

    configinit.late_init(fake_save_manager)

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
        assert configinit.qt_args(parsed) == expected

    def test_qt_both(self, config_stub, parser):
        """Test commandline with a Qt argument and flag."""
        args = parser.parse_args(['--qt-arg', 'stylesheet', 'foobar',
                                  '--qt-flag', 'reverse'])
        qt_args = configinit.qt_args(args)
        assert qt_args[0] == sys.argv[0]
        assert '--reverse' in qt_args
        assert '--stylesheet' in qt_args
        assert 'foobar' in qt_args

    def test_with_settings(self, config_stub, parser):
        parsed = parser.parse_args(['--qt-flag', 'foo'])
        config_stub.val.qt_args = ['bar']
        assert configinit.qt_args(parsed) == [sys.argv[0], '--foo', '--bar']


@pytest.mark.parametrize('arg, confval, can_import, is_new_webkit, used', [
    # overridden by commandline arg
    ('webkit', 'auto', False, False, usertypes.Backend.QtWebKit),
    # overridden by config
    (None, 'webkit', False, False, usertypes.Backend.QtWebKit),
    # WebKit available but too old
    (None, 'auto', True, False, usertypes.Backend.QtWebEngine),
    # WebKit available and new
    (None, 'auto', True, True, usertypes.Backend.QtWebKit),
    # WebKit unavailable
    (None, 'auto', False, False, usertypes.Backend.QtWebEngine),
])
def test_get_backend(monkeypatch, fake_args, config_stub,
                     arg, confval, can_import, is_new_webkit, used):
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name != 'PyQt5.QtWebKit':
            return real_import(name, *args, **kwargs)
        if can_import:
            return None
        raise ImportError

    fake_args.backend = arg
    config_stub.val.backend = confval
    monkeypatch.setattr(configinit.qtutils, 'is_new_qtwebkit',
                        lambda: is_new_webkit)
    monkeypatch.setattr('builtins.__import__', fake_import)

    assert configinit.get_backend(fake_args) == used
