# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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
import collections
import shutil
from unittest import mock

from PyQt5.QtCore import QObject
from PyQt5.QtGui import QColor
import pytest

import qutebrowser
from qutebrowser.config import config, configexc, configdata
from qutebrowser.config.parsers import keyconf
from qutebrowser.commands import runners
from qutebrowser.utils import objreg, standarddir


class TestConfigParser:

    """Test reading of ConfigParser."""

    Objects = collections.namedtuple('Objects', ['cp', 'cfg'])

    @pytest.fixture
    def objects(self):
        cp = configparser.ConfigParser(interpolation=None,
                                       comment_prefixes='#')
        cp.optionxform = lambda opt: opt  # be case-insensitive
        cfg = config.ConfigManager()
        cfg.read(None, None)
        return self.Objects(cp=cp, cfg=cfg)

    def test_simple(self, objects):
        """Test a simple option which is not transformed."""
        objects.cp.read_dict({'general': {'ignore-case': 'false'}})
        objects.cfg._from_cp(objects.cp)
        assert not objects.cfg.get('general', 'ignore-case')

    def test_transformed_section_old(self, objects):
        """Test a transformed section with the old name."""
        objects.cp.read_dict({'permissions': {'allow-plugins': 'true'}})
        objects.cfg._from_cp(objects.cp)
        assert objects.cfg.get('content', 'allow-plugins')

    def test_transformed_section_new(self, objects):
        """Test a transformed section with the new name."""
        objects.cp.read_dict({'content': {'allow-plugins': 'true'}})
        objects.cfg._from_cp(objects.cp)
        assert objects.cfg.get('content', 'allow-plugins')

    def test_transformed_option_old(self, objects):
        """Test a transformed option with the old name."""
        objects.cp.read_dict({'colors': {'tab.fg.odd': 'pink'}})
        objects.cfg._from_cp(objects.cp)
        actual = objects.cfg.get('colors', 'tabs.fg.odd').name()
        expected = QColor('pink').name()
        assert actual == expected

    def test_transformed_option_new(self, objects):
        """Test a transformed section with the new name."""
        objects.cp.read_dict({'colors': {'tabs.fg.odd': 'pink'}})
        objects.cfg._from_cp(objects.cp)
        actual = objects.cfg.get('colors', 'tabs.fg.odd').name()
        expected = QColor('pink').name()
        assert actual == expected

    def test_invalid_value(self, objects):
        """Test setting an invalid value."""
        objects.cp.read_dict({'general': {'ignore-case': 'invalid'}})
        objects.cfg._from_cp(objects.cp)
        with pytest.raises(configexc.ValidationError):
            objects.cfg._validate_all()

    def test_invalid_value_interpolated(self, objects):
        """Test setting an invalid interpolated value."""
        objects.cp.read_dict({'general': {
            'ignore-case': 'smart', 'private-browsing': '${ignore-case}'}})
        objects.cfg._from_cp(objects.cp)
        with pytest.raises(configexc.ValidationError):
            objects.cfg._validate_all()

    def test_interpolation(self, objects):
        """Test setting an interpolated value."""
        objects.cp.read_dict({'general': {
            'ignore-case': 'false', 'private-browsing': '${ignore-case}'}})
        objects.cfg._from_cp(objects.cp)
        assert not objects.cfg.get('general', 'ignore-case')
        assert not objects.cfg.get('general', 'private-browsing')

    def test_interpolation_cross_section(self, objects):
        """Test setting an interpolated value from another section."""
        objects.cp.read_dict({
            'general': {'ignore-case': '${network:do-not-track}'},
            'network': {'do-not-track': 'false'},
        })
        objects.cfg._from_cp(objects.cp)
        assert not objects.cfg.get('general', 'ignore-case')
        assert not objects.cfg.get('network', 'do-not-track')

    def test_invalid_interpolation(self, objects):
        """Test an invalid interpolation."""
        objects.cp.read_dict({'general': {'ignore-case': '${foo}'}})
        objects.cfg._from_cp(objects.cp)
        with pytest.raises(configparser.InterpolationError):
            objects.cfg._validate_all()

    def test_invalid_interpolation_syntax(self, objects):
        """Test an invalid interpolation syntax."""
        objects.cp.read_dict({'general': {'ignore-case': '${'}})
        with pytest.raises(configexc.InterpolationSyntaxError):
            objects.cfg._from_cp(objects.cp)

    def test_invalid_section(self, objects):
        """Test an invalid section."""
        objects.cp.read_dict({'foo': {'bar': 'baz'}})
        with pytest.raises(configexc.NoSectionError):
            objects.cfg._from_cp(objects.cp)

    def test_invalid_option(self, objects):
        """Test an invalid option."""
        objects.cp.read_dict({'general': {'bar': 'baz'}})
        with pytest.raises(configexc.NoOptionError):
            objects.cfg._from_cp(objects.cp)

    def test_invalid_section_relaxed(self, objects):
        """Test an invalid section with relaxed=True."""
        objects.cp.read_dict({'foo': {'bar': 'baz'}})
        objects.cfg._from_cp(objects.cp, relaxed=True)
        with pytest.raises(configexc.NoSectionError):
            objects.cfg.get('foo', 'bar')

    def test_invalid_option_relaxed(self, objects):
        """Test an invalid option with relaxed=True."""
        objects.cp.read_dict({'general': {'bar': 'baz'}})
        objects.cfg._from_cp(objects.cp, relaxed=True)
        with pytest.raises(configexc.NoOptionError):
            objects.cfg.get('general', 'bar')

    def test_fallback(self, objects):
        """Test getting an option with fallback.

        This is done during interpolation in later Python 3.4 versions.

        See https://github.com/The-Compiler/qutebrowser/issues/968
        """
        assert objects.cfg.get('general', 'blabla', fallback='blub') == 'blub'

    def test_sectionproxy(self, objects):
        """Test getting an option via the section proxy."""
        objects.cp.read_dict({'general': {'ignore-case': 'false'}})
        objects.cfg._from_cp(objects.cp)
        assert not objects.cfg['general'].get('ignore-case')

    def test_sectionproxy_keyerror(self, objects):
        """Test getting an inexistent option via the section proxy."""
        with pytest.raises(configexc.NoOptionError):
            objects.cfg['general'].get('blahblahblub')

    @pytest.mark.parametrize('old_sect, new_sect',
        config.ConfigManager.RENAMED_SECTIONS.items())
    def test_renamed_sections(self, old_sect, new_sect):
        """Make sure renamed sections don't exist anymore."""
        assert old_sect not in configdata.DATA
        assert new_sect in configdata.DATA

    @pytest.mark.parametrize('old_tuple, new_option',
        sorted(config.ConfigManager.RENAMED_OPTIONS.items()))
    def test_renamed_options(self, old_tuple, new_option):
        """Make sure renamed options exist under the new name."""
        section, old_option = old_tuple
        assert old_option not in configdata.DATA[section]
        assert new_option in configdata.DATA[section]

    @pytest.mark.parametrize('section, option',
        config.ConfigManager.DELETED_OPTIONS)
    def test_deleted_options(self, section, option):
        """Make sure renamed options don't exist anymore."""
        assert option not in configdata.DATA[section]

    def test_config_reading_with_deleted_options(self, objects):
        """Test an invalid option with relaxed=True."""
        objects.cp.read_dict({
            'general': collections.OrderedDict(
                [('wrap-search', 'true'), ('save-session', 'true')])
        })
        objects.cfg._from_cp(objects.cp)
        with pytest.raises(configexc.NoOptionError):
            objects.cfg.get('general', 'wrap-search')
        assert objects.cfg.get('general', 'save-session')


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

            ('download-remove --all', 'download-clear'),
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


@pytest.mark.usefixtures('config_tmpdir')
@pytest.mark.integration
class TestDefaultConfig:

    """Test validating of the default config."""

    @pytest.mark.usefixtures('qapp')
    def test_default_config(self):
        """Test validating of the default config."""
        conf = config.ConfigManager()
        conf.read(None, None)
        conf._validate_all()

    def test_default_key_config(self):
        """Test validating of the default key config."""
        # We import qutebrowser.app so the cmdutils.register decorators run.
        import qutebrowser.app  # pylint: disable=unused-variable
        conf = keyconf.KeyConfigParser(None, None)
        runner = runners.CommandRunner(win_id=0)
        for sectname in configdata.KEY_DATA:
            for cmd in conf.get_bindings_for(sectname).values():
                runner.parse(cmd)

    def test_upgrade_version(self):
        """Fail when the qutebrowser version changed.

        The aim of this is to remind us to add a new file to old_configs.

        If the config file of the current release didn't change compared to the
        last one in old_configs, just increment the version here.

        If it did change, place a new qutebrowser-vx.y.z.conf in old_configs
        and then increment the version.
        """
        assert qutebrowser.__version__ == '0.8.1'

    @pytest.mark.parametrize('filename',
        os.listdir(os.path.join(os.path.dirname(__file__), 'old_configs')),
        ids=os.path.basename)
    def test_old_config(self, qapp, tmpdir, filename):
        """Check if upgrading old configs works correctly."""
        full_path = os.path.join(os.path.dirname(__file__), 'old_configs',
                                 filename)
        shutil.copy(full_path, str(tmpdir / 'qutebrowser.conf'))
        conf = config.ConfigManager()
        conf.read(str(tmpdir), 'qutebrowser.conf')


@pytest.mark.integration
class TestConfigInit:

    """Test initializing of the config."""

    @pytest.yield_fixture(autouse=True)
    def patch(self, fake_args):
        objreg.register('app', QObject())
        objreg.register('save-manager', mock.MagicMock())
        fake_args.relaxed_config = False
        old_standarddir_args = standarddir._args
        yield
        objreg.delete('app')
        objreg.delete('save-manager')
        # registered by config.init()
        objreg.delete('config')
        objreg.delete('key-config')
        objreg.delete('state-config')
        standarddir._args = old_standarddir_args

    @pytest.fixture
    def env(self, tmpdir):
        conf_path = (tmpdir / 'config').ensure(dir=1)
        data_path = (tmpdir / 'data').ensure(dir=1)
        cache_path = (tmpdir / 'cache').ensure(dir=1)
        env = {
            'XDG_CONFIG_HOME': str(conf_path),
            'XDG_DATA_HOME': str(data_path),
            'XDG_CACHE_HOME': str(cache_path),
        }
        return env

    def test_config_none(self, monkeypatch, env, fake_args):
        """Test initializing with config path set to None."""
        fake_args.confdir = ''
        fake_args.datadir = ''
        fake_args.cachedir = ''
        fake_args.basedir = None
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        standarddir.init(fake_args)
        config.init()
        assert not os.listdir(env['XDG_CONFIG_HOME'])
