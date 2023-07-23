# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Keychain string displayed in the statusbar."""

from qutebrowser.qt.core import pyqtSlot

from qutebrowser.mainwindow.statusbar import textbase
from qutebrowser.utils import usertypes


class KeyString(textbase.TextBase):

    """Keychain string displayed in the statusbar."""

    @pyqtSlot(usertypes.KeyMode, str)
    def on_keystring_updated(self, _mode, keystr):
        self.setText(keystr)
