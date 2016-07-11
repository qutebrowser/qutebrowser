# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Daniel Schadt
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
from qutebrowser.config import configtypes
from PyQt5.QtGui import QIcon, QPixmap, QFont, QColor
from PyQt5.QtCore import Qt


class TestTabWidget:

    """Tests for TabWidget."""

    CONFIG = {
        'fonts': {
            'tabbar': QFont(),
        },
        'tabs': {
            'show-switching-delay': 800,
            'movable': True,
            'position': 0,
            'select-on-remove': 1,
            'show': 'always',
            'padding': configtypes.PaddingValues(0, 0, 5, 5),
            'indicator-width': 3,
            'indicator-padding': configtypes.PaddingValues(2, 2, 0, 4),
            'title-format': '{index}: {title}',
            'title-alignment': Qt.AlignLeft,
        },
        'colors': {
            'tabs.bg.bar': QColor(),
            'tabs.bg.selected.even': QColor(),
            'tabs.fg.selected.even': QColor(),
        }
    }

    @pytest.fixture
    def widget(self, qtbot, config_stub):
        config_stub.data = self.CONFIG
        w = tabwidget.TabWidget(0)
        qtbot.addWidget(w)
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
        widget.show()
        qtbot.waitForWindowShown(widget)
