# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# Copyright 2017-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Tests for qutebrowser.config.configfiles."""

import os
import sys
import unittest.mock
import textwrap

import pytest
from PyQt5.QtCore import QSettings

from qutebrowser.config import (config, configfiles, configexc, configdata,
                                configtypes)
from qutebrowser.utils import utils, usertypes, urlmatch
from qutebrowser.keyinput import keyutils


@pytest.fixture(autouse=True)
def configdata_init():
    """Initialize configdata if needed."""
    if configdata.DATA is None:
        configdata.init()


class AutoConfigHelper:

    """A helper to easily create/validate autoconfig.yml files."""

    def __init__(self, config_tmpdir):
        self.fobj = config_tmpdir / 'autoconfig.yml'

    def write_toplevel(self, data):
        with self.fobj.open('w', encoding='utf-8') as f:
            utils.yaml_dump(data, f)

    def write(self, values):
        data = {'config_version': 2, 'settings': values}
        self.write_toplevel(data)

    def write_raw(self, text):
        self.fobj.write_text(text, encoding='utf-8', ensure=True)

    def read_toplevel(self):
        with self.fobj.open('r', encoding='utf-8') as f:
            data = utils.yaml_load(f)
            assert data['config_version'] == 2
            return data

    def read(self):
        return self.read_toplevel()['settings']

    def read_raw(self):
        return self.fobj.read_text('utf-8')


@pytest.fixture
def autoconfig(config_tmpdir):
    return AutoConfigHelper(config_tmpdir)


@pytest.mark.parametrize('old_data, insert, new_data', [
    (None,
     False,
     '[general]\n'
     'qt_version = 5.6.7\n'
     'version = 1.2.3\n'
     '\n'
     '[geometry]\n'
     '\n'),
    ('[general]\n'
     'fooled = true',
     False,
     '[general]\n'
     'qt_version = 5.6.7\n'
     'version = 1.2.3\n'
     '\n'
     '[geometry]\n'
     '\n'),
    ('[general]\n'
     'foobar = 42',
     False,
     '[general]\n'
     'foobar = 42\n'
     'qt_version = 5.6.7\n'
     'version = 1.2.3\n'
     '\n'
     '[geometry]\n'
     '\n'),
    (None,
     True,
     '[general]\n'
     'qt_version = 5.6.7\n'
     'version = 1.2.3\n'
     'newval = 23\n'
     '\n'
     '[geometry]\n'
     '\n'),
])
def test_state_config(fake_save_manager, data_tmpdir, monkeypatch,
                      old_data, insert, new_data):
    monkeypatch.setattr(configfiles.qutebrowser, '__version__', '1.2.3')
    monkeypatch.setattr(configfiles, 'qVersion', lambda: '5.6.7')

    statefile = data_tmpdir / 'state'
    if old_data is not None:
        statefile.write_text(old_data, 'utf-8')

    state = configfiles.StateConfig()
    state.init_save_manager(fake_save_manager)

    if insert:
        state['general']['newval'] = '23'
    if 'foobar' in (old_data or ''):
        assert state['general']['foobar'] == '42'

    state._save()

    assert statefile.read_text('utf-8') == new_data
    fake_save_manager.add_saveable('state-config', unittest.mock.ANY)


@pytest.mark.parametrize('old_version, new_version, changed', [
    (None, '5.12.1', False),
    ('5.12.1', '5.12.1', False),
    ('5.12.2', '5.12.1', True),
    ('5.12.1', '5.12.2', True),
    ('5.13.0', '5.12.2', True),
    ('5.12.2', '5.13.0', True),
])
def test_qt_version_changed(data_tmpdir, monkeypatch,
                            old_version, new_version, changed):
    monkeypatch.setattr(configfiles, 'qVersion', lambda: new_version)

    statefile = data_tmpdir / 'state'
    if old_version is not None:
        data = ('[general]\n'
                'qt_version = {}'.format(old_version))
        statefile.write_text(data, 'utf-8')

    state = configfiles.StateConfig()
    assert state.qt_version_changed == changed


@pytest.fixture
def yaml(config_tmpdir):
    return configfiles.YamlConfig()


class TestYaml:

    @pytest.mark.parametrize('old_config', [
        None,
        # Only global
        {'colors.hints.fg': {'global': 'magenta'}},
        # Global and for pattern
        {'content.javascript.enabled':
         {'global': True, 'https://example.com/': False}},
        # Only for pattern
        {'content.images': {'https://example.com/': False}},
    ])
    @pytest.mark.parametrize('insert', [True, False])
    def test_yaml_config(self, yaml, autoconfig, old_config, insert):
        if old_config is not None:
            autoconfig.write(old_config)

        yaml.load()

        if insert:
            yaml.set_obj('tabs.show', 'never')

        yaml._save()

        if not insert and old_config is None:
            lines = []
        else:
            data = autoconfig.read()
            lines = autoconfig.read_raw().splitlines()

            if insert:
                assert lines[0].startswith(
                    '# If a config.py file exists, this file is ignored')
                assert lines[3].startswith('# DO NOT edit this file by hand,')

        print(lines)

        if old_config is None:
            pass
        elif 'colors.hints.fg' in old_config:
            assert data['colors.hints.fg'] == {'global': 'magenta'}
        elif 'content.javascript.enabled' in old_config:
            expected = {'global': True, 'https://example.com/': False}
            assert data['content.javascript.enabled'] == expected
        elif 'content.images' in old_config:
            assert data['content.images'] == {'https://example.com/': False}

        if insert:
            assert data['tabs.show'] == {'global': 'never'}

    def test_init_save_manager(self, yaml, fake_save_manager):
        yaml.init_save_manager(fake_save_manager)
        fake_save_manager.add_saveable.assert_called_with(
            'yaml-config', unittest.mock.ANY, unittest.mock.ANY)

    def test_unknown_key(self, yaml, autoconfig):
        """An unknown setting should show an error."""
        autoconfig.write({'hello': {'global': 'world'}})

        with pytest.raises(configexc.ConfigFileErrors) as excinfo:
            yaml.load()

        assert len(excinfo.value.errors) == 1
        error = excinfo.value.errors[0]
        assert error.text == "While loading options"
        assert str(error.exception) == "Unknown option hello"

    def test_multiple_unknown_keys(self, yaml, autoconfig):
        """With multiple unknown settings, all should be shown."""
        autoconfig.write({'one': {'global': 1}, 'two': {'global': 2}})

        with pytest.raises(configexc.ConfigFileErrors) as excinfo:
            yaml.load()

        assert len(excinfo.value.errors) == 2
        error1, error2 = excinfo.value.errors
        assert error1.text == error2.text == "While loading options"
        assert str(error1.exception) == "Unknown option one"
        assert str(error2.exception) == "Unknown option two"

    @pytest.mark.parametrize('old_config', [
        None,
        {'colors.hints.fg': {'global': 'magenta'}},
    ])
    @pytest.mark.parametrize('key, value', [
        ('colors.hints.fg', 'green'),
        ('colors.hints.bg', None),
        ('confirm_quit', True),
        ('confirm_quit', False),
    ])
    def test_changed(self, yaml, qtbot, autoconfig,
                     old_config, key, value):
        if old_config is not None:
            autoconfig.write(old_config)

        yaml.load()

        with qtbot.wait_signal(yaml.changed):
            yaml.set_obj(key, value)

        assert yaml._values[key].get_for_url(fallback=False) == value

        yaml._save()

        yaml = configfiles.YamlConfig()
        yaml.load()

        assert yaml._values[key].get_for_url(fallback=False) == value

    def test_iter(self, yaml):
        assert list(iter(yaml)) == list(iter(yaml._values.values()))

    @pytest.mark.parametrize('old_config', [
        None,
        {'colors.hints.fg': {'global': 'magenta'}},
    ])
    def test_unchanged(self, yaml, autoconfig, old_config):
        mtime = None
        if old_config is not None:
            autoconfig.write(old_config)
            mtime = autoconfig.fobj.stat().mtime

        yaml.load()
        yaml._save()

        if old_config is None:
            assert not autoconfig.fobj.exists()
        else:
            assert autoconfig.fobj.stat().mtime == mtime

    @pytest.mark.parametrize('line, text, exception', [
        ('%', 'While parsing', 'while scanning a directive'),
        ('settings: 42\nconfig_version: 2',
         'While loading data', "'settings' object is not a dict"),
        ('foo: 42\nconfig_version: 2', 'While loading data',
         "Toplevel object does not contain 'settings' key"),
        ('settings: {}', 'While loading data',
         "Toplevel object does not contain 'config_version' key"),
        ('42', 'While loading data', "Toplevel object is not a dict"),
        ('settings: {"content.images": 42}\nconfig_version: 2',
         "While parsing 'content.images'", "value is not a dict"),
        ('settings: {"content.images": {"https://": true}}\nconfig_version: 2',
         "While parsing pattern 'https://' for 'content.images'",
         "Pattern without host"),
        ('settings: {"content.images": {true: true}}\nconfig_version: 2',
         "While parsing 'content.images'", "pattern is not of type string"),
    ])
    def test_invalid(self, yaml, autoconfig, line, text, exception):
        autoconfig.write_raw(line)

        with pytest.raises(configexc.ConfigFileErrors) as excinfo:
            yaml.load()

        assert len(excinfo.value.errors) == 1
        error = excinfo.value.errors[0]
        assert error.text == text
        assert str(error.exception).splitlines()[0] == exception
        assert error.traceback is None

    def test_legacy_migration(self, yaml, autoconfig, qtbot):
        autoconfig.write_toplevel({
            'config_version': 1,
            'global': {'content.javascript.enabled': True},
        })
        with qtbot.wait_signal(yaml.changed):
            yaml.load()

        yaml._save()

        data = autoconfig.read_toplevel()
        assert data == {
            'config_version': 2,
            'settings': {
                'content.javascript.enabled': {
                    'global': True,
                }
            }
        }

    def test_read_newer_version(self, yaml, autoconfig):
        autoconfig.write_toplevel({
            'config_version': 999,
            'settings': {},
        })
        with pytest.raises(configexc.ConfigFileErrors) as excinfo:
            yaml.load()

        assert len(excinfo.value.errors) == 1
        error = excinfo.value.errors[0]
        assert error.text == "While reading"
        msg = "Can't read config from incompatible newer version"
        assert error.exception == msg

    @pytest.fixture
    def unreadable_autoconfig(self, autoconfig):
        autoconfig.fobj.ensure()
        autoconfig.fobj.chmod(0)
        if os.access(str(autoconfig.fobj), os.R_OK):
            # Docker container or similar
            pytest.skip("File was still readable")

        yield autoconfig

        autoconfig.fobj.chmod(0o755)

    def test_oserror(self, yaml, unreadable_autoconfig):
        with pytest.raises(configexc.ConfigFileErrors) as excinfo:
            yaml.load()

        assert len(excinfo.value.errors) == 1
        error = excinfo.value.errors[0]
        assert error.text == "While reading"
        assert isinstance(error.exception, OSError)
        assert error.traceback is None

    def test_unset(self, yaml, qtbot):
        name = 'tabs.show'
        yaml.set_obj(name, 'never')

        with qtbot.wait_signal(yaml.changed):
            yaml.unset(name)

        assert name not in yaml

    def test_unset_never_set(self, yaml, qtbot):
        with qtbot.assert_not_emitted(yaml.changed):
            yaml.unset('tabs.show')

    def test_clear(self, yaml, qtbot):
        name = 'tabs.show'
        yaml.set_obj(name, 'never')

        with qtbot.wait_signal(yaml.changed):
            yaml.clear()

        assert name not in yaml


class TestYamlMigrations:

    @pytest.fixture
    def migration_test(self, yaml, autoconfig):
        def run(setting, old, new):
            autoconfig.write({setting: {'global': old}})

            yaml.load()
            yaml._save()

            data = autoconfig.read()
            assert data[setting]['global'] == new

        return run

    def test_deleted_key(self, monkeypatch, yaml, autoconfig):
        """A key marked as deleted should be removed."""
        autoconfig.write({'hello': {'global': 'world'}})

        monkeypatch.setattr(configdata.MIGRATIONS, 'deleted', ['hello'])

        yaml.load()
        yaml._save()

        data = autoconfig.read()
        assert not data

    def test_renamed_key(self, monkeypatch, yaml, autoconfig):
        """A key marked as renamed should be renamed properly."""
        autoconfig.write({'old': {'global': 'value'}})

        monkeypatch.setattr(configdata.MIGRATIONS, 'renamed',
                            {'old': 'tabs.show'})

        yaml.load()
        yaml._save()

        data = autoconfig.read()
        assert data == {'tabs.show': {'global': 'value'}}

    def test_renamed_key_unknown_target(self, monkeypatch, yaml,
                                        autoconfig):
        """A key marked as renamed with invalid name should raise an error."""
        autoconfig.write({'old': {'global': 'value'}})

        monkeypatch.setattr(configdata.MIGRATIONS, 'renamed',
                            {'old': 'new'})

        with pytest.raises(configexc.ConfigFileErrors) as excinfo:
            yaml.load()

        assert len(excinfo.value.errors) == 1
        error = excinfo.value.errors[0]
        assert error.text == "While loading options"
        assert str(error.exception) == "Unknown option new"

    @pytest.mark.parametrize('persist, expected', [
        (True, 'persist'),
        (False, 'normal'),
    ])
    def test_merge_persist(self, yaml, autoconfig, persist, expected):
        """Tests for migration of tabs.persist_mode_on_change."""
        autoconfig.write({'tabs.persist_mode_on_change': {'global': persist}})
        yaml.load()
        yaml._save()

        data = autoconfig.read()
        assert 'tabs.persist_mode_on_change' not in data
        assert data['tabs.mode_on_change']['global'] == expected

    def test_bindings_default(self, yaml, autoconfig):
        """Make sure bindings.default gets removed from autoconfig.yml."""
        autoconfig.write({'bindings.default': {'global': '{}'}})

        yaml.load()
        yaml._save()

        data = autoconfig.read()
        assert 'bindings.default' not in data

    @pytest.mark.parametrize('public_only, expected', [
        (True, 'default-public-interface-only'),
        (False, 'all-interfaces'),
    ])
    def test_webrtc(self, yaml, autoconfig, public_only, expected):
        autoconfig.write({'content.webrtc_public_interfaces_only':
                          {'global': public_only}})

        yaml.load()
        yaml._save()

        data = autoconfig.read()
        assert data['content.webrtc_ip_handling_policy']['global'] == expected

    @pytest.mark.parametrize('setting, old, new', [
        ('tabs.favicons.show', True, 'always'),
        ('tabs.favicons.show', False, 'never'),
        ('tabs.favicons.show', 'always', 'always'),

        ('scrolling.bar', True, 'always'),
        ('scrolling.bar', False, 'when-searching'),
        ('scrolling.bar', 'always', 'always'),

        ('qt.force_software_rendering', True, 'software-opengl'),
        ('qt.force_software_rendering', False, 'none'),
        ('qt.force_software_rendering', 'chromium', 'chromium'),
    ])
    def test_bool(self, migration_test, setting, old, new):
        migration_test(setting, old, new)

    @pytest.mark.parametrize('setting', [
        'tabs.title.format',
        'tabs.title.format_pinned',
        'window.title_format'
    ])
    @pytest.mark.parametrize('old, new', [
        ('{title}', '{current_title}'),
        ('eve{title}duna', 'eve{current_title}duna'),
        ('eve{{title}}duna', 'eve{{title}}duna'),
        ('{{title}}', '{{title}}'),
        ('', ''),
        (None, None),
    ])
    def test_title_format(self, migration_test, setting, old, new):
        migration_test(setting, old, new)

    @pytest.mark.parametrize('old, new', [
        (None, ('Mozilla/5.0 ({os_info}) '
                'AppleWebKit/{webkit_version} (KHTML, like Gecko) '
                '{qt_key}/{qt_version} '
                '{upstream_browser_key}/{upstream_browser_version} '
                'Safari/{webkit_version}')),
        ('toaster', 'toaster'),
    ])
    def test_user_agent(self, migration_test, old, new):
        migration_test('content.headers.user_agent', old, new)

    OLD_DEFAULT_FONTS = (
        'Monospace, "DejaVu Sans Mono", Monaco, "Bitstream Vera Sans Mono", '
        '"Andale Mono", "Courier New", Courier, "Liberation Mono", monospace, '
        'Fixed, Consolas, Terminal'
    )

    @pytest.mark.parametrize('old, new', [
        (OLD_DEFAULT_FONTS,
         []),
        ('Custom Font',
         ['Custom Font']),
        ('Custom Font, ' + OLD_DEFAULT_FONTS,
         ['Custom Font']),
        ('Terminus, ' + OLD_DEFAULT_FONTS,
         ['Terminus']),
        ('"xos4 Terminus", ' + OLD_DEFAULT_FONTS,
         ['xos4 Terminus']),
        ('xos4 Terminus, ' + OLD_DEFAULT_FONTS,
         ['xos4 Terminus']),
        ('"xos4 Terminus", Terminus, ' + OLD_DEFAULT_FONTS,
         ['xos4 Terminus', 'Terminus']),
        ('Terminus, "xos4 Terminus", ' + OLD_DEFAULT_FONTS,
         ['Terminus', 'xos4 Terminus']),
        ('xos4 Terminus, Terminus, ' + OLD_DEFAULT_FONTS,
         ['xos4 Terminus', 'Terminus']),
        ('Terminus, xos4 Terminus, ' + OLD_DEFAULT_FONTS,
         ['Terminus', 'xos4 Terminus']),
    ])
    def test_font_default_family(self, yaml, autoconfig, old, new):
        autoconfig.write({'fonts.monospace': {'global': old}})

        yaml.load()
        yaml._save()

        data = autoconfig.read()
        assert data['fonts.default_family']['global'] == new

    @pytest.mark.parametrize('setting, old, new', [
        # Font
        ('fonts.hints', '10pt monospace', '10pt default_family'),
        # QtFont
        ('fonts.debug_console', '10pt monospace', '10pt default_family'),
        # String
        ('content.headers.accept_language', 'x monospace', 'x monospace'),
        # Not at end of string
        ('fonts.hints', '10pt monospace serif', '10pt monospace serif'),
    ])
    def test_font_replacements(self, migration_test, setting, old, new):
        migration_test(setting, old, new)


class ConfPy:

    """Helper class to get a confpy fixture."""

    def __init__(self, tmpdir, filename: str = "config.py"):
        self._file = tmpdir / filename
        self.filename = str(self._file)

    def write(self, *lines):
        text = '\n'.join(lines)
        self._file.write_text(text, 'utf-8', ensure=True)

    def read(self, error=False):
        """Read the config.py via configfiles and check for errors."""
        if error:
            with pytest.raises(configexc.ConfigFileErrors) as excinfo:
                configfiles.read_config_py(self.filename)
            errors = excinfo.value.errors
            assert len(errors) == 1
            return errors[0]
        else:
            configfiles.read_config_py(self.filename, raising=True)
            return None

    def write_qbmodule(self):
        self.write('import qbmodule',
                   'qbmodule.run(config)')


@pytest.fixture
def confpy(tmpdir, config_tmpdir, data_tmpdir, config_stub, key_config_stub):
    return ConfPy(tmpdir)


class TestConfigPyModules:

    pytestmark = pytest.mark.usefixtures('config_stub', 'key_config_stub')

    @pytest.fixture
    def qbmodulepy(self, tmpdir):
        return ConfPy(tmpdir, filename="qbmodule.py")

    @pytest.fixture(autouse=True)
    def restore_sys_path(self):
        old_path = sys.path.copy()
        yield
        sys.path = old_path

    def test_bind_in_module(self, confpy, qbmodulepy, tmpdir):
        qbmodulepy.write(
            'def run(config):',
            '    config.bind(",a", "message-info foo", mode="normal")')
        confpy.write_qbmodule()
        confpy.read()
        expected = {'normal': {',a': 'message-info foo'}}
        assert config.instance.get_obj('bindings.commands') == expected
        assert "qbmodule" not in sys.modules.keys()
        assert tmpdir not in sys.path

    def test_restore_sys_on_err(self, confpy, qbmodulepy, tmpdir):
        confpy.write_qbmodule()
        qbmodulepy.write('def run(config):',
                         '    1/0')
        error = confpy.read(error=True)

        assert error.text == "Unhandled exception"
        assert isinstance(error.exception, ZeroDivisionError)
        assert "qbmodule" not in sys.modules.keys()
        assert tmpdir not in sys.path

    def test_fail_on_nonexistent_module(self, confpy, qbmodulepy, tmpdir):
        qbmodulepy.write('def run(config):',
                         '    pass')
        confpy.write('import foobar',
                     'foobar.run(config)')

        error = confpy.read(error=True)

        assert error.text == "Unhandled exception"
        assert isinstance(error.exception, ImportError)

        tblines = error.traceback.strip().splitlines()
        assert tblines[0] == "Traceback (most recent call last):"
        assert tblines[-1].endswith("Error: No module named 'foobar'")

    def test_no_double_if_path_exists(self, confpy, qbmodulepy, tmpdir):
        sys.path.insert(0, tmpdir)
        confpy.write('import sys',
                     'if sys.path[0] in sys.path[1:]:',
                     '    raise Exception("Path not expected")')
        confpy.read()
        assert sys.path.count(tmpdir) == 1


class TestConfigPy:

    """Tests for ConfigAPI and read_config_py()."""

    pytestmark = pytest.mark.usefixtures('config_stub', 'key_config_stub')

    def test_assertions(self, confpy):
        """Make sure assertions in config.py work for these tests."""
        confpy.write('assert False')
        with pytest.raises(AssertionError):
            confpy.read()  # no errors=True so it gets raised

    @pytest.mark.parametrize('what', ['configdir', 'datadir'])
    def test_getting_dirs(self, confpy, what):
        confpy.write('import pathlib',
                     'directory = config.{}'.format(what),
                     'assert isinstance(directory, pathlib.Path)',
                     'assert directory.exists()')
        confpy.read()

    @pytest.mark.parametrize('line', [
        'c.colors.hints.bg = "red"',
        'config.set("colors.hints.bg", "red")',
        'config.set("colors.hints.bg", "red", pattern=None)',
    ])
    def test_set(self, confpy, line):
        confpy.write(line)
        confpy.read()
        assert config.instance.get_obj('colors.hints.bg') == 'red'

    @pytest.mark.parametrize('template', [
        "config.set({opt!r}, False, {pattern!r})",
        "with config.pattern({pattern!r}) as p: p.{opt} = False",
    ])
    def test_set_with_pattern(self, confpy, template):
        option = 'content.javascript.enabled'
        pattern = 'https://www.example.com/'

        confpy.write(template.format(opt=option, pattern=pattern))
        confpy.read()

        assert config.instance.get_obj(option)
        assert not config.instance.get_obj_for_pattern(
            option, pattern=urlmatch.UrlPattern(pattern))

    def test_set_context_manager_global(self, confpy):
        """When "with config.pattern" is used, "c." should still be global."""
        option = 'content.javascript.enabled'
        confpy.write('with config.pattern("https://www.example.com/") as p:'
                     '    c.{} = False'.format(option))
        confpy.read()
        assert not config.instance.get_obj(option)

    @pytest.mark.parametrize('set_first', [True, False])
    @pytest.mark.parametrize('get_line', [
        'c.colors.hints.fg',
        'config.get("colors.hints.fg")',
        'config.get("colors.hints.fg", pattern=None)',
    ])
    def test_get(self, confpy, set_first, get_line):
        """Test whether getting options works correctly."""
        # pylint: disable=bad-config-option
        config.val.colors.hints.fg = 'green'
        # pylint: enable=bad-config-option
        if set_first:
            confpy.write('c.colors.hints.fg = "red"',
                         'assert {} == "red"'.format(get_line))
        else:
            confpy.write('assert {} == "green"'.format(get_line))
        confpy.read()

    def test_get_with_pattern(self, confpy):
        """Test whether we get a matching value with a pattern."""
        option = 'content.javascript.enabled'
        pattern = 'https://www.example.com/'
        config.instance.set_obj(option, False,
                                pattern=urlmatch.UrlPattern(pattern))
        confpy.write('assert config.get({!r})'.format(option),
                     'assert not config.get({!r}, pattern={!r})'
                     .format(option, pattern))
        confpy.read()

    def test_get_with_pattern_no_match(self, confpy):
        confpy.write(
            'val = config.get("content.images", "https://www.example.com")',
            'assert val is True',
        )
        confpy.read()

    @pytest.mark.parametrize('line, mode', [
        ('config.bind(",a", "message-info foo")', 'normal'),
        ('config.bind(",a", "message-info foo", "prompt")', 'prompt'),
    ])
    def test_bind(self, confpy, line, mode):
        confpy.write(line)
        confpy.read()
        expected = {mode: {',a': 'message-info foo'}}
        assert config.instance.get_obj('bindings.commands') == expected

    def test_bind_freshly_defined_alias(self, confpy):
        """Make sure we can bind to a new alias.

        https://github.com/qutebrowser/qutebrowser/issues/3001
        """
        confpy.write("c.aliases['foo'] = 'message-info foo'",
                     "config.bind(',f', 'foo')")
        confpy.read()

    def test_bind_duplicate_key(self, confpy):
        """Make sure overriding a keybinding works."""
        confpy.write("config.bind('H', 'message-info back')")
        confpy.read()
        expected = {'normal': {'H': 'message-info back'}}
        assert config.instance.get_obj('bindings.commands') == expected

    def test_bind_nop(self, confpy):
        confpy.write("c.bindings.commands = None",
                     "config.bind(',x', 'nop')")
        confpy.read()
        expected = {'normal': {',x': 'nop'}}
        assert config.instance.get_obj('bindings.commands') == expected

    def test_bind_none(self, confpy):
        confpy.write("config.bind('<Ctrl+q>', None)")
        with pytest.raises(configexc.ConfigFileErrors) as excinfo:
            confpy.read()

        assert not config.instance.get_obj('bindings.commands')

        msg = ("While binding '<Ctrl+q>': Can't bind <Ctrl+q> to None "
               "(maybe you want to use config.unbind('<Ctrl+q>') instead?)")
        assert len(excinfo.value.errors) == 1
        assert str(excinfo.value.errors[0]) == msg

    @pytest.mark.parametrize('line, key, mode', [
        ('config.unbind("o")', 'o', 'normal'),
        ('config.unbind("y", mode="yesno")', 'y', 'yesno'),
    ])
    def test_unbind(self, confpy, line, key, mode):
        confpy.write(line)
        confpy.read()
        expected = {mode: {key: None}}
        assert config.instance.get_obj('bindings.commands') == expected

    def test_mutating(self, confpy):
        confpy.write('c.aliases["foo"] = "message-info foo"',
                     'c.aliases["bar"] = "message-info bar"')
        confpy.read()
        assert config.instance.get_obj('aliases')['foo'] == 'message-info foo'
        assert config.instance.get_obj('aliases')['bar'] == 'message-info bar'

    @pytest.mark.parametrize('option, value', [
        ('content.user_stylesheets', 'style.css'),
        ('url.start_pages', 'https://www.python.org/'),
    ])
    def test_appending(self, config_tmpdir, confpy, option, value):
        """Test appending an item to some special list types.

        See https://github.com/qutebrowser/qutebrowser/issues/3104
        """
        (config_tmpdir / 'style.css').ensure()
        confpy.write('c.{}.append("{}")'.format(option, value))
        confpy.read()
        assert config.instance.get_obj(option)[-1] == value

    def test_oserror(self, tmpdir, data_tmpdir, config_tmpdir):
        with pytest.raises(configexc.ConfigFileErrors) as excinfo:
            configfiles.read_config_py(str(tmpdir / 'foo'))

        assert len(excinfo.value.errors) == 1
        error = excinfo.value.errors[0]
        assert isinstance(error.exception, OSError)
        assert error.text == "Error while reading foo"
        assert error.traceback is None

    def test_nul_bytes(self, confpy):
        confpy.write('\0')
        with pytest.raises(configexc.ConfigFileErrors) as excinfo:
            configfiles.read_config_py(confpy.filename)

        assert len(excinfo.value.errors) == 1
        error = excinfo.value.errors[0]
        assert isinstance(error.exception, ValueError)
        assert error.text == "Error while compiling"
        exception_text = 'source code string cannot contain null bytes'
        assert str(error.exception) == exception_text
        assert error.traceback is None

    def test_syntax_error(self, confpy):
        confpy.write('+')
        with pytest.raises(configexc.ConfigFileErrors) as excinfo:
            configfiles.read_config_py(confpy.filename)

        assert len(excinfo.value.errors) == 1
        error = excinfo.value.errors[0]
        assert isinstance(error.exception, SyntaxError)
        assert error.text == "Unhandled exception"
        exception_text = 'invalid syntax (config.py, line 1)'
        assert str(error.exception) == exception_text

        tblines = error.traceback.strip().splitlines()
        assert tblines[0] == "Traceback (most recent call last):"
        assert tblines[-1] == "SyntaxError: invalid syntax"
        assert "    +" in tblines
        # Starting with the new PEG-based parser in Python 3.9, the caret
        # points at the location *after* the +
        assert "    ^" in tblines or "     ^" in tblines

    def test_unhandled_exception(self, confpy):
        confpy.write("1/0")
        error = confpy.read(error=True)

        assert error.text == "Unhandled exception"
        assert isinstance(error.exception, ZeroDivisionError)

        tblines = error.traceback.strip().splitlines()
        assert tblines[0] == "Traceback (most recent call last):"
        assert tblines[-1] == "ZeroDivisionError: division by zero"
        assert "    1/0" in tblines

    def test_config_val(self, confpy):
        """Using config.val should not work in config.py files."""
        confpy.write("config.val.colors.hints.bg = 'red'")
        error = confpy.read(error=True)

        assert error.text == "Unhandled exception"
        assert isinstance(error.exception, AttributeError)
        message = "'ConfigAPI' object has no attribute 'val'"
        assert str(error.exception) == message

    @pytest.mark.parametrize('line', [
        'config.bind("<blub>", "nop")',
        'config.bind("\U00010000", "nop")',
        'config.unbind("<blub>")',
        'config.unbind("\U00010000")',
    ])
    def test_invalid_keys(self, confpy, line):
        confpy.write(line)
        error = confpy.read(error=True)
        assert error.text.endswith("and parsing key")
        assert isinstance(error.exception, keyutils.KeyParseError)
        assert str(error.exception).startswith("Could not parse")
        assert str(error.exception).endswith("Got invalid key!")

    @pytest.mark.parametrize('line', ["c.foo = 42", "config.set('foo', 42)"])
    def test_config_error(self, confpy, line):
        confpy.write(line)
        error = confpy.read(error=True)

        assert error.text == "While setting 'foo'"
        assert isinstance(error.exception, configexc.NoOptionError)
        assert str(error.exception) == "No option 'foo'"
        assert error.traceback is None

    def test_renamed_option_error(self, confpy, monkeypatch):
        """Setting an option which has been renamed should show a hint."""
        monkeypatch.setattr(configdata.MIGRATIONS, 'renamed',
                            {'qt_args': 'qt.args'})
        confpy.write('c.qt_args = ["foo"]')

        error = confpy.read(error=True)
        assert isinstance(error.exception, configexc.NoOptionError)
        expected = ("No option 'qt_args' (this option was renamed to "
                    "'qt.args')")
        assert str(error.exception) == expected

    @pytest.mark.parametrize('line, text', [
        ('config.get("content.images", "http://")',
         "While getting 'content.images' and parsing pattern"),
        ('config.set("content.images", False, "http://")',
         "While setting 'content.images' and parsing pattern"),
        ('with config.pattern("http://"): pass',
         "Unhandled exception"),
    ])
    def test_invalid_pattern(self, confpy, line, text):
        confpy.write(line)
        error = confpy.read(error=True)

        assert error.text == text
        assert isinstance(error.exception, urlmatch.ParseError)
        assert str(error.exception) == "Pattern without host"

    def test_multiple_errors(self, confpy):
        confpy.write("c.foo = 42", "config.set('foo', 42)", "1/0")

        with pytest.raises(configexc.ConfigFileErrors) as excinfo:
            configfiles.read_config_py(confpy.filename)

        errors = excinfo.value.errors
        assert len(errors) == 3

        for error in errors[:2]:
            assert error.text == "While setting 'foo'"
            assert isinstance(error.exception, configexc.NoOptionError)
            assert str(error.exception) == "No option 'foo'"
            assert error.traceback is None

        error = errors[2]
        assert error.text == "Unhandled exception"
        assert isinstance(error.exception, ZeroDivisionError)
        assert error.traceback is not None

    @pytest.mark.parametrize('location', ['abs', 'rel'])
    def test_source(self, tmpdir, confpy, location):
        if location == 'abs':
            subfile = tmpdir / 'subfile.py'
            arg = str(subfile)
        else:
            subfile = tmpdir / 'config' / 'subfile.py'
            arg = 'subfile.py'

        subfile.write_text("c.content.javascript.enabled = False",
                           encoding='utf-8')
        confpy.write("config.source({!r})".format(arg))
        confpy.read()

        assert not config.instance.get_obj('content.javascript.enabled')

    def test_source_errors(self, tmpdir, confpy):
        subfile = tmpdir / 'config' / 'subfile.py'
        subfile.write_text("c.foo = 42", encoding='utf-8')
        confpy.write("config.source('subfile.py')")
        error = confpy.read(error=True)

        assert error.text == "While setting 'foo'"
        assert isinstance(error.exception, configexc.NoOptionError)

    def test_source_multiple_errors(self, tmpdir, confpy):
        subfile = tmpdir / 'config' / 'subfile.py'
        subfile.write_text("c.foo = 42", encoding='utf-8')
        confpy.write("config.source('subfile.py')", "c.bar = 23")

        with pytest.raises(configexc.ConfigFileErrors) as excinfo:
            configfiles.read_config_py(confpy.filename)

        errors = excinfo.value.errors
        assert len(errors) == 2

        for error in errors:
            assert isinstance(error.exception, configexc.NoOptionError)

    def test_source_not_found(self, confpy):
        confpy.write("config.source('doesnotexist.py')")
        error = confpy.read(error=True)

        assert error.text == "Error while reading doesnotexist.py"
        assert isinstance(error.exception, FileNotFoundError)


class TestConfigPyWriter:

    def test_output(self):
        desc = ("This is an option description.\n\n"
                "Nullam eu ante vel est convallis dignissim. Fusce suscipit, "
                "wisi nec facilisis facilisis, est dui fermentum leo, quis "
                "tempor ligula erat quis odio.")
        opt = configdata.Option(
            name='opt', typ=configtypes.Int(), default='def',
            backends=[usertypes.Backend.QtWebEngine], raw_backends=None,
            description=desc)
        options = [(None, opt, 'val')]
        bindings = {'normal': {',x': 'message-info normal'},
                    'caret': {',y': 'message-info caret'}}

        writer = configfiles.ConfigPyWriter(options, bindings, commented=False)
        text = '\n'.join(writer._gen_lines())

        assert text == textwrap.dedent("""
            # Autogenerated config.py
            # Documentation:
            #   qute://help/configuring.html
            #   qute://help/settings.html

            # Uncomment this to still load settings configured via autoconfig.yml
            # config.load_autoconfig()

            # This is an option description.  Nullam eu ante vel est convallis
            # dignissim. Fusce suscipit, wisi nec facilisis facilisis, est dui
            # fermentum leo, quis tempor ligula erat quis odio.
            # Type: Int
            c.opt = 'val'

            # Bindings for normal mode
            config.bind(',x', 'message-info normal')

            # Bindings for caret mode
            config.bind(',y', 'message-info caret', mode='caret')
        """).lstrip()

    def test_binding_options_hidden(self):
        opt1 = configdata.DATA['bindings.default']
        opt2 = configdata.DATA['bindings.commands']
        options = [(None, opt1, {'normal': {'x': 'message-info x'}}),
                   (None, opt2, {})]
        writer = configfiles.ConfigPyWriter(options, bindings={},
                                            commented=False)
        text = '\n'.join(writer._gen_lines())
        assert 'bindings.default' not in text
        assert 'bindings.commands' not in text

    def test_unbind(self):
        bindings = {'normal': {',x': None},
                    'caret': {',y': 'message-info caret', ',z': None}}

        writer = configfiles.ConfigPyWriter([], bindings, commented=False)
        lines = list(writer._gen_lines())

        assert "config.unbind(',x')" in lines
        assert "config.unbind(',z', mode='caret')" in lines
        caret_bind = ("config.bind(',y', 'message-info caret', "
                      "mode='caret')")
        assert caret_bind in lines

    def test_commented(self):
        opt = configdata.Option(
            name='opt', typ=configtypes.Int(), default='def',
            backends=[usertypes.Backend.QtWebEngine], raw_backends=None,
            description='Hello World')
        options = [(None, opt, 'val')]
        bindings = {'normal': {',x': 'message-info normal'},
                    'caret': {',y': 'message-info caret'}}

        writer = configfiles.ConfigPyWriter(options, bindings, commented=True)
        lines = list(writer._gen_lines())

        assert "## Autogenerated config.py" in lines
        assert "# config.load_autoconfig()" in lines
        assert "# c.opt = 'val'" in lines
        assert "## Bindings for normal mode" in lines
        assert "# config.bind(',x', 'message-info normal')" in lines
        caret_bind = ("# config.bind(',y', 'message-info caret', "
                      "mode='caret')")
        assert caret_bind in lines

    def test_valid_values(self):
        opt1 = configdata.Option(
            name='opt1', typ=configtypes.BoolAsk(), default='ask',
            backends=[usertypes.Backend.QtWebEngine], raw_backends=None,
            description='Hello World')
        opt2 = configdata.Option(
            name='opt2', typ=configtypes.ColorSystem(), default='rgb',
            backends=[usertypes.Backend.QtWebEngine], raw_backends=None,
            description='All colors are beautiful!')

        options = [(None, opt1, 'ask'), (None, opt2, 'rgb')]

        writer = configfiles.ConfigPyWriter(options, bindings={},
                                            commented=False)
        text = '\n'.join(writer._gen_lines())

        expected = textwrap.dedent("""
            # Hello World
            # Type: BoolAsk
            # Valid values:
            #   - true
            #   - false
            #   - ask
            c.opt1 = 'ask'

            # All colors are beautiful!
            # Type: ColorSystem
            # Valid values:
            #   - rgb: Interpolate in the RGB color system.
            #   - hsv: Interpolate in the HSV color system.
            #   - hsl: Interpolate in the HSL color system.
            #   - none: Don't show a gradient.
            c.opt2 = 'rgb'
        """)
        assert expected in text

    def test_empty(self):
        writer = configfiles.ConfigPyWriter(options=[], bindings={},
                                            commented=False)
        text = '\n'.join(writer._gen_lines())
        expected = textwrap.dedent("""
            # Autogenerated config.py
            # Documentation:
            #   qute://help/configuring.html
            #   qute://help/settings.html

            # Uncomment this to still load settings configured via autoconfig.yml
            # config.load_autoconfig()
        """).lstrip()
        assert text == expected

    def test_pattern(self):
        opt = configdata.Option(
            name='opt', typ=configtypes.BoolAsk(), default='ask',
            backends=[usertypes.Backend.QtWebEngine], raw_backends=None,
            description='Hello World')
        options = [
            (urlmatch.UrlPattern('https://www.example.com/'), opt, 'ask'),
        ]
        writer = configfiles.ConfigPyWriter(options=options, bindings={},
                                            commented=False)
        text = '\n'.join(writer._gen_lines())
        expected = "config.set('opt', 'ask', 'https://www.example.com/')"
        assert expected in text

    def test_write(self, tmpdir):
        pyfile = tmpdir / 'config.py'
        writer = configfiles.ConfigPyWriter(options=[], bindings={},
                                            commented=False)
        writer.write(str(pyfile))
        lines = pyfile.read_text('utf-8').splitlines()
        assert '# Autogenerated config.py' in lines

    def test_defaults_work(self, confpy):
        """Get a config.py with default values and run it."""
        options = [(None, opt, opt.default)
                   for _name, opt in sorted(configdata.DATA.items())]
        bindings = dict(configdata.DATA['bindings.default'].default)
        writer = configfiles.ConfigPyWriter(options, bindings, commented=False)
        writer.write(confpy.filename)

        try:
            configfiles.read_config_py(confpy.filename)
        except configexc.ConfigFileErrors as exc:
            # Make sure no other errors happened
            for error in exc.errors:
                assert isinstance(error.exception, configexc.BackendError)


@pytest.fixture
def init_patch(qapp, fake_save_manager, config_tmpdir, data_tmpdir,
               config_stub, monkeypatch):
    monkeypatch.setattr(configfiles, 'state', None)
    yield


def test_init(init_patch, config_tmpdir):
    configfiles.init()

    # Make sure qsettings land in a subdir
    if utils.is_linux:
        settings = QSettings()
        settings.setValue("hello", "world")
        settings.sync()
        assert (config_tmpdir / 'qsettings').exists()

    # Lots of other stuff is tested in test_configinit.py
