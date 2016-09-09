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

    @pytest.mark.parametrize('config, section, option, value', [
        # Simple option without transformation
        ({'general': {'ignore-case': 'false'}},
         'general', 'ignore-case', False),
        # Transformed section with old name
        ({'permissions': {'allow-plugins': 'true'}},
         'content', 'allow-plugins', True),
        # Transformed section with new name
        ({'content': {'allow-plugins': 'true'}},
         'content', 'allow-plugins', True),
        # Transformed option with old name
        ({'colors': {'tab.fg.odd': 'pink'}},
         'colors', 'tabs.fg.odd', QColor('pink')),
        # Transformed option with new name
        ({'colors': {'tabs.fg.odd': 'pink'}},
         'colors', 'tabs.fg.odd', QColor('pink')),
    ])
    def test_get(self, objects, config, section, option, value):
        objects.cp.read_dict(config)
        objects.cfg._from_cp(objects.cp)
        assert objects.cfg.get(section, option) == value

    @pytest.mark.parametrize('config', [
        {'general': {'ignore-case': 'invalid'}},
        {'general': {'ignore-case': 'smart',
                     'private-browsing': '${ignore-case}'}},
    ])
    def test_failing_validation(self, objects, config):
        objects.cp.read_dict(config)
        objects.cfg._from_cp(objects.cp)
        with pytest.raises(configexc.ValidationError):
            objects.cfg._validate_all()

    @pytest.mark.parametrize('config, sect1, opt1, sect2, opt2', [
        # Same section
        ({'general': {'ignore-case': 'false',
                      'private-browsing': '${ignore-case}'}},
         'general', 'ignore-case', 'general', 'private-browsing'),
        # Across sections
        ({'general': {'ignore-case': '${network:do-not-track}'},
          'network': {'do-not-track': 'false'}},
         'general', 'ignore-case', 'network', 'do-not-track'),
    ])
    def test_interpolation(self, objects, config, sect1, opt1, sect2, opt2):
        objects.cp.read_dict(config)
        objects.cfg._from_cp(objects.cp)
        assert not objects.cfg.get(sect1, opt1)
        assert not objects.cfg.get(sect2, opt2)

    def test_invalid_interpolation(self, objects):
        """Test an invalid interpolation."""
        objects.cp.read_dict({'general': {'ignore-case': '${foo}'}})
        objects.cfg._from_cp(objects.cp)
        with pytest.raises(configparser.InterpolationError):
            objects.cfg._validate_all()

    @pytest.mark.parametrize('config, exception', [
        # Invalid interpolation syntax
        ({'general': {'ignore-case': '${'}},
         configexc.InterpolationSyntaxError),
        # Invalid section
        ({'foo': {'bar': 'baz'}}, configexc.NoSectionError),
        # Invalid option
        ({'general': {'bar': 'baz'}}, configexc.NoOptionError),
    ])
    def test_invalid_from_cp(self, objects, config, exception):
        objects.cp.read_dict(config)
        with pytest.raises(exception):
            objects.cfg._from_cp(objects.cp)

    @pytest.mark.parametrize('config, sect, opt, exception', [
        # Invalid section
        ({'foo': {'bar': 'baz'}}, 'foo', 'bar', configexc.NoSectionError),
        # Invalid option
        ({'general': {'bar': 'baz'}}, 'general', 'baz',
         configexc.NoOptionError),
    ])
    def test_invalid_relaxed(self, objects, config, sect, opt, exception):
        objects.cp.read_dict(config)
        objects.cfg._from_cp(objects.cp, relaxed=True)
        with pytest.raises(exception):
            objects.cfg.get(sect, opt)

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


class TestTransformers:

    """Test value transformers in CHANGED_OPTIONS."""

    @pytest.mark.parametrize('val, expected', [('a', 'b'), ('c', 'c')])
    def test_get_value_transformer(self, val, expected):
        func = config._get_value_transformer({'a': 'b'})
        assert func(val) == expected

    @pytest.mark.parametrize('val, expected', [
        ('top', 'top'),
        ('north', 'top'),
        ('south', 'bottom'),
        ('west', 'left'),
        ('east', 'right'),
    ])
    def test_position(self, val, expected):
        func = config._transform_position
        assert func(val) == expected

    OLD_GRADIENT = ('-webkit-gradient(linear, left top, left bottom, '
                    'color-stop(0%,{}), color-stop(100%,{}))')
    NEW_GRADIENT = ('qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {}, '
                    'stop:1 {})')

    @pytest.mark.parametrize('val, expected', [
        ('-unknown-stuff', None),
        ('blue', 'blue'),
        ('rgba(1, 2, 3, 4)', 'rgba(1, 2, 3, 4)'),
        ('-webkit-gradient(unknown)', None),
        (OLD_GRADIENT.format('blah', 'blah'), None),
        (OLD_GRADIENT.format('red', 'green'),
         NEW_GRADIENT.format('rgba(255, 0, 0, 0.8)', 'rgba(0, 128, 0, 0.8)')),
        (OLD_GRADIENT.format(' red', ' green'),
         NEW_GRADIENT.format('rgba(255, 0, 0, 0.8)', 'rgba(0, 128, 0, 0.8)')),
        (OLD_GRADIENT.format('#101010', ' #202020'),
         NEW_GRADIENT.format('rgba(16, 16, 16, 0.8)',
                             'rgba(32, 32, 32, 0.8)')),
        (OLD_GRADIENT.format('#666', ' #777'),
         NEW_GRADIENT.format('rgba(102, 102, 102, 0.8)',
                             'rgba(119, 119, 119, 0.8)')),
        (OLD_GRADIENT.format('red', 'green') + 'more stuff', None),
    ])
    def test_hint_color(self, val, expected):
        assert config._transform_hint_color(val) == expected

    @pytest.mark.parametrize('val, expected', [
        ('bold 12pt Monospace', 'bold 12pt ${_monospace}'),
        ('23pt Monospace', '23pt ${_monospace}'),
        ('bold 12pt ${_monospace}', 'bold 12pt ${_monospace}'),
        ('bold 12pt Comic Sans MS', 'bold 12pt Comic Sans MS'),
    ])
    def test_hint_font(self, val, expected):
        assert config._transform_hint_font(val) == expected


class TestKeyConfigParser:

    """Test config.parsers.keyconf.KeyConfigParser."""

    def test_cmd_binding(self, cmdline_test, config_stub):
        """Test various command bindings.

        See https://github.com/The-Compiler/qutebrowser/issues/615

        Args:
            cmdline_test: A pytest fixture which provides testcases.
        """
        config_stub.data = {'aliases': []}
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
            ('clear-keychain ;; leave-mode', 'leave-mode'),
            ('leave-mode ;; foo', None),

            ('download-remove --all', 'download-clear'),

            ('hint links fill ":open {hint-url}"',
                'hint links fill :open {hint-url}'),
            ('hint links fill ":open -t {hint-url}"',
                'hint links fill :open -t {hint-url}'),

            ('yank-selected', 'yank selection'),
            ('yank-selected --sel', 'yank selection --sel'),
            ('yank-selected -p', 'yank selection -s'),

            ('yank -t', 'yank title'),
            ('yank -ts', 'yank title -s'),
            ('yank -d', 'yank domain'),
            ('yank -ds', 'yank domain -s'),
            ('yank -p', 'yank pretty-url'),
            ('yank -ps', 'yank pretty-url -s'),

            ('paste', 'open -- {clipboard}'),
            ('paste -s', 'open -- {primary}'),
            ('paste -t', 'open -t -- {clipboard}'),
            ('paste -ws', 'open -w -- {primary}'),

            ('open {clipboard}', 'open -- {clipboard}'),
            ('open -t {clipboard}', 'open -t -- {clipboard}'),
            ('open -b {primary}', 'open -b -- {primary}'),

            ('set-cmd-text -s :search', 'set-cmd-text /'),
            ('set-cmd-text -s :search -r', 'set-cmd-text ?'),
            ('set-cmd-text -s :', 'set-cmd-text :'),
            ('set-cmd-text -s :set keybind', 'set-cmd-text -s :bind'),

            ('prompt-yes', 'prompt-accept yes'),
            ('prompt-no', 'prompt-accept no'),
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

    @pytest.fixture(autouse=True)
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
