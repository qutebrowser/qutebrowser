# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Daniel Schadt
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

from qutebrowser.mainwindow import tabwidget
from PyQt5.QtGui import QIcon, QPixmap


class TestTabWidget:

    """Tests for TabBar."""

    @pytest.fixture
    def widget(self, qtbot, default_config):
        w = tabwidget.TabWidget(0)
        qtbot.addWidget(w)
        return w

    def test_small_icon_doesnt_crash(self, widget, qtbot, stubs):
        """Test that setting a small icon doesn't produce a crash.

        Regression test for #1015.
        """
        # Size taken from issue report
        pixmap = QPixmap(72, 1)
        icon = QIcon(pixmap)
        page = stubs.FakeWebView()
        widget.addTab(page, icon, 'foobar')
        widget.show()
        qtbot.waitForWindowShown(widget)
