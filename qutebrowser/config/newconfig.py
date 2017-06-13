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

"""New qutebrowser configuration code."""


from PyQt5.QtCore import pyqtSignal, QObject


from qutebrowser.config import configdata
from qutebrowser.utils import utils, objreg

# An easy way to access the config from other code via config.val.foo
val = None


class UnknownOptionError(Exception):

    """Raised by NewConfigManager when an option is unknown."""


class SectionStub:

    # FIXME get rid of this once we get rid of sections

    def __init__(self, conf, name):
        self._conf = conf
        self._name = name

    def __getitem__(self, item):
        return self._conf.get(self._name, item)


class NewConfigManager(QObject):

    # FIXME:conf QObject?

    changed = pyqtSignal(str, str)  # FIXME:conf stub... where is this used?

    def __init__(self, parent=None):
        super().__init__(parent)
        self._values = {}

    def read_defaults(self):
        for name, option in configdata.DATA.items():
            self._values[name] = option

    def get(self, option):
        try:
            val = self._values[option]
        except KeyError as e:
            raise UnknownOptionError(e)
        return val.typ.from_py(val.default)

    def is_valid_prefix(self, prefix):
        """Check whether the given prefix is a valid prefix for some option."""
        return any(key.startswith(prefix + '.') for key in self._values)


class ConfigContainer:

    """An object implementing config access via __getattr__.

    Attributes:
        _manager: The ConfigManager object.
        _prefix: The __getattr__ chain leading up to this object.
    """

    def __init__(self, manager, prefix=''):
        self._manager = manager
        self._prefix = prefix

    def __repr__(self):
        return utils.get_repr(self, constructor=True, manager=self._manager,
                              prefix=self._prefix)

    def __getattr__(self, attr):
        """Get an option or a new ConfigContainer with the added prefix.

        If we get an option which exists, we return the value for it.
        If we get a part of an option name, we return a new ConfigContainer.

        Those two never overlap as configdata.py ensures there are no shadowing
        options.
        """
        name = self._join(attr)
        if self._manager.is_valid_prefix(name):
            return ConfigContainer(manager=self._manager, prefix=name)
        # If it's not a valid prefix, this will raise NoOptionError.
        self._manager.get(name)

    def __setattr__(self, attr, value):
        if attr.startswith('_'):
            return super().__setattr__(attr, value)
        self._handler(self._join(attr), value)

    def _join(self, attr):
        if self._prefix:
            return '{}.{}'.format(self._prefix, attr)
        else:
            return attr


def init(parent):
    new_config = NewConfigManager(parent)
    new_config.read_defaults()
    objreg.register('config', new_config)
    global val
    val = ConfigContainer(new_config)
