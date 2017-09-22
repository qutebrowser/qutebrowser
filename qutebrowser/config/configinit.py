# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Initialization of the configuration."""

import sys

from PyQt5.QtWidgets import QMessageBox

from qutebrowser.config import (config, configdata, configfiles, configtypes,
                                configexc)
from qutebrowser.utils import objreg, qtutils, usertypes, log
from qutebrowser.misc import earlyinit, msgbox, objects


# Errors which happened during init, so we can show a message box.
_init_errors = []


def early_init(args):
    """Initialize the part of the config which works without a QApplication."""
    configdata.init()

    yaml_config = configfiles.YamlConfig()

    config.instance = config.Config(yaml_config=yaml_config)
    config.val = config.ConfigContainer(config.instance)
    config.key_instance = config.KeyConfig(config.instance)

    for cf in config.change_filters:
        cf.validate()

    configtypes.Font.monospace_fonts = config.val.fonts.monospace

    config_commands = config.ConfigCommands(config.instance,
                                            config.key_instance)
    objreg.register('config-commands', config_commands)

    config_api = None

    try:
        config_api = configfiles.read_config_py()
        # Raised here so we get the config_api back.
        if config_api.errors:
            raise configexc.ConfigFileErrors('config.py', config_api.errors)
    except configexc.ConfigFileErrors as e:
        log.config.exception("Error while loading config.py")
        _init_errors.append(e)

    try:
        if getattr(config_api, 'load_autoconfig', True):
            try:
                config.instance.read_yaml()
            except configexc.ConfigFileErrors as e:
                raise  # caught in outer block
            except configexc.Error as e:
                desc = configexc.ConfigErrorDesc("Error", e)
                raise configexc.ConfigFileErrors('autoconfig.yml', [desc])
    except configexc.ConfigFileErrors as e:
        log.config.exception("Error while loading config.py")
        _init_errors.append(e)

    configfiles.init()

    objects.backend = get_backend(args)
    earlyinit.init_with_backend(objects.backend)


def get_backend(args):
    """Find out what backend to use based on available libraries."""
    try:
        import PyQt5.QtWebKit  # pylint: disable=unused-variable
    except ImportError:
        webkit_available = False
    else:
        webkit_available = qtutils.is_new_qtwebkit()

    str_to_backend = {
        'webkit': usertypes.Backend.QtWebKit,
        'webengine': usertypes.Backend.QtWebEngine,
    }

    if args.backend is not None:
        return str_to_backend[args.backend]
    elif config.val.backend != 'auto':
        return str_to_backend[config.val.backend]
    elif webkit_available:
        return usertypes.Backend.QtWebKit
    else:
        return usertypes.Backend.QtWebEngine


def late_init(save_manager):
    """Initialize the rest of the config after the QApplication is created."""
    global _init_errors
    for err in _init_errors:
        errbox = msgbox.msgbox(parent=None,
                               title="Error while reading config",
                               text=err.to_html(),
                               icon=QMessageBox.Warning,
                               plain_text=False)
        errbox.exec_()
    _init_errors = []

    config.instance.init_save_manager(save_manager)
    configfiles.state.init_save_manager(save_manager)


def qt_args(namespace):
    """Get the Qt QApplication arguments based on an argparse namespace.

    Args:
        namespace: The argparse namespace.

    Return:
        The argv list to be passed to Qt.
    """
    argv = [sys.argv[0]]

    if namespace.qt_flag is not None:
        argv += ['--' + flag[0] for flag in namespace.qt_flag]

    if namespace.qt_arg is not None:
        for name, value in namespace.qt_arg:
            argv += ['--' + name, value]

    argv += ['--' + arg for arg in config.val.qt_args]
    return argv
