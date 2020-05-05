# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Commands related to the configuration."""

import typing
import os.path
import contextlib

from PyQt5.QtCore import QUrl

from qutebrowser.api import cmdutils
from qutebrowser.completion.models import configmodel
from qutebrowser.utils import objreg, message, standarddir, urlmatch
from qutebrowser.config import configtypes, configexc, configfiles, configdata
from qutebrowser.misc import editor
from qutebrowser.keyinput import keyutils

if typing.TYPE_CHECKING:
    from qutebrowser.config.config import Config, KeyConfig


class ConfigCommands:

    """qutebrowser commands related to the configuration."""

    def __init__(self,
                 config: 'Config',
                 keyconfig: 'KeyConfig') -> None:
        self._config = config
        self._keyconfig = keyconfig

    @contextlib.contextmanager
    def _handle_config_error(self) -> typing.Iterator[None]:
        """Catch errors in set_command and raise CommandError."""
        try:
            yield
        except configexc.Error as e:
            raise cmdutils.CommandError(str(e))

    def _parse_pattern(
            self,
            pattern: typing.Optional[str]
    ) -> typing.Optional[urlmatch.UrlPattern]:
        """Parse a pattern string argument to a pattern."""
        if pattern is None:
            return None

        try:
            return urlmatch.UrlPattern(pattern)
        except urlmatch.ParseError as e:
            raise cmdutils.CommandError("Error while parsing {}: {}"
                                        .format(pattern, str(e)))

    def _parse_key(self, key: str) -> keyutils.KeySequence:
        """Parse a key argument."""
        try:
            return keyutils.KeySequence.parse(key)
        except keyutils.KeyParseError as e:
            raise cmdutils.CommandError(str(e))

    def _print_value(self, option: str,
                     pattern: typing.Optional[urlmatch.UrlPattern]) -> None:
        """Print the value of the given option."""
        with self._handle_config_error():
            value = self._config.get_str(option, pattern=pattern)

        text = "{} = {}".format(option, value)
        if pattern is not None:
            text += " for {}".format(pattern)
        message.info(text)

    @cmdutils.register(instance='config-commands')
    @cmdutils.argument('option', completion=configmodel.option)
    @cmdutils.argument('value', completion=configmodel.value)
    @cmdutils.argument('win_id', value=cmdutils.Value.win_id)
    @cmdutils.argument('pattern', flag='u')
    def set(self, win_id: int, option: str = None, value: str = None,
            temp: bool = False, print_: bool = False,
            *, pattern: str = None) -> None:
        """Set an option.

        If the option name ends with '?' or no value is provided, the
        value of the option is shown instead.

        Using :set without any arguments opens a page where settings can be
        changed interactively.

        Args:
            option: The name of the option.
            value: The value to set.
            pattern: The URL pattern to use.
            temp: Set value temporarily until qutebrowser is closed.
            print_: Print the value after setting.
        """
        if option is None:
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=win_id)
            tabbed_browser.load_url(QUrl('qute://settings'), newtab=False)
            return

        if option.endswith('!'):
            raise cmdutils.CommandError("Toggling values was moved to the "
                                        ":config-cycle command")

        parsed_pattern = self._parse_pattern(pattern)

        if option.endswith('?') and option != '?':
            self._print_value(option[:-1], pattern=parsed_pattern)
            return

        with self._handle_config_error():
            if value is None:
                self._print_value(option, pattern=parsed_pattern)
            else:
                self._config.set_str(option, value, pattern=parsed_pattern,
                                     save_yaml=not temp)

        if print_:
            self._print_value(option, pattern=parsed_pattern)

    @cmdutils.register(instance='config-commands', maxsplit=1,
                       no_cmd_split=True, no_replace_variables=True)
    @cmdutils.argument('command', completion=configmodel.bind)
    @cmdutils.argument('win_id', value=cmdutils.Value.win_id)
    def bind(self, win_id: str, key: str = None, command: str = None, *,
             mode: str = 'normal', default: bool = False) -> None:
        """Bind a key to a command.

        If no command is given, show the current binding for the given key.
        Using :bind without any arguments opens a page showing all keybindings.

        Args:
            key: The keychain to bind. Examples of valid keychains are `gC`,
                 `<Ctrl-X>` or `<Ctrl-C>a`.
            command: The command to execute, with optional args.
            mode: The mode to bind the key in (default: `normal`). See `:help
                  bindings.commands` for the available modes.
            default: If given, restore a default binding.
        """
        if key is None:
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=win_id)
            tabbed_browser.load_url(QUrl('qute://bindings'), newtab=True)
            return

        seq = self._parse_key(key)

        if command is None:
            if default:
                # :bind --default: Restore default
                with self._handle_config_error():
                    self._keyconfig.bind_default(seq, mode=mode,
                                                 save_yaml=True)
                return

            # No --default -> print binding
            with self._handle_config_error():
                cmd = self._keyconfig.get_command(seq, mode)
            if cmd is None:
                message.info("{} is unbound in {} mode".format(seq, mode))
            else:
                message.info("{} is bound to '{}' in {} mode".format(
                    seq, cmd, mode))
            return

        with self._handle_config_error():
            self._keyconfig.bind(seq, command, mode=mode, save_yaml=True)

    @cmdutils.register(instance='config-commands')
    def unbind(self, key: str, *, mode: str = 'normal') -> None:
        """Unbind a keychain.

        Args:
            key: The keychain to unbind. See the help for `:bind` for the
                  correct syntax for keychains.
            mode: The mode to unbind the key in (default: `normal`).
                  See `:help bindings.commands` for the available modes.
        """
        with self._handle_config_error():
            self._keyconfig.unbind(self._parse_key(key), mode=mode,
                                   save_yaml=True)

    @cmdutils.register(instance='config-commands', star_args_optional=True)
    @cmdutils.argument('option', completion=configmodel.option)
    @cmdutils.argument('values', completion=configmodel.value)
    @cmdutils.argument('pattern', flag='u')
    def config_cycle(self, option: str, *values: str,
                     pattern: str = None,
                     temp: bool = False, print_: bool = False) -> None:
        """Cycle an option between multiple values.

        Args:
            option: The name of the option.
            values: The values to cycle through.
            pattern: The URL pattern to use.
            temp: Set value temporarily until qutebrowser is closed.
            print_: Print the value after setting.
        """
        parsed_pattern = self._parse_pattern(pattern)

        with self._handle_config_error():
            opt = self._config.get_opt(option)
            old_value = self._config.get_obj_for_pattern(
                option, pattern=parsed_pattern)

        if not values and isinstance(opt.typ, configtypes.Bool):
            values = ('true', 'false')

        if len(values) < 2:
            raise cmdutils.CommandError("Need at least two values for "
                                        "non-boolean settings.")

        # Use the next valid value from values, or the first if the current
        # value does not appear in the list
        with self._handle_config_error():
            cycle_values = [opt.typ.from_str(val) for val in values]

        try:
            idx = cycle_values.index(old_value)
            idx = (idx + 1) % len(cycle_values)
            value = cycle_values[idx]
        except ValueError:
            value = cycle_values[0]

        with self._handle_config_error():
            self._config.set_obj(option, value, pattern=parsed_pattern,
                                 save_yaml=not temp)

        if print_:
            self._print_value(option, pattern=parsed_pattern)

    @cmdutils.register(instance='config-commands')
    @cmdutils.argument('option', completion=configmodel.customized_option)
    def config_unset(self, option: str, temp: bool = False) -> None:
        """Unset an option.

        This sets an option back to its default and removes it from
        autoconfig.yml.

        Args:
            option: The name of the option.
            temp: Set value temporarily until qutebrowser is closed.
        """
        with self._handle_config_error():
            self._config.unset(option, save_yaml=not temp)

    @cmdutils.register(instance='config-commands')
    @cmdutils.argument('win_id', value=cmdutils.Value.win_id)
    def config_diff(self, win_id: int, old: bool = False) -> None:
        """Show all customized options.

        Args:
            old: Show difference for the pre-v1.0 files
                 (qutebrowser.conf/keys.conf).
        """
        url = QUrl('qute://configdiff')
        if old:
            url.setPath('/old')

        tabbed_browser = objreg.get('tabbed-browser',
                                    scope='window', window=win_id)
        tabbed_browser.load_url(url, newtab=False)

    @cmdutils.register(instance='config-commands')
    @cmdutils.argument('option', completion=configmodel.list_option)
    def config_list_add(self, option: str, value: str,
                        temp: bool = False) -> None:
        """Append a value to a config option that is a list.

        Args:
            option: The name of the option.
            value: The value to append to the end of the list.
            temp: Add value temporarily until qutebrowser is closed.
        """
        with self._handle_config_error():
            opt = self._config.get_opt(option)
        valid_list_types = (configtypes.List, configtypes.ListOrValue)
        if not isinstance(opt.typ, valid_list_types):
            raise cmdutils.CommandError(":config-list-add can only be used "
                                        "for lists")

        with self._handle_config_error():
            option_value = self._config.get_mutable_obj(option)
            option_value.append(value)
            self._config.update_mutables(save_yaml=not temp)

    @cmdutils.register(instance='config-commands')
    @cmdutils.argument('option', completion=configmodel.dict_option)
    def config_dict_add(self, option: str, key: str, value: str,
                        temp: bool = False, replace: bool = False) -> None:
        """Add a key/value pair to a dictionary option.

        Args:
            option: The name of the option.
            key: The key to use.
            value: The value to place in the dictionary.
            temp: Add value temporarily until qutebrowser is closed.
            replace: Replace existing values. By default, existing values are
                     not overwritten.
        """
        with self._handle_config_error():
            opt = self._config.get_opt(option)
        if not isinstance(opt.typ, configtypes.Dict):
            raise cmdutils.CommandError(":config-dict-add can only be used "
                                        "for dicts")

        with self._handle_config_error():
            option_value = self._config.get_mutable_obj(option)

            if key in option_value and not replace:
                raise cmdutils.CommandError("{} already exists in {} - use "
                                            "--replace to overwrite!"
                                            .format(key, option))

            option_value[key] = value
            self._config.update_mutables(save_yaml=not temp)

    @cmdutils.register(instance='config-commands')
    @cmdutils.argument('option', completion=configmodel.list_option)
    def config_list_remove(self, option: str, value: str,
                           temp: bool = False) -> None:
        """Remove a value from a list.

        Args:
            option: The name of the option.
            value: The value to remove from the list.
            temp: Remove value temporarily until qutebrowser is closed.
        """
        with self._handle_config_error():
            opt = self._config.get_opt(option)
        valid_list_types = (configtypes.List, configtypes.ListOrValue)
        if not isinstance(opt.typ, valid_list_types):
            raise cmdutils.CommandError(":config-list-remove can only be used "
                                        "for lists")

        with self._handle_config_error():
            option_value = self._config.get_mutable_obj(option)

            if value not in option_value:
                raise cmdutils.CommandError("{} is not in {}!".format(
                    value, option))

            option_value.remove(value)

            self._config.update_mutables(save_yaml=not temp)

    @cmdutils.register(instance='config-commands')
    @cmdutils.argument('option', completion=configmodel.dict_option)
    def config_dict_remove(self, option: str, key: str,
                           temp: bool = False) -> None:
        """Remove a key from a dict.

        Args:
            option: The name of the option.
            key: The key to remove from the dict.
            temp: Remove value temporarily until qutebrowser is closed.
        """
        with self._handle_config_error():
            opt = self._config.get_opt(option)
        if not isinstance(opt.typ, configtypes.Dict):
            raise cmdutils.CommandError(":config-dict-remove can only be used "
                                        "for dicts")

        with self._handle_config_error():
            option_value = self._config.get_mutable_obj(option)

            if key not in option_value:
                raise cmdutils.CommandError("{} is not in {}!".format(
                    key, option))

            del option_value[key]

            self._config.update_mutables(save_yaml=not temp)

    @cmdutils.register(instance='config-commands')
    def config_clear(self, save: bool = False) -> None:
        """Set all settings back to their default.

        Args:
            save: If given, all configuration in autoconfig.yml is also
                  removed.
        """
        self._config.clear(save_yaml=save)

    @cmdutils.register(instance='config-commands')
    def config_source(self, filename: str = None, clear: bool = False) -> None:
        """Read a config.py file.

        Args:
            filename: The file to load. If not given, loads the default
                      config.py.
            clear: Clear current settings first.
        """
        if filename is None:
            filename = standarddir.config_py()
        else:
            filename = os.path.expanduser(filename)
            if not os.path.isabs(filename):
                filename = os.path.join(standarddir.config(), filename)

        if clear:
            self.config_clear()

        try:
            configfiles.read_config_py(filename)
        except configexc.ConfigFileErrors as e:
            raise cmdutils.CommandError(e)

    @cmdutils.register(instance='config-commands')
    def config_edit(self, no_source: bool = False) -> None:
        """Open the config.py file in the editor.

        Args:
            no_source: Don't re-source the config file after editing.
        """
        def on_file_updated() -> None:
            """Source the new config when editing finished.

            This can't use cmdutils.CommandError as it's run async.
            """
            try:
                configfiles.read_config_py(filename)
            except configexc.ConfigFileErrors as e:
                message.error(str(e))

        ed = editor.ExternalEditor(watch=True, parent=self._config)
        if not no_source:
            ed.file_updated.connect(on_file_updated)

        filename = standarddir.config_py()
        ed.edit_file(filename)

    @cmdutils.register(instance='config-commands')
    def config_write_py(self, filename: str = None,
                        force: bool = False, defaults: bool = False) -> None:
        """Write the current configuration to a config.py file.

        Args:
            filename: The file to write to, or None for the default config.py.
            force: Force overwriting existing files.
            defaults: Write the defaults instead of values configured via :set.
        """
        if filename is None:
            filename = standarddir.config_py()
        else:
            if not os.path.isabs(filename):
                filename = os.path.join(standarddir.config(), filename)
            filename = os.path.expanduser(filename)

        if os.path.exists(filename) and not force:
            raise cmdutils.CommandError("{} already exists - use --force to "
                                        "overwrite!".format(filename))

        options = []  # type: typing.List
        if defaults:
            options = [(None, opt, opt.default)
                       for _name, opt in sorted(configdata.DATA.items())]
            bindings = dict(configdata.DATA['bindings.default'].default)
            commented = True
        else:
            for values in self._config:
                for scoped in values:
                    options.append((scoped.pattern, values.opt, scoped.value))
            bindings = dict(self._config.get_mutable_obj('bindings.commands'))
            commented = False

        writer = configfiles.ConfigPyWriter(options, bindings,
                                            commented=commented)
        try:
            writer.write(filename)
        except OSError as e:
            raise cmdutils.CommandError(str(e))
