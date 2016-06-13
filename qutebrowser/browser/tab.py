# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Base class for a wrapper over QWebView/QWebEngineView."""

from PyQt5.QtWidgets import QWidget, QLayout


class WrapperLayout(QLayout):

    def __init__(self, widget, parent=None):
        super().__init__(parent)
        self._widget = widget

    def addItem(self, w):
        raise AssertionError("Should never be called!")

    def sizeHint(self):
        return self._widget.sizeHint()

    def itemAt(self, i):
        raise AssertionError("Should never be called!")

    def takeAt(self, i):
        raise AssertionError("Should never be called!")

    def setGeometry(self, r):
        self._widget.setGeometry(r)


class AbstractTab(QWidget):

    """A wrapper over the given widget to hide its API and expose another one.

    We use this to unify QWebView QWebEngineView.
    """

    def __init__(self, widget, parent=None):
        super().__init__(parent)
        self._layout = WrapperLayout(widget, self)
        self._widget = widget
        widget.setParent(self)
