# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
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

"""Configuration files residing on disk."""

import enum
import pathlib
import types
import os.path
import sys
import textwrap
import traceback
import configparser
import contextlib
import re
from typing import (TYPE_CHECKING, Any, Dict, Iterable, Iterator, List, Mapping,
                    MutableMapping, Optional, Tuple, cast)

import yaml
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QSettings, qVersion

import qutebrowser
from qutebrowser.config import (configexc, config, configdata, configutils,
                                configtypes)
from qutebrowser.keyinput import keyutils
from qutebrowser.utils import standarddir, utils, qtutils, log, urlmatch, version

if TYPE_CHECKING:
    from qutebrowser.misc import savemanager


# The StateConfig instance
state = cast('StateConfig', None)


_SettingsType = Dict[str, Dict[str, Any]]


class VersionChange(enum.Enum):

    """The type of version change when comparing two versions."""

    unknown = enum.auto()
    equal = enum.auto()
    downgrade = enum.auto()

    patch = enum.auto()
    minor = enum.auto()
    major = enum.auto()

    def matches_filter(self, filterstr: str) -> bool:
        """Whether the change matches a given filter.

        This is intended to use filters like "major" (show major only), "minor" (show
        major/minor) or "patch" (show all changes).
        """
        allowed_values: Dict[str, List[VersionChange]] = {
            'major': [VersionChange.major],
            'minor': [VersionChange.major, VersionChange.minor],
            'patch': [VersionChange.major, VersionChange.minor, VersionChange.patch],
            'never': [],
        }
        return self in allowed_values[filterstr]


class StateConfig(configparser.ConfigParser):

    """The "state" file saving various application state."""

    def __init__(self) -> None:
        super().__init__()
        self._filename = os.path.join(standarddir.data(), 'state')
        self.read(self._filename, encoding='utf-8')

        self.qt_version_changed = False
        self.qtwe_version_changed = False
        self.qutebrowser_version_changed = VersionChange.unknown
        self._set_changed_attributes()

        for sect in ['general', 'geometry', 'inspector']:
            try:
                self.add_section(sect)
            except configparser.DuplicateSectionError:
                pass

        deleted_keys = [
            ('general', 'fooled'),
            ('general', 'backend-warning-shown'),
            ('general', 'old-qt-warning-shown'),
            ('geometry', 'inspector'),
        ]
        for sect, key in deleted_keys:
            self[sect].pop(key, None)

        self['general']['qt_version'] = qVersion()
        self['general']['qtwe_version'] = self._qtwe_version_str()
        self['general']['version'] = qutebrowser.__version__

    def _qtwe_version_str(self) -> str:
        """Get the QtWebEngine version string.

        Note that it's too early to use objects.backend here...
        """
        try:
            import PyQt5.QtWebEngineWidgets  # pylint: disable=unused-import
        except ImportError:
            return 'no'
        return str(version.qtwebengine_versions(avoid_init=True).webengine)

    def _set_changed_attributes(self) -> None:
        """Set qt_version_changed/qutebrowser_version_changed attributes.

        We handle this here, so we can avoid setting qt_version_changed if
        the config is brand new, but can still set it when qt_version wasn't
        there before...
        """
        if 'general' not in self:
            return

        old_qt_version = self['general'].get('qt_version', None)
        self.qt_version_changed = old_qt_version != qVersion()

        old_qtwe_version = self['general'].get('qtwe_version', None)
        self.qtwe_version_changed = old_qtwe_version != self._qtwe_version_str()

        old_qutebrowser_version = self['general'].get('version', None)
        if old_qutebrowser_version is None:
            # https://github.com/python/typeshed/issues/2093
            return  # type: ignore[unreachable]

        try:
            old_version = utils.VersionNumber.parse(old_qutebrowser_version)
        except ValueError:
            log.init.warning(f"Unable to parse old version {old_qutebrowser_version}")
            return

        new_version = utils.VersionNumber.parse(qutebrowser.__version__)

        if old_version == new_version:
            self.qutebrowser_version_changed = VersionChange.equal
        elif new_version < old_version:
            self.qutebrowser_version_changed = VersionChange.downgrade
        elif old_version.segments[:2] == new_version.segments[:2]:
            self.qutebrowser_version_changed = VersionChange.patch
        elif old_version.major == new_version.major:
            self.qutebrowser_version_changed = VersionChange.minor
        else:
            self.qutebrowser_version_changed = VersionChange.major

    def init_save_manager(self,
                          save_manager: 'savemanager.SaveManager') -> None:
        """Make sure the config gets saved properly.

        We do this outside of __init__ because the config gets created before
        the save_manager exists.
        """
        save_manager.add_saveable('state-config', self._save)

    def _save(self) -> None:
        """Save the state file to the configured location."""
        with open(self._filename, 'w', encoding='utf-8') as f:
            self.write(f)


class YamlConfig(QObject):

    """A config stored on disk as YAML file.

    Class attributes:
        VERSION: The current version number of the config file.
    """

    VERSION = 2
    changed = pyqtSignal()

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)
        self._filename = os.path.join(standarddir.config(auto=True),
                                      'autoconfig.yml')
        self._dirty = False

        self._values: Dict[str, configutils.Values] = {}
        for name, opt in configdata.DATA.items():
            self._values[name] = configutils.Values(opt)

    def init_save_manager(self,
                          save_manager: 'savemanager.SaveManager') -> None:
        """Make sure the config gets saved properly.

        We do this outside of __init__ because the config gets created before
        the save_manager exists.
        """
        save_manager.add_saveable('yaml-config', self._save, self.changed)

    def __iter__(self) -> Iterator[configutils.Values]:
        """Iterate over configutils.Values items."""
        yield from self._values.values()

    @pyqtSlot()
    def _mark_changed(self) -> None:
        """Mark the YAML config as changed."""
        self._dirty = True
        self.changed.emit()

    def _save(self) -> None:
        """Save the settings to the YAML file if they've changed."""
        if not self._dirty:
            return

        settings: _SettingsType = {}
        for name, values in sorted(self._values.items()):
            if not values:
                continue
            settings[name] = {}
            for scoped in values:
                key = ('global' if scoped.pattern is None
                       else str(scoped.pattern))
                settings[name][key] = scoped.value

        data = {'config_version': self.VERSION, 'settings': settings}
        with qtutils.savefile_open(self._filename) as f:
            f.write(textwrap.dedent("""
                # If a config.py file exists, this file is ignored unless it's explicitly loaded
                # via config.load_autoconfig(). For more information, see:
                # https://github.com/qutebrowser/qutebrowser/blob/master/doc/help/configuring.asciidoc#loading-autoconfigyml
                # DO NOT edit this file by hand, qutebrowser will overwrite it.
                # Instead, create a config.py - see :help for details.

            """.lstrip('\n')))
            utils.yaml_dump(data, f)

    def _pop_object(self, yaml_data: Any, key: str, typ: type) -> Any:
        """Get a global object from the given data."""
        if not isinstance(yaml_data, dict):
            desc = configexc.ConfigErrorDesc("While loading data",
                                             "Toplevel object is not a dict")
            raise configexc.ConfigFileErrors('autoconfig.yml', [desc])

        if key not in yaml_data:
            desc = configexc.ConfigErrorDesc(
                "While loading data",
                "Toplevel object does not contain '{}' key".format(key))
            raise configexc.ConfigFileErrors('autoconfig.yml', [desc])

        data = yaml_data.pop(key)

        if not isinstance(data, typ):
            desc = configexc.ConfigErrorDesc(
                "While loading data",
                "'{}' object is not a {}".format(key, typ.__name__))
            raise configexc.ConfigFileErrors('autoconfig.yml', [desc])

        return data

    def load(self) -> None:
        """Load configuration from the configured YAML file."""
        try:
            with open(self._filename, 'r', encoding='utf-8') as f:
                yaml_data = utils.yaml_load(f)
        except FileNotFoundError:
            return
        except OSError as e:
            desc = configexc.ConfigErrorDesc("While reading", e)
            raise configexc.ConfigFileErrors('autoconfig.yml', [desc])
        except yaml.YAMLError as e:
            desc = configexc.ConfigErrorDesc("While parsing", e)
            raise configexc.ConfigFileErrors('autoconfig.yml', [desc])

        config_version = self._pop_object(yaml_data, 'config_version', int)
        if config_version == 1:
            settings = self._load_legacy_settings_object(yaml_data)
            self._mark_changed()
        elif config_version > self.VERSION:
            desc = configexc.ConfigErrorDesc(
                "While reading",
                "Can't read config from incompatible newer version")
            raise configexc.ConfigFileErrors('autoconfig.yml', [desc])
        else:
            settings = self._load_settings_object(yaml_data)
            self._dirty = False

        migrations = YamlMigrations(settings, parent=self)
        migrations.changed.connect(self._mark_changed)
        migrations.migrate()

        self._validate_names(settings)
        self._build_values(settings)

    def _load_settings_object(self, yaml_data: Any) -> _SettingsType:
        """Load the settings from the settings: key."""
        return self._pop_object(yaml_data, 'settings', dict)

    def _load_legacy_settings_object(self, yaml_data: Any) -> _SettingsType:
        data = self._pop_object(yaml_data, 'global', dict)
        settings = {}
        for name, value in data.items():
            settings[name] = {'global': value}
        return settings

    def _build_values(self, settings: Mapping[str, Any]) -> None:
        """Build up self._values from the values in the given dict."""
        errors = []
        for name, yaml_values in settings.items():
            if not isinstance(yaml_values, dict):
                errors.append(configexc.ConfigErrorDesc(
                    "While parsing {!r}".format(name), "value is not a dict"))
                continue

            values = configutils.Values(configdata.DATA[name])
            if 'global' in yaml_values:
                values.add(yaml_values.pop('global'))

            for pattern, value in yaml_values.items():
                if not isinstance(pattern, str):
                    errors.append(configexc.ConfigErrorDesc(
                        "While parsing {!r}".format(name),
                        "pattern is not of type string"))
                    continue
                try:
                    urlpattern = urlmatch.UrlPattern(pattern)
                except urlmatch.ParseError as e:
                    errors.append(configexc.ConfigErrorDesc(
                        "While parsing pattern {!r} for {!r}"
                        .format(pattern, name), e))
                    continue
                values.add(value, urlpattern)

            self._values[name] = values

        if errors:
            raise configexc.ConfigFileErrors('autoconfig.yml', errors)

    def _validate_names(self, settings: _SettingsType) -> None:
        """Make sure all settings exist."""
        unknown = []
        for name in settings:
            if name not in configdata.DATA:
                unknown.append(name)

        if unknown:
            errors = [configexc.ConfigErrorDesc("While loading options",
                                                "Unknown option {}".format(e))
                      for e in sorted(unknown)]
            raise configexc.ConfigFileErrors('autoconfig.yml', errors)

    def set_obj(self, name: str, value: Any, *,
                pattern: urlmatch.UrlPattern = None) -> None:
        """Set the given setting to the given value."""
        self._values[name].add(value, pattern)
        self._mark_changed()

    def unset(self, name: str, *, pattern: urlmatch.UrlPattern = None) -> None:
        """Remove the given option name if it's configured."""
        changed = self._values[name].remove(pattern)
        if changed:
            self._mark_changed()

    def clear(self) -> None:
        """Clear all values from the YAML file."""
        for values in self._values.values():
            values.clear()
        self._mark_changed()


class YamlMigrations(QObject):

    """Automated migrations for autoconfig.yml."""

    changed = pyqtSignal()

    def __init__(self, settings: _SettingsType,
                 parent: QObject = None) -> None:
        super().__init__(parent)
        self._settings = settings

    def migrate(self) -> None:
        """Migrate older configs to the newest format."""
        self._migrate_configdata()
        self._migrate_bindings_default()
        self._migrate_font_default_family()
        self._migrate_font_replacements()

        self._migrate_bool('tabs.favicons.show', 'always', 'never')
        self._migrate_bool('scrolling.bar', 'always', 'overlay')
        self._migrate_bool('qt.force_software_rendering',
                           'software-opengl', 'none')
        self._migrate_renamed_bool(
            old_name='content.webrtc_public_interfaces_only',
            new_name='content.webrtc_ip_handling_policy',
            true_value='default-public-interface-only',
            false_value='all-interfaces')
        self._migrate_renamed_bool(
            old_name='tabs.persist_mode_on_change',
            new_name='tabs.mode_on_change',
            true_value='persist',
            false_value='normal')
        self._migrate_renamed_bool(
            old_name='statusbar.hide',
            new_name='statusbar.show',
            true_value='never',
            false_value='always')
        self._migrate_renamed_bool(
            old_name='content.ssl_strict',
            new_name='content.tls.certificate_errors',
            true_value='block',
            false_value='load-insecurely',
            ask_value='ask',
        )

        for setting in ['colors.webpage.force_dark_color_scheme',
                        'colors.webpage.prefers_color_scheme_dark']:
            self._migrate_renamed_bool(
                old_name=setting,
                new_name='colors.webpage.preferred_color_scheme',
                true_value='dark',
                false_value='auto',
            )

        for setting in ['tabs.title.format',
                        'tabs.title.format_pinned',
                        'window.title_format']:
            self._migrate_string_value(setting,
                                       r'(?<!{)\{title\}(?!})',
                                       r'{current_title}')

        self._migrate_to_multiple('fonts.tabs',
                                  ('fonts.tabs.selected',
                                   'fonts.tabs.unselected'))

        self._migrate_to_multiple('content.media_capture',
                                  ('content.media.audio_capture',
                                   'content.media.audio_video_capture',
                                   'content.media.video_capture'))

        # content.headers.user_agent can't be empty to get the default anymore.
        setting = 'content.headers.user_agent'
        self._migrate_none(setting, configdata.DATA[setting].default)

        self._remove_empty_patterns()

    def _migrate_configdata(self) -> None:
        """Migrate simple renamed/deleted options."""
        for name in list(self._settings):
            if name in configdata.MIGRATIONS.renamed:
                new_name = configdata.MIGRATIONS.renamed[name]
                log.config.debug("Renaming {} to {}".format(name, new_name))
                self._settings[new_name] = self._settings[name]
                del self._settings[name]
                self.changed.emit()
            elif name in configdata.MIGRATIONS.deleted:
                log.config.debug("Removing {}".format(name))
                del self._settings[name]
                self.changed.emit()

    def _migrate_bindings_default(self) -> None:
        """bindings.default can't be set in autoconfig.yml anymore.

        => Ignore old values.
        """
        if 'bindings.default' not in self._settings:
            return

        del self._settings['bindings.default']
        self.changed.emit()

    def _migrate_font_default_family(self) -> None:
        old_name = 'fonts.monospace'
        new_name = 'fonts.default_family'

        if old_name not in self._settings:
            return

        old_default_fonts = (
            'Monospace, "DejaVu Sans Mono", Monaco, '
            '"Bitstream Vera Sans Mono", "Andale Mono", "Courier New", '
            'Courier, "Liberation Mono", monospace, Fixed, Consolas, Terminal'
        )

        self._settings[new_name] = {}

        for scope, val in self._settings[old_name].items():
            old_fonts = val.replace(old_default_fonts, '').rstrip(' ,')
            new_fonts = configutils.FontFamilies.from_str(old_fonts)
            self._settings[new_name][scope] = list(new_fonts)

        del self._settings[old_name]
        self.changed.emit()

    def _migrate_font_replacements(self) -> None:
        """Replace 'monospace' replacements by 'default_family'."""
        for name, values in self._settings.items():
            if not isinstance(values, dict):
                continue

            try:
                opt = configdata.DATA[name]
            except KeyError:
                continue

            if not isinstance(opt.typ, configtypes.FontBase):
                continue

            for scope, val in values.items():
                if isinstance(val, str) and val.endswith(' monospace'):
                    new_val = val.replace('monospace', 'default_family')
                    self._settings[name][scope] = new_val
                    self.changed.emit()

    def _migrate_bool(self, name: str,
                      true_value: str,
                      false_value: str) -> None:
        if name not in self._settings:
            return

        values = self._settings[name]
        if not isinstance(values, dict):
            return

        for scope, val in values.items():
            if isinstance(val, bool):
                new_value = true_value if val else false_value
                self._settings[name][scope] = new_value
                self.changed.emit()

    def _migrate_renamed_bool(self, old_name: str,
                              new_name: str,
                              true_value: str,
                              false_value: str,
                              ask_value: str = None) -> None:
        if old_name not in self._settings:
            return

        self._settings[new_name] = {}

        for scope, val in self._settings[old_name].items():
            if val == 'ask':
                assert ask_value is not None
                new_value = ask_value
            elif val:
                new_value = true_value
            else:
                new_value = false_value
            self._settings[new_name][scope] = new_value

        del self._settings[old_name]
        self.changed.emit()

    def _migrate_none(self, name: str, value: str) -> None:
        if name not in self._settings:
            return

        values = self._settings[name]
        if not isinstance(values, dict):
            return

        for scope, val in values.items():
            if val is None:
                self._settings[name][scope] = value
                self.changed.emit()

    def _migrate_to_multiple(self, old_name: str, new_names: Iterable[str]) -> None:
        if old_name not in self._settings:
            return

        for new_name in new_names:
            self._settings[new_name] = {}
            for scope, val in self._settings[old_name].items():
                self._settings[new_name][scope] = val

        del self._settings[old_name]
        self.changed.emit()

    def _migrate_string_value(self, name: str, source: str, target: str) -> None:
        if name not in self._settings:
            return

        values = self._settings[name]
        if not isinstance(values, dict):
            return

        for scope, val in values.items():
            if isinstance(val, str):
                new_val = re.sub(source, target, val)
                if new_val != val:
                    self._settings[name][scope] = new_val
                    self.changed.emit()

    def _remove_empty_patterns(self) -> None:
        """Remove *. host patterns from the config.

        Those used to be valid (and could be accidentally produced by using tSH
        on about:blank), but aren't anymore.
        """
        scope = '*://*./*'
        for name, values in self._settings.items():
            if not isinstance(values, dict):
                continue
            if scope in values:
                del self._settings[name][scope]
                self.changed.emit()


class ConfigAPI:

    """Object which gets passed to config.py as "config" object.

    This is a small wrapper over the Config object, but with more
    straightforward method names (get/set call get_obj/set_obj) and a more
    shallow API.

    Attributes:
        _config: The main Config object to use.
        _keyconfig: The KeyConfig object.
        _warn_autoconfig: Whether to warn if autoconfig.yml wasn't loaded.
        errors: Errors which occurred while setting options.
        configdir: The qutebrowser config directory, as pathlib.Path.
        datadir: The qutebrowser data directory, as pathlib.Path.
    """

    def __init__(
            self,
            conf: config.Config,
            keyconfig: config.KeyConfig,
            warn_autoconfig: bool,
    ):
        self._config = conf
        self._keyconfig = keyconfig
        self.errors: List[configexc.ConfigErrorDesc] = []
        self.configdir = pathlib.Path(standarddir.config())
        self.datadir = pathlib.Path(standarddir.data())
        self._warn_autoconfig = warn_autoconfig

    @contextlib.contextmanager
    def _handle_error(self, action: str, name: str) -> Iterator[None]:
        """Catch config-related exceptions and save them in self.errors."""
        try:
            yield
        except configexc.ConfigFileErrors as e:
            for err in e.errors:
                new_err = err.with_text(e.basename)
                self.errors.append(new_err)
        except configexc.Error as e:
            text = "While {} '{}'".format(action, name)
            self.errors.append(configexc.ConfigErrorDesc(text, e))
        except urlmatch.ParseError as e:
            text = "While {} '{}' and parsing pattern".format(action, name)
            self.errors.append(configexc.ConfigErrorDesc(text, e))
        except keyutils.KeyParseError as e:
            text = "While {} '{}' and parsing key".format(action, name)
            self.errors.append(configexc.ConfigErrorDesc(text, e))

    def finalize(self) -> None:
        """Do work which needs to be done after reading config.py."""
        if self._warn_autoconfig:
            desc = configexc.ConfigErrorDesc(
                "autoconfig loading not specified",
                ("Your config.py should call either `config.load_autoconfig()`"
                 " (to load settings configured via the GUI) or "
                 "`config.load_autoconfig(False)` (to not do so)"))
            self.errors.append(desc)
        self._config.update_mutables()

    def load_autoconfig(self, load_config: bool = True) -> None:
        """Load the autoconfig.yml file which is used for :set/:bind/etc."""
        self._warn_autoconfig = False
        if load_config:
            with self._handle_error('reading', 'autoconfig.yml'):
                read_autoconfig()

    def get(self, name: str, pattern: str = None) -> Any:
        """Get a setting value from the config, optionally with a pattern."""
        with self._handle_error('getting', name):
            urlpattern = urlmatch.UrlPattern(pattern) if pattern else None
            return self._config.get_mutable_obj(name, pattern=urlpattern)

    def set(self, name: str, value: Any, pattern: str = None) -> None:
        """Set a setting value in the config, optionally with a pattern."""
        with self._handle_error('setting', name):
            urlpattern = urlmatch.UrlPattern(pattern) if pattern else None
            self._config.set_obj(name, value, pattern=urlpattern)

    def bind(self, key: str, command: Optional[str], mode: str = 'normal') -> None:
        """Bind a key to a command, with an optional key mode."""
        with self._handle_error('binding', key):
            seq = keyutils.KeySequence.parse(key)
            if command is None:
                raise configexc.Error("Can't bind {key} to None (maybe you "
                                      "want to use config.unbind('{key}') "
                                      "instead?)".format(key=key))
            self._keyconfig.bind(seq, command, mode=mode)

    def unbind(self, key: str, mode: str = 'normal') -> None:
        """Unbind a key from a command, with an optional key mode."""
        with self._handle_error('unbinding', key):
            seq = keyutils.KeySequence.parse(key)
            self._keyconfig.unbind(seq, mode=mode)

    def source(self, filename: str) -> None:
        """Read the given config file from disk."""
        if not os.path.isabs(filename):
            # We don't use self.configdir here so we get the proper file when starting
            # with a --config-py argument given.
            filename = os.path.join(os.path.dirname(standarddir.config_py()), filename)

        try:
            read_config_py(filename)
        except configexc.ConfigFileErrors as e:
            self.errors += e.errors

    @contextlib.contextmanager
    def pattern(self, pattern: str) -> Iterator[config.ConfigContainer]:
        """Get a ConfigContainer for the given pattern."""
        # We need to propagate the exception so we don't need to return
        # something.
        urlpattern = urlmatch.UrlPattern(pattern)
        container = config.ConfigContainer(config=self._config, configapi=self,
                                           pattern=urlpattern)
        yield container


class ConfigPyWriter:

    """Writer for config.py files from given settings."""

    def __init__(
            self,
            options: List[
                Tuple[
                    Optional[urlmatch.UrlPattern],
                    configdata.Option,
                    Any
                ]
            ],
            bindings: MutableMapping[str, Mapping[str, Optional[str]]],
            *,
            commented: bool,
    ) -> None:
        self._options = options
        self._bindings = bindings
        self._commented = commented

    def write(self, filename: str) -> None:
        """Write the config to the given file."""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self._gen_lines()))

    def _line(self, line: str) -> str:
        """Get an (optionally commented) line."""
        if self._commented:
            if line.startswith('#'):
                return '#' + line
            else:
                return '# ' + line
        else:
            return line

    def _gen_lines(self) -> Iterator[str]:
        """Generate a config.py with the given settings/bindings.

        Yields individual lines.
        """
        yield from self._gen_header()
        yield from self._gen_options()
        yield from self._gen_bindings()

    def _gen_header(self) -> Iterator[str]:
        """Generate the initial header of the config."""
        yield self._line("# Autogenerated config.py")
        yield self._line("#")

        note = ("NOTE: config.py is intended for advanced users who are "
                "comfortable with manually migrating the config file on "
                "qutebrowser upgrades. If you prefer, you can also configure "
                "qutebrowser using the :set/:bind/:config-* commands without "
                "having to write a config.py file.")
        for line in textwrap.wrap(note):
            yield self._line("# {}".format(line))

        yield self._line("#")
        yield self._line("# Documentation:")
        yield self._line("#   qute://help/configuring.html")
        yield self._line("#   qute://help/settings.html")
        yield ''
        if self._commented:
            # When generated from an autoconfig.yml with commented=False,
            # we don't want to load that autoconfig.yml anymore.
            yield self._line("# This is here so configs done via the GUI are "
                             "still loaded.")
            yield self._line("# Remove it to not load settings done via the "
                             "GUI.")
            yield self._line("config.load_autoconfig(True)")
            yield ''
        else:
            yield self._line("# Change the argument to True to still load settings "
                             "configured via autoconfig.yml")
            yield self._line("config.load_autoconfig(False)")
            yield ''

    def _gen_options(self) -> Iterator[str]:
        """Generate the options part of the config."""
        for pattern, opt, value in self._options:
            if opt.name in ['bindings.commands', 'bindings.default']:
                continue

            for line in textwrap.wrap(opt.description):
                yield self._line("# {}".format(line))

            yield self._line("# Type: {}".format(opt.typ.get_name()))

            valid_values = opt.typ.get_valid_values()
            if valid_values is not None and valid_values.generate_docs:
                yield self._line("# Valid values:")
                for val in valid_values:
                    try:
                        desc = valid_values.descriptions[val]
                        yield self._line("#   - {}: {}".format(val, desc))
                    except KeyError:
                        yield self._line("#   - {}".format(val))

            if pattern is None:
                yield self._line('c.{} = {!r}'.format(opt.name, value))
            else:
                yield self._line('config.set({!r}, {!r}, {!r})'.format(
                    opt.name, value, str(pattern)))
            yield ''

    def _gen_bindings(self) -> Iterator[str]:
        """Generate the bindings part of the config."""
        normal_bindings = self._bindings.pop('normal', {})
        if normal_bindings:
            yield self._line('# Bindings for normal mode')
            for key, command in sorted(normal_bindings.items()):
                if command is None:
                    yield self._line('config.unbind({!r})'.format(key))
                else:
                    yield self._line('config.bind({!r}, {!r})'.format(
                        key, command))
            yield ''

        for mode, mode_bindings in sorted(self._bindings.items()):
            yield self._line('# Bindings for {} mode'.format(mode))
            for key, command in sorted(mode_bindings.items()):
                if command is None:
                    yield self._line('config.unbind({!r}, mode={!r})'.format(
                        key, mode))
                else:
                    yield self._line(
                        'config.bind({!r}, {!r}, mode={!r})'.format(
                            key, command, mode))
            yield ''


def read_config_py(
        filename: str,
        raising: bool = False,
        warn_autoconfig: bool = False,
) -> None:
    """Read a config.py file.

    Arguments;
        filename: The name of the file to read.
        raising: Raise exceptions happening in config.py.
                 This is needed during tests to use pytest's inspection.
        warn_autoconfig: Whether to warn if config.load_autoconfig() wasn't specified.
    """
    assert config.instance is not None
    assert config.key_instance is not None

    api = ConfigAPI(
        config.instance,
        config.key_instance,
        warn_autoconfig=warn_autoconfig,
    )
    container = config.ConfigContainer(config.instance, configapi=api)
    basename = os.path.basename(filename)

    module = types.ModuleType('config')
    module.config = api  # type: ignore[attr-defined]
    module.c = container  # type: ignore[attr-defined]
    module.__file__ = filename

    try:
        with open(filename, mode='rb') as f:
            source = f.read()
    except OSError as e:
        text = "Error while reading {}".format(basename)
        desc = configexc.ConfigErrorDesc(text, e)
        raise configexc.ConfigFileErrors(basename, [desc])

    try:
        code = compile(source, filename, 'exec')
    except ValueError as e:
        # source contains NUL bytes
        desc = configexc.ConfigErrorDesc("Error while compiling", e)
        raise configexc.ConfigFileErrors(basename, [desc])
    except SyntaxError as e:
        desc = configexc.ConfigErrorDesc("Unhandled exception", e,
                                         traceback=traceback.format_exc())
        raise configexc.ConfigFileErrors(basename, [desc])

    try:
        # Save and restore sys variables
        with saved_sys_properties():
            # Add config directory to python path, so config.py can import
            # other files in logical places
            config_dir = os.path.dirname(filename)
            if config_dir not in sys.path:
                sys.path.insert(0, config_dir)

            exec(code, module.__dict__)
    except Exception as e:
        if raising:
            raise
        api.errors.append(configexc.ConfigErrorDesc(
            "Unhandled exception",
            exception=e, traceback=traceback.format_exc()))

    api.finalize()
    config.instance.config_py_loaded = True

    if api.errors:
        raise configexc.ConfigFileErrors('config.py', api.errors)


def read_autoconfig() -> None:
    """Read the autoconfig.yml file."""
    try:
        config.instance.read_yaml()
    except configexc.ConfigFileErrors:
        raise  # caught in outer block
    except configexc.Error as e:
        desc = configexc.ConfigErrorDesc("Error", e)
        raise configexc.ConfigFileErrors('autoconfig.yml', [desc])


@contextlib.contextmanager
def saved_sys_properties() -> Iterator[None]:
    """Save various sys properties such as sys.path and sys.modules."""
    old_path = sys.path.copy()
    old_modules = sys.modules.copy()

    try:
        yield
    finally:
        sys.path = old_path
        for module in set(sys.modules).difference(old_modules):
            del sys.modules[module]


def init() -> None:
    """Initialize config storage not related to the main config."""
    global state

    try:
        state = StateConfig()
    except (configparser.Error, UnicodeDecodeError) as e:
        msg = "While loading state file from {}".format(standarddir.data())
        desc = configexc.ConfigErrorDesc(msg, e)
        raise configexc.ConfigFileErrors('state', [desc], fatal=True)

    # Set the QSettings path to something like
    # ~/.config/qutebrowser/qsettings/qutebrowser/qutebrowser.conf so it
    # doesn't overwrite our config.
    #
    # This fixes one of the corruption issues here:
    # https://github.com/qutebrowser/qutebrowser/issues/515

    path = os.path.join(standarddir.config(auto=True), 'qsettings')
    for fmt in [QSettings.NativeFormat, QSettings.IniFormat]:
        QSettings.setPath(fmt, QSettings.UserScope, path)
