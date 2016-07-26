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

from PyQt5.QtCore import PYQT_VERSION, pyqtSignal, QPoint

from qutebrowser.browser import browsertab
from qutebrowser.keyinput import modeman
from qutebrowser.utils import objreg

pytestmark = pytest.mark.usefixtures('redirect_xdg_data')

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


@pytest.fixture(params=[WebView, WebEngineView])
def view(qtbot, config_stub, request):
    config_stub.data = {
        'input': {
            'forward-unbound-keys': 'auto'
        },
        'ui': {
            'zoom-levels': [100],
            'default-zoom': 100,
        }
    }

    if request.param is None:
        pytest.skip("View not available")

    v = request.param()
    qtbot.add_widget(v)
    return v


@pytest.yield_fixture(params=['webkit', 'webengine'])
def tab(request, default_config, qtbot, tab_registry, cookiejar_and_cache):
    if PYQT_VERSION < 0x050600:
        pytest.skip('Causes segfaults, see #1638')

    if request.param == 'webkit':
        webkittab = pytest.importorskip('qutebrowser.browser.webkit.webkittab')
        tab_class = webkittab.WebKitTab
    elif request.param == 'webengine':
        webenginetab = pytest.importorskip(
            'qutebrowser.browser.webengine.webenginetab')
        tab_class = webenginetab.WebEngineTab
    else:
        assert False

    # Can't use the mode_manager fixture as that uses config_stub, which
    # conflicts with default_config
    mm = modeman.ModeManager(0)
    objreg.register('mode-manager', mm, scope='window', window=0)

    t = tab_class(win_id=0, mode_manager=mm)
    qtbot.add_widget(t)
    yield t

    objreg.delete('mode-manager', scope='window', window=0)


@pytest.mark.skipif(PYQT_VERSION < 0x050600,
                    reason='Causes segfaults, see #1638')
def test_tab(qtbot, view, config_stub, tab_registry):
    tab_w = browsertab.AbstractTab(win_id=0)
    qtbot.add_widget(tab_w)
    tab_w.show()

    assert tab_w.win_id == 0
    assert tab_w._widget is None

    mode_manager = modeman.ModeManager(0)

    tab_w.history = browsertab.AbstractHistory(tab_w)
    tab_w.scroller = browsertab.AbstractScroller(tab_w, parent=tab_w)
    tab_w.caret = browsertab.AbstractCaret(win_id=tab_w.win_id,
                                           mode_manager=mode_manager,
                                           tab=tab_w, parent=tab_w)
    tab_w.zoom = browsertab.AbstractZoom(win_id=tab_w.win_id)
    tab_w.search = browsertab.AbstractSearch(parent=tab_w)
    tab_w.printing = browsertab.AbstractPrinting()

    tab_w._set_widget(view)
    assert tab_w._widget is view
    assert tab_w.history._tab is tab_w
    assert tab_w.history._history is view.history()
    assert view.parent() is tab_w


class TestJs:

    @pytest.mark.parametrize('inp, expected', [('1+1', 2),
                                               ('undefined', None)])
    def test_blocking(self, tab, inp, expected):
        assert tab.run_js_blocking(inp) == expected


class TestTabData:

    def test_known_attr(self):
        data = browsertab.TabData()
        assert not data.keep_icon
        data.keep_icon = True
        assert data.keep_icon

    def test_unknown_attr(self):
        data = browsertab.TabData()
        with pytest.raises(AttributeError):
            data.bar = 42  # pylint: disable=assigning-non-slot
        with pytest.raises(AttributeError):
            data.bar  # pylint: disable=pointless-statement
