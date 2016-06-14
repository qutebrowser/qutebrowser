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

import pytest

from qutebrowser.browser import tab

try:
    from PyQt5.QtWebKitWidgets import QWebView
except ImportError:
    QWebView = None

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
except ImportError:
    QWebEngineView = None


@pytest.mark.parametrize('view', [QWebView, QWebEngineView])
def test_tab(qtbot, view):
    if view is None:
        pytest.skip("View not available")
    w = view()
    qtbot.add_widget(w)
    tab_w = tab.AbstractTab()
    tab_w.show()
    assert tab_w._widget is None
    tab_w._set_widget(w)
    assert tab_w._widget is w
    assert tab_w.history.tab is tab_w
    assert tab_w.history.history is w.history()
    assert w.parent() is tab_w
