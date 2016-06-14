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

from qutebrowser.browser import tab

from PyQt5.QtWidgets import QWidget


def test_tab(qtbot):
    w = QWidget()
    qtbot.add_widget(w)
    tab_w = tab.AbstractTab()
    tab_w.show()
    assert tab_w._widget is None
    tab_w._set_widget(w)
    assert tab_w._widget is w
    assert w.parent() is tab_w
