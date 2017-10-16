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

import os.path
import sys

from PyQt5.QtWidgets import QMessageBox

from qutebrowser.config import (config, configdata, configfiles, configtypes,
                                configexc, configcommands)
from qutebrowser.utils import objreg, usertypes, log, standarddir, message
from qutebrowser.misc import msgbox, objects


# Error which happened during init, so we can show a message box.
_init_errors = None


def early_init(args):
    """Initialize the part of the config which works without a QApplication."""
    configdata.init()

    yaml_config = configfiles.YamlConfig()

    config.instance = config.Config(yaml_config=yaml_config)
    config.val = config.ConfigContainer(config.instance)
    config.key_instance = config.KeyConfig(config.instance)
    yaml_config.setParent(config.instance)

    for cf in config.change_filters:
        cf.validate()

    config_commands = configcommands.ConfigCommands(
        config.instance, config.key_instance)
    objreg.register('config-commands', config_commands)

    config_file = os.path.join(standarddir.config(), 'config.py')

    try:
        if os.path.exists(config_file):
            configfiles.read_config_py(config_file)
        else:
            configfiles.read_autoconfig()
    except configexc.ConfigFileErrors as e:
        log.config.exception("Error while loading {}".format(e.basename))
        global _init_errors
        _init_errors = e

    configfiles.init()

    objects.backend = get_backend(args)

    for opt, val in args.temp_settings:
        try:
            config.instance.set_str(opt, val)
        except configexc.Error as e:
            message.error("set: {} - {}".format(e.__class__.__name__, e))

    configtypes.Font.monospace_fonts = config.val.fonts.monospace
    config.instance.changed.connect(_update_monospace_fonts)

    _init_envvars()


def _init_envvars():
    """Initialize environment variables which need to be set early."""
    if (objects.backend == usertypes.Backend.QtWebEngine and
            config.val.qt.force_software_rendering):
        os.environ['QT_XCB_FORCE_SOFTWARE_OPENGL'] = '1'

    if config.val.qt.force_platform is not None:
        os.environ['QT_QPA_PLATFORM'] = config.val.qt.force_platform

    if config.val.window.hide_wayland_decoration:
        os.environ['QT_WAYLAND_DISABLE_WINDOWDECORATION'] = '1'
    else:
        os.environ.pop('QT_WAYLAND_DISABLE_WINDOWDECORATION', None)


@config.change_filter('fonts.monospace', function=True)
def _update_monospace_fonts():
    """Update all fonts if fonts.monospace was set."""
    configtypes.Font.monospace_fonts = config.val.fonts.monospace
    for name, opt in configdata.DATA.items():
        if name == 'fonts.monospace':
            continue
        elif not isinstance(opt.typ, configtypes.Font):
            continue

        value = config.instance.get_obj(name)
        if value is None or not value.endswith(' monospace'):
            continue

        config.instance.changed.emit(name)


def get_backend(args):
    """Find out what backend to use based on available libraries."""
    str_to_backend = {
        'webkit': usertypes.Backend.QtWebKit,
        'webengine': usertypes.Backend.QtWebEngine,
    }

    if args.backend is not None:
        return str_to_backend[args.backend]
    else:
        return str_to_backend[config.val.backend]


def late_init(save_manager):
    """Initialize the rest of the config after the QApplication is created."""
    global _init_errors
    if _init_errors is not None:
        errbox = msgbox.msgbox(parent=None,
                               title="Error while reading config",
                               text=_init_errors.to_html(),
                               icon=QMessageBox.Warning,
                               plain_text=False)
        errbox.exec_()
    _init_errors = None

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

    argv += ['--' + arg for arg in config.val.qt.args]
    return argv
