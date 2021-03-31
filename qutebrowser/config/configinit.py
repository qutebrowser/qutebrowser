# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Initialization of the configuration."""

import argparse
import os.path
import sys

from PyQt5.QtWidgets import QMessageBox

from qutebrowser.api import config as configapi
from qutebrowser.config import (config, configdata, configfiles, configtypes,
                                configexc, configcommands, stylesheet, qtargs)
from qutebrowser.utils import objreg, usertypes, log, standarddir, message
from qutebrowser.config import configcache
from qutebrowser.misc import msgbox, objects, savemanager


# Error which happened during init, so we can show a message box.
_init_errors = None


def early_init(args: argparse.Namespace) -> None:
    """Initialize the part of the config which works without a QApplication."""
    configdata.init()

    yaml_config = configfiles.YamlConfig()

    config.instance = config.Config(yaml_config=yaml_config)
    config.val = config.ConfigContainer(config.instance)
    configapi.val = config.ConfigContainer(config.instance)
    config.key_instance = config.KeyConfig(config.instance)
    config.cache = configcache.ConfigCache()
    yaml_config.setParent(config.instance)

    for cf in config.change_filters:
        cf.validate()

    config_commands = configcommands.ConfigCommands(
        config.instance, config.key_instance)
    objreg.register('config-commands', config_commands, command_only=True)

    config_file = standarddir.config_py()
    custom_config_py = args.config_py is not None

    global _init_errors

    try:
        if os.path.exists(config_file) or custom_config_py:
            # If we have a custom --config-py flag, we want it to be fatal if it doesn't
            # exist, so we don't silently fall back to autoconfig.yml in that case.
            configfiles.read_config_py(
                config_file,
                warn_autoconfig=not custom_config_py,
            )
        else:
            configfiles.read_autoconfig()
    except configexc.ConfigFileErrors as e:
        log.config.error("Error while loading {}".format(e.basename))
        _init_errors = e

    try:
        configfiles.init()
    except configexc.ConfigFileErrors as e:
        _init_errors = e

    for opt, val in args.temp_settings:
        try:
            config.instance.set_str(opt, val)
        except configexc.Error as e:
            message.error("set: {} - {}".format(e.__class__.__name__, e))

    objects.backend = get_backend(args)
    objects.debug_flags = set(args.debug_flags)

    stylesheet.init()

    qtargs.init_envvars()


def _update_font_defaults(setting: str) -> None:
    """Update all fonts if fonts.default_family/_size was set."""
    if setting not in {'fonts.default_family', 'fonts.default_size'}:
        return

    configtypes.FontBase.set_defaults(config.val.fonts.default_family,
                                      config.val.fonts.default_size)

    for name, opt in configdata.DATA.items():
        if not isinstance(opt.typ, configtypes.FontBase):
            continue

        value = config.instance.get_obj(name)
        if value is None or not (value.endswith(' default_family') or
                                 'default_size ' in value):
            continue

        config.instance.changed.emit(name)


def get_backend(args: argparse.Namespace) -> usertypes.Backend:
    """Find out what backend to use based on available libraries."""
    str_to_backend = {
        'webkit': usertypes.Backend.QtWebKit,
        'webengine': usertypes.Backend.QtWebEngine,
    }

    if args.backend is not None:
        return str_to_backend[args.backend]
    else:
        return str_to_backend[config.val.backend]


def late_init(save_manager: savemanager.SaveManager) -> None:
    """Initialize the rest of the config after the QApplication is created."""
    global _init_errors
    if _init_errors is not None:
        errbox = msgbox.msgbox(parent=None,
                               title="Error while reading config",
                               text=_init_errors.to_html(),
                               icon=QMessageBox.Warning,
                               plain_text=False)
        errbox.exec()

        if _init_errors.fatal:
            sys.exit(usertypes.Exit.err_init)

    _init_errors = None

    configtypes.FontBase.set_defaults(config.val.fonts.default_family,
                                      config.val.fonts.default_size)
    config.instance.changed.connect(_update_font_defaults)

    config.instance.init_save_manager(save_manager)
    configfiles.state.init_save_manager(save_manager)
