# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import os.path
import contextlib

from PyQt5.QtCore import QUrl

from qutebrowser.commands import cmdexc, cmdutils
from qutebrowser.completion.models import configmodel
from qutebrowser.utils import objreg, utils, message, standarddir
from qutebrowser.config import configtypes, configexc, configfiles, configdata
from qutebrowser.misc import editor


class ConfigCommands:

    """qutebrowser commands related to the configuration."""

    def __init__(self, config, keyconfig):
        self._config = config
        self._keyconfig = keyconfig

    @contextlib.contextmanager
    def _handle_config_error(self):
        """Catch errors in set_command and raise CommandError."""
        try:
            yield
        except configexc.Error as e:
            raise cmdexc.CommandError(str(e))

    def _print_value(self, option):
        """Print the value of the given option."""
        with self._handle_config_error():
            value = self._config.get_str(option)
        message.info("{} = {}".format(option, value))

    @cmdutils.register(instance='config-commands')
    @cmdutils.argument('option', completion=configmodel.option)
    @cmdutils.argument('value', completion=configmodel.value)
    @cmdutils.argument('win_id', win_id=True)
    def set(self, win_id, option=None, value=None, temp=False, print_=False):
        """Set an option.

        If the option name ends with '?', the value of the option is shown
        instead.

        Args:
            option: The name of the option.
            value: The value to set.
            temp: Set value temporarily until qutebrowser is closed.
            print_: Print the value after setting.
        """
        if option is None:
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=win_id)
            tabbed_browser.openurl(QUrl('qute://settings'), newtab=False)
            return

        if option.endswith('!'):
            raise cmdexc.CommandError("Toggling values was moved to the "
                                      ":config-cycle command")

        if option.endswith('?') and option != '?':
            self._print_value(option[:-1])
            return

        with self._handle_config_error():
            if value is None:
                raise cmdexc.CommandError("set: The following arguments "
                                          "are required: value")
            else:
                self._config.set_str(option, value, save_yaml=not temp)

        if print_:
            self._print_value(option)

    @cmdutils.register(instance='config-commands', maxsplit=1,
                       no_cmd_split=True, no_replace_variables=True)
    @cmdutils.argument('command', completion=configmodel.bind)
    def bind(self, key, command=None, *, mode='normal', default=False):
        """Bind a key to a command.

        Args:
            key: The keychain or special key (inside `<...>`) to bind.
            command: The command to execute, with optional args, or None to
                     print the current binding.
            mode: A comma-separated list of modes to bind the key in
                  (default: `normal`). See `:help bindings.commands` for the
                  available modes.
            default: If given, restore a default binding.
        """
        if command is None:
            if default:
                # :bind --default: Restore default
                with self._handle_config_error():
                    self._keyconfig.bind_default(key, mode=mode,
                                                 save_yaml=True)
                return

            # No --default -> print binding
            if utils.is_special_key(key):
                # self._keyconfig.get_command does this, but we also need it
                # normalized for the output below
                key = utils.normalize_keystr(key)
            with self._handle_config_error():
                cmd = self._keyconfig.get_command(key, mode)
            if cmd is None:
                message.info("{} is unbound in {} mode".format(key, mode))
            else:
                message.info("{} is bound to '{}' in {} mode".format(
                    key, cmd, mode))
            return

        with self._handle_config_error():
            self._keyconfig.bind(key, command, mode=mode, save_yaml=True)

    @cmdutils.register(instance='config-commands')
    def unbind(self, key, *, mode='normal'):
        """Unbind a keychain.

        Args:
            key: The keychain or special key (inside <...>) to unbind.
            mode: A mode to unbind the key in (default: `normal`).
                  See `:help bindings.commands` for the available modes.
        """
        with self._handle_config_error():
            self._keyconfig.unbind(key, mode=mode, save_yaml=True)

    @cmdutils.register(instance='config-commands', star_args_optional=True)
    @cmdutils.argument('option', completion=configmodel.option)
    @cmdutils.argument('values', completion=configmodel.value)
    def config_cycle(self, option, *values, temp=False, print_=False):
        """Cycle an option between multiple values.

        Args:
            option: The name of the option.
            values: The values to cycle through.
            temp: Set value temporarily until qutebrowser is closed.
            print_: Print the value after setting.
        """
        with self._handle_config_error():
            opt = self._config.get_opt(option)
            old_value = self._config.get_obj(option, mutable=False)

        if not values and isinstance(opt.typ, configtypes.Bool):
            values = ['true', 'false']

        if len(values) < 2:
            raise cmdexc.CommandError("Need at least two values for "
                                      "non-boolean settings.")

        # Use the next valid value from values, or the first if the current
        # value does not appear in the list
        with self._handle_config_error():
            values = [opt.typ.from_str(val) for val in values]

        try:
            idx = values.index(old_value)
            idx = (idx + 1) % len(values)
            value = values[idx]
        except ValueError:
            value = values[0]

        with self._handle_config_error():
            self._config.set_obj(option, value, save_yaml=not temp)

        if print_:
            self._print_value(option)

    @cmdutils.register(instance='config-commands')
    @cmdutils.argument('option', completion=configmodel.customized_option)
    def config_unset(self, option, temp=False):
        """Unset an option.

        This sets an option back to its default and removes it from
        autoconfig.yml.

        Args:
            option: The name of the option.
            temp: Don't touch autoconfig.yml.
        """
        with self._handle_config_error():
            self._config.unset(option, save_yaml=not temp)

    @cmdutils.register(instance='config-commands')
    def config_clear(self, save=False):
        """Set all settings back to their default.

        Args:
            save: If given, all configuration in autoconfig.yml is also
                  removed.
        """
        self._config.clear(save_yaml=save)

    @cmdutils.register(instance='config-commands')
    def config_source(self, filename=None, clear=False):
        """Read a config.py file.

        Args:
            filename: The file to load. If not given, loads the default
                      config.py.
            clear: Clear current settings first.
        """
        if filename is None:
            filename = os.path.join(standarddir.config(), 'config.py')
        else:
            filename = os.path.expanduser(filename)

        if clear:
            self.config_clear()

        try:
            configfiles.read_config_py(filename)
        except configexc.ConfigFileErrors as e:
            raise cmdexc.CommandError(e)

    @cmdutils.register(instance='config-commands')
    def config_edit(self, no_source=False):
        """Open the config.py file in the editor.

        Args:
            no_source: Don't re-source the config file after editing.
        """
        def on_editing_finished():
            """Source the new config when editing finished.

            This can't use cmdexc.CommandError as it's run async.
            """
            try:
                configfiles.read_config_py(filename)
            except configexc.ConfigFileErrors as e:
                message.error(str(e))

        ed = editor.ExternalEditor(self._config)
        if not no_source:
            ed.editing_finished.connect(on_editing_finished)

        filename = os.path.join(standarddir.config(), 'config.py')
        ed.edit_file(filename)

    @cmdutils.register(instance='config-commands')
    def config_write_py(self, filename=None, force=False, defaults=False):
        """Write the current configuration to a config.py file.

        Args:
            filename: The file to write to, or None for the default config.py.
            force: Force overwriting existing files.
            defaults: Write the defaults instead of values configured via :set.
        """
        if filename is None:
            filename = os.path.join(standarddir.config(), 'config.py')
        else:
            filename = os.path.expanduser(filename)

        if os.path.exists(filename) and not force:
            raise cmdexc.CommandError("{} already exists - use --force to "
                                      "overwrite!".format(filename))

        if defaults:
            options = [(opt, opt.default)
                       for _name, opt in sorted(configdata.DATA.items())]
            bindings = dict(configdata.DATA['bindings.default'].default)
            commented = True
        else:
            options = list(self._config)
            bindings = dict(self._config.get_obj('bindings.commands'))
            commented = False

        writer = configfiles.ConfigPyWriter(options, bindings,
                                            commented=commented)
        try:
            writer.write(filename)
        except OSError as e:
            raise cmdexc.CommandError(str(e))
