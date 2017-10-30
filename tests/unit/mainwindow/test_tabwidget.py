# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2017 Daniel Schadt
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

from qutebrowser.mainwindow import tabwidget
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

    def test_update_tab_titles_benchmark(self, benchmark, widget,
                                         qtbot, fake_web_tab):
        """Benchmark for update_tab_titles."""
        widget.addTab(fake_web_tab(), 'foobar')
        widget.addTab(fake_web_tab(), 'foobar2')
        widget.addTab(fake_web_tab(), 'foobar3')
        widget.addTab(fake_web_tab(), 'foobar4')

        with qtbot.waitExposed(widget):
            widget.show()

        benchmark(widget._update_tab_titles)
