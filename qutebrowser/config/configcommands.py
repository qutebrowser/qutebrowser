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

import contextlib

from PyQt5.QtCore import QUrl

from qutebrowser.commands import cmdexc, cmdutils
from qutebrowser.completion.models import configmodel
from qutebrowser.utils import objreg, utils, message
from qutebrowser.config import configtypes, configexc


class ConfigCommands:

    """qutebrowser commands related to the configuration."""

    def __init__(self, config, keyconfig):
        self._config = config
        self._keyconfig = keyconfig

    @cmdutils.register(instance='config-commands', star_args_optional=True)
    @cmdutils.argument('option', completion=configmodel.option)
    @cmdutils.argument('values', completion=configmodel.value)
    @cmdutils.argument('win_id', win_id=True)
    def set(self, win_id, option=None, *values, temp=False, print_=False):
        """Set an option.

        If the option name ends with '?', the value of the option is shown
        instead.

        If the option name ends with '!' and it is a boolean value, toggle it.

        Args:
            option: The name of the option.
            values: The value to set, or the values to cycle through.
            temp: Set value temporarily until qutebrowser is closed.
            print_: Print the value after setting.
        """
        if option is None:
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=win_id)
            tabbed_browser.openurl(QUrl('qute://settings'), newtab=False)
            return

        if option.endswith('?') and option != '?':
            self._print_value(option[:-1])
            return

        with self._handle_config_error():
            if option.endswith('!') and option != '!' and not values:
                # Handle inversion as special cases of the cycle code path
                option = option[:-1]
                opt = self._config.get_opt(option)
                if isinstance(opt.typ, configtypes.Bool):
                    values = ['false', 'true']
                else:
                    raise cmdexc.CommandError(
                        "set: Can't toggle non-bool setting {}".format(option))
            elif not values:
                raise cmdexc.CommandError("set: The following arguments "
                                          "are required: value")
            self._set_next(option, values, temp=temp)

        if print_:
            self._print_value(option)

    def _print_value(self, option):
        """Print the value of the given option."""
        with self._handle_config_error():
            value = self._config.get_str(option)
        message.info("{} = {}".format(option, value))

    def _set_next(self, option, values, *, temp):
        """Set the next value out of a list of values."""
        if len(values) == 1:
            # If we have only one value, just set it directly (avoid
            # breaking stuff like aliases or other pseudo-settings)
            self._config.set_str(option, values[0], save_yaml=not temp)
            return

        # Use the next valid value from values, or the first if the current
        # value does not appear in the list
        old_value = self._config.get_obj(option, mutable=False)
        opt = self._config.get_opt(option)
        values = [opt.typ.from_str(val) for val in values]

        try:
            idx = values.index(old_value)
            idx = (idx + 1) % len(values)
            value = values[idx]
        except ValueError:
            value = values[0]
        self._config.set_obj(option, value, save_yaml=not temp)

    @contextlib.contextmanager
    def _handle_config_error(self):
        """Catch errors in set_command and raise CommandError."""
        try:
            yield
        except configexc.Error as e:
            raise cmdexc.CommandError("set: {}".format(e))

    @cmdutils.register(instance='config-commands', maxsplit=1,
                       no_cmd_split=True, no_replace_variables=True)
    @cmdutils.argument('command', completion=configmodel.bind)
    def bind(self, key, command=None, *, mode='normal', force=False):
        """Bind a key to a command.

        Args:
            key: The keychain or special key (inside `<...>`) to bind.
            command: The command to execute, with optional args, or None to
                     print the current binding.
            mode: A comma-separated list of modes to bind the key in
                  (default: `normal`). See `:help bindings.commands` for the
                  available modes.
            force: Rebind the key if it is already bound.
        """
        if command is None:
            if utils.is_special_key(key):
                # self._keyconfig.get_command does this, but we also need it
                # normalized for the output below
                key = utils.normalize_keystr(key)
            cmd = self._keyconfig.get_command(key, mode)
            if cmd is None:
                message.info("{} is unbound in {} mode".format(key, mode))
            else:
                message.info("{} is bound to '{}' in {} mode".format(
                    key, cmd, mode))
            return

        try:
            self._keyconfig.bind(key, command, mode=mode, force=force,
                                 save_yaml=True)
        except configexc.DuplicateKeyError as e:
            raise cmdexc.CommandError("bind: {} - use --force to override!"
                                      .format(e))
        except configexc.KeybindingError as e:
            raise cmdexc.CommandError("bind: {}".format(e))

    @cmdutils.register(instance='config-commands')
    def unbind(self, key, *, mode='normal'):
        """Unbind a keychain.

        Args:
            key: The keychain or special key (inside <...>) to unbind.
            mode: A mode to unbind the key in (default: `normal`).
                  See `:help bindings.commands` for the available modes.
        """
        try:
            self._keyconfig.unbind(key, mode=mode, save_yaml=True)
        except configexc.KeybindingError as e:
            raise cmdexc.CommandError('unbind: {}'.format(e))
