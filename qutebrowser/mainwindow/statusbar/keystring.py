# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Keychain string displayed in the statusbar."""

from qutebrowser.mainwindow.statusbar.item import StatusBarItem
from qutebrowser.qt.core import pyqtSlot

from qutebrowser.mainwindow.statusbar import textbase
from qutebrowser.utils import usertypes


class KeyStringWidget(textbase.TextBaseWidget):

    """Keychain string displayed in the statusbar."""

    @pyqtSlot(usertypes.KeyMode, str)
    def on_keystring_updated(self, _mode, keystr):
        self.setText(keystr)


class KeyString(StatusBarItem):
    pass
