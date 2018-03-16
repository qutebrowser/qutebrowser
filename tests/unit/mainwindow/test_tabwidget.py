# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2018 Daniel Schadt
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

"""Tests for the custom TabWidget/TabBar."""

import pytest

from PyQt5.QtGui import QIcon, QPixmap

from qutebrowser.mainwindow import tabwidget, tabbedbrowser
from qutebrowser.utils import usertypes


class TestTabWidget:

    """Tests for TabWidget."""

    @pytest.fixture
    def widget(self, qtbot, monkeypatch, config_stub):
        w = tabwidget.TabWidget(0)
        qtbot.addWidget(w)
        monkeypatch.setattr(tabwidget.objects, 'backend',
                            usertypes.Backend.QtWebKit)
        return w

    @pytest.fixture
    def browser(self, qtbot, monkeypatch, config_stub):
        w = tabbedbrowser.TabbedBrowser(win_id=0, private=False)
        qtbot.addWidget(w)
        monkeypatch.setattr(tabwidget.objects, 'backend',
                            usertypes.Backend.QtWebKit)
        return w

    def test_small_icon_doesnt_crash(self, widget, qtbot, fake_web_tab):
        """Test that setting a small icon doesn't produce a crash.

        Regression test for #1015.
        """
        # Size taken from issue report
        pixmap = QPixmap(72, 1)
        icon = QIcon(pixmap)
        tab = fake_web_tab()
        widget.addTab(tab, icon, 'foobar')

        with qtbot.waitExposed(widget):
            widget.show()

    @pytest.mark.parametrize("num_tabs", [4, 10])
    def test_update_tab_titles_benchmark(self, benchmark, widget,
                                         qtbot, fake_web_tab, num_tabs):
        """Benchmark for update_tab_titles."""
        for i in range(num_tabs):
            widget.addTab(fake_web_tab(), 'foobar' + str(i))

        with qtbot.waitExposed(widget):
            widget.show()

        benchmark(widget.update_tab_titles)

    @pytest.mark.parametrize("num_tabs", [4, 10])
    def test_add_remove_tab_benchmark(self, benchmark, browser,
                                      qtbot, fake_web_tab, num_tabs):
        """Benchmark for addTab and removeTab."""
        def _run_bench():
            for i in range(num_tabs):
                browser.widget.addTab(fake_web_tab(), 'foobar' + str(i))

            with qtbot.waitExposed(browser):
                browser.show()

            browser.shutdown()

        benchmark(_run_bench)
