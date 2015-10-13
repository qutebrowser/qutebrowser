# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

import os
import os.path
import configparser
import types
import argparse
from unittest import mock

from PyQt5.QtCore import QObject
from PyQt5.QtGui import QColor
import pytest

from qutebrowser.config import config, configexc, configdata
from qutebrowser.config.parsers import keyconf
from qutebrowser.commands import runners
from qutebrowser.utils import objreg, standarddir


class TestConfigParser:

    """Test reading of ConfigParser."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.cp = configparser.ConfigParser(interpolation=None,
                                            comment_prefixes='#')
        self.cp.optionxform = lambda opt: opt  # be case-insensitive
        self.cfg = config.ConfigManager(None, None)

    def test_simple(self):
        """Test a simple option which is not transformed."""
        self.cp.read_dict({'general': {'ignore-case': 'false'}})
        self.cfg._from_cp(self.cp)
        assert not self.cfg.get('general', 'ignore-case')

    def test_transformed_section_old(self):
        """Test a transformed section with the old name."""
        self.cp.read_dict({'permissions': {'allow-plugins': 'true'}})
        self.cfg._from_cp(self.cp)
        assert self.cfg.get('content', 'allow-plugins')

    def test_transformed_section_new(self):
        """Test a transformed section with the new name."""
        self.cp.read_dict({'content': {'allow-plugins': 'true'}})
        self.cfg._from_cp(self.cp)
        assert self.cfg.get('content', 'allow-plugins')

    def test_transformed_option_old(self):
        """Test a transformed option with the old name."""
        # WORKAROUND
        # Instance of 'object' has no 'name' member (no-member)
        # pylint: disable=no-member
        self.cp.read_dict({'colors': {'tab.fg.odd': 'pink'}})
        self.cfg._from_cp(self.cp)
        actual = self.cfg.get('colors', 'tabs.fg.odd').name()
        expected = QColor('pink').name()
        assert actual == expected

    def test_transformed_option_new(self):
        """Test a transformed section with the new name."""
        # WORKAROUND
        # Instance of 'object' has no 'name' member (no-member)
        # pylint: disable=no-member
        self.cp.read_dict({'colors': {'tabs.fg.odd': 'pink'}})
        self.cfg._from_cp(self.cp)
        actual = self.cfg.get('colors', 'tabs.fg.odd').name()
        expected = QColor('pink').name()
        assert actual == expected

    def test_invalid_value(self):
        """Test setting an invalid value."""
        self.cp.read_dict({'general': {'ignore-case': 'invalid'}})
        self.cfg._from_cp(self.cp)
        with pytest.raises(configexc.ValidationError):
            self.cfg._validate_all()

    def test_invalid_value_interpolated(self):
        """Test setting an invalid interpolated value."""
        self.cp.read_dict({'general': {'ignore-case': 'smart',
                                       'wrap-search': '${ignore-case}'}})
        self.cfg._from_cp(self.cp)
        with pytest.raises(configexc.ValidationError):
            self.cfg._validate_all()

    def test_interpolation(self):
        """Test setting an interpolated value."""
        self.cp.read_dict({'general': {'ignore-case': 'false',
                                       'wrap-search': '${ignore-case}'}})
        self.cfg._from_cp(self.cp)
        assert not self.cfg.get('general', 'ignore-case')
        assert not self.cfg.get('general', 'wrap-search')

    def test_interpolation_cross_section(self):
        """Test setting an interpolated value from another section."""
        self.cp.read_dict(
            {
                'general': {'ignore-case': '${network:do-not-track}'},
                'network': {'do-not-track': 'false'},
            }
        )
        self.cfg._from_cp(self.cp)
        assert not self.cfg.get('general', 'ignore-case')
        assert not self.cfg.get('network', 'do-not-track')

    def test_invalid_interpolation(self):
        """Test an invalid interpolation."""
        self.cp.read_dict({'general': {'ignore-case': '${foo}'}})
        self.cfg._from_cp(self.cp)
        with pytest.raises(configparser.InterpolationError):
            self.cfg._validate_all()

    def test_invalid_interpolation_syntax(self):
        """Test an invalid interpolation syntax."""
        self.cp.read_dict({'general': {'ignore-case': '${'}})
        with pytest.raises(configexc.InterpolationSyntaxError):
            self.cfg._from_cp(self.cp)

    def test_invalid_section(self):
        """Test an invalid section."""
        self.cp.read_dict({'foo': {'bar': 'baz'}})
        with pytest.raises(configexc.NoSectionError):
            self.cfg._from_cp(self.cp)

    def test_invalid_option(self):
        """Test an invalid option."""
        self.cp.read_dict({'general': {'bar': 'baz'}})
        with pytest.raises(configexc.NoOptionError):
            self.cfg._from_cp(self.cp)

    def test_invalid_section_relaxed(self):
        """Test an invalid section with relaxed=True."""
        self.cp.read_dict({'foo': {'bar': 'baz'}})
        self.cfg._from_cp(self.cp, relaxed=True)
        with pytest.raises(configexc.NoSectionError):
            self.cfg.get('foo', 'bar')  # pylint: disable=bad-config-call

    def test_invalid_option_relaxed(self):
        """Test an invalid option with relaxed=True."""
        self.cp.read_dict({'general': {'bar': 'baz'}})
        self.cfg._from_cp(self.cp, relaxed=True)
        with pytest.raises(configexc.NoOptionError):
            self.cfg.get('general', 'bar')  # pylint: disable=bad-config-call

    def test_fallback(self):
        """Test getting an option with fallback.

        This is done during interpolation in later Python 3.4 versions.

        See https://github.com/The-Compiler/qutebrowser/issues/968
        """
        # pylint: disable=bad-config-call
        assert self.cfg.get('general', 'blabla', fallback='blub') == 'blub'

    def test_sectionproxy(self):
        """Test getting an option via the section proxy."""
        self.cp.read_dict({'general': {'ignore-case': 'false'}})
        self.cfg._from_cp(self.cp)
        assert not self.cfg['general'].get('ignore-case')

    def test_sectionproxy_keyerror(self):
        """Test getting an inexistent option via the section proxy."""
        with pytest.raises(configexc.NoOptionError):
            self.cfg['general'].get('blahblahblub')


class TestKeyConfigParser:

    """Test config.parsers.keyconf.KeyConfigParser."""

    def test_cmd_binding(self, cmdline_test):
        """Test various command bindings.

        See https://github.com/The-Compiler/qutebrowser/issues/615

        Args:
            cmdline_test: A pytest fixture which provides testcases.
        """
        kcp = keyconf.KeyConfigParser(None, None)
        kcp._cur_section = 'normal'
        if cmdline_test.valid:
            kcp._read_command(cmdline_test.cmd)
        else:
            with pytest.raises(keyconf.KeyConfigError):
                kcp._read_command(cmdline_test.cmd)

    @pytest.mark.parametrize('rgx', [rgx for rgx, _repl
                                     in configdata.CHANGED_KEY_COMMANDS])
    def test_default_config_no_deprecated(self, rgx):
        """Make sure the default config contains no deprecated commands."""
        for sect in configdata.KEY_DATA.values():
            for command in sect:
                assert rgx.match(command) is None

    @pytest.mark.parametrize(
        'old, new_expected',
        [
            ('open -t about:blank', 'open -t'),
            ('open -w about:blank', 'open -w'),
            ('open -b about:blank', 'open -b'),
            ('open about:blank', None),
            ('open -t example.com', None),

            ('download-page', 'download'),
            ('cancel-download', 'download-cancel'),

            ('search ""', 'clear-keychain ;; search'),
            ("search ''", 'clear-keychain ;; search'),
            ("search", 'clear-keychain ;; search'),
            ("search ;; foobar", None),
            ('search "foo"', None),

            ('set-cmd-text "foo bar"', 'set-cmd-text foo bar'),
            ("set-cmd-text 'foo bar'", 'set-cmd-text foo bar'),
            ('set-cmd-text foo bar', None),
            ('set-cmd-text "foo bar "', 'set-cmd-text -s foo bar'),
            ("set-cmd-text 'foo bar '", 'set-cmd-text -s foo bar'),

            ('hint links rapid', 'hint --rapid links tab-bg'),
            ('hint links rapid-win', 'hint --rapid links window'),

            ('scroll -50 0', 'scroll left'),
            ('scroll 0 50', 'scroll down'),
            ('scroll 0 -50', 'scroll up'),
            ('scroll 50 0', 'scroll right'),
            ('scroll -50 10', 'scroll-px -50 10'),
            ('scroll 50 50', 'scroll-px 50 50'),
            ('scroll 0 0', 'scroll-px 0 0'),
            ('scroll 23 42', 'scroll-px 23 42'),

            ('search ;; clear-keychain', 'clear-keychain ;; search'),
            ('search;;clear-keychain', 'clear-keychain ;; search'),
            ('search;;foo', None),
            ('leave-mode', 'clear-keychain ;; leave-mode'),
            ('leave-mode ;; foo', None),
        ]
    )
    def test_migrations(self, old, new_expected):
        """Make sure deprecated commands get migrated correctly."""
        if new_expected is None:
            new_expected = old
        new = old
        for rgx, repl in configdata.CHANGED_KEY_COMMANDS:
            if rgx.match(new):
                new = rgx.sub(repl, new)
                break
        assert new == new_expected


@pytest.mark.integration
class TestDefaultConfig:

    """Test validating of the default config."""

    @pytest.mark.usefixtures('qapp')
    def test_default_config(self):
        """Test validating of the default config."""
        conf = config.ConfigManager(None, None)
        conf._validate_all()

    def test_default_key_config(self):
        """Test validating of the default key config."""
        # We import qutebrowser.app so the cmdutils.register decorators run.
        import qutebrowser.app  # pylint: disable=unused-variable
        conf = keyconf.KeyConfigParser(None, None)
        runner = runners.CommandRunner(win_id=0)
        for sectname in configdata.KEY_DATA:
            for cmd in conf.get_bindings_for(sectname).values():
                runner.parse(cmd, aliases=False)


@pytest.mark.integration
class TestConfigInit:

    """Test initializing of the config."""

    @pytest.yield_fixture(autouse=True)
    def setup(self, tmpdir):
        self.conf_path = (tmpdir / 'config').ensure(dir=1)
        self.data_path = (tmpdir / 'data').ensure(dir=1)
        self.cache_path = (tmpdir / 'cache').ensure(dir=1)
        self.env = {
            'XDG_CONFIG_HOME': str(self.conf_path),
            'XDG_DATA_HOME': str(self.data_path),
            'XDG_CACHE_HOME': str(self.cache_path),
        }
        objreg.register('app', QObject())
        objreg.register('save-manager', mock.MagicMock())
        args = argparse.Namespace(relaxed_config=False)
        objreg.register('args', args)
        old_standarddir_args = standarddir._args
        yield
        objreg.global_registry.clear()
        standarddir._args = old_standarddir_args

    def test_config_none(self, monkeypatch):
        """Test initializing with config path set to None."""
        args = types.SimpleNamespace(confdir='', datadir='', cachedir='')
        for k, v in self.env.items():
            monkeypatch.setenv(k, v)
        standarddir.init(args)
        config.init()
        assert not os.listdir(str(self.conf_path))
