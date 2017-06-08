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

    def _key(self, sect, opt):
        return sect + ' -> ' + opt

    def read_defaults(self):
        for name, section in configdata.data().items():
            for key, value in section.items():
                self._values[self._key(name, key)] = value

    def get(self, section, option):
        val = self._values[self._key(section, option)]
        return val.typ.transform(val.value())
