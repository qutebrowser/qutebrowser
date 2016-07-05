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

from PyQt5.QtCore import pyqtSignal, QPoint

from qutebrowser.browser import tab
from qutebrowser.keyinput import modeman

try:
    from PyQt5.QtWebKitWidgets import QWebView

    class WebView(QWebView):
        mouse_wheel_zoom = pyqtSignal(QPoint)
except ImportError:
    WebView = None

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView

    class WebEngineView(QWebEngineView):
        mouse_wheel_zoom = pyqtSignal(QPoint)
except ImportError:
    WebEngineView = None


@pytest.mark.parametrize('view', [WebView, WebEngineView])
def test_tab(qtbot, view, config_stub):
    config_stub.data = {
        'input': {
            'forward-unbound-keys': 'auto'
        },
        'ui': {
            'zoom-levels': [100],
            'default-zoom': 100,
        }
    }

    if view is None:
        pytest.skip("View not available")

    w = view()
    qtbot.add_widget(w)

    tab_w = tab.AbstractTab(win_id=0)
    qtbot.add_widget(tab_w)
    tab_w.show()

    assert tab_w.win_id == 0
    assert tab_w._widget is None

    mode_man = modeman.ModeManager(0)

    tab_w.history = tab.AbstractHistory(tab_w)
    tab_w.scroll = tab.AbstractScroller(parent=tab_w)
    tab_w.caret = tab.AbstractCaret(win_id=tab_w.win_id, modeman=mode_man,
                                    tab=tab_w, parent=tab_w)
    tab_w.zoom = tab.AbstractZoom(win_id=tab_w.win_id)
    tab_w.search = tab.AbstractSearch(parent=tab_w)

    tab_w._set_widget(w)
    assert tab_w._widget is w
    assert tab_w.history._tab is tab_w
    assert tab_w.history._history is w.history()
    assert w.parent() is tab_w


class TestTabData:

    def test_known_attr(self):
        data = tab.TabData()
        assert data.keep_icon == False
        data.keep_icon = True
        assert data.keep_icon == True

    def test_unknown_attr(self):
        data = tab.TabData()
        with pytest.raises(AttributeError):
            data.bar = 42
        with pytest.raises(AttributeError):
            data.bar
