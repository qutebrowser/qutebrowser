# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import functools

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
        w.show()
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

    # Sizing tests

    def test_tab_size_same(self, widget, fake_web_tab):
        """Ensure by default, all tab sizes are the same."""
        num_tabs = 10
        for i in range(num_tabs):
            widget.addTab(fake_web_tab(), 'foobar' + str(i))

        first_size = widget.tabBar().tabSizeHint(0)
        first_size_min = widget.tabBar().minimumTabSizeHint(0)

        for i in range(num_tabs):
            assert first_size == widget.tabBar().tabSizeHint(i)
            assert first_size_min == widget.tabBar().minimumTabSizeHint(i)

    @pytest.mark.parametrize("shrink_pinned", [True, False])
    @pytest.mark.parametrize("vertical", [True, False])
    def test_pinned_size(self, widget, fake_web_tab, config_stub,
                         shrink_pinned, vertical):
        """Ensure by default, pinned min sizes are forced to title.

        If pinned.shrink is not true, then all tabs should be the same

        If tabs are vertical, all tabs should be the same"""
        num_tabs = 10
        for i in range(num_tabs):
            widget.addTab(fake_web_tab(), 'foobar' + str(i))

        # Set pinned title format longer than unpinned
        config_stub.val.tabs.title.format_pinned = "_" * 10
        config_stub.val.tabs.title.format = "_" * 2
        config_stub.val.tabs.pinned.shrink = shrink_pinned
        if vertical:
            # Use pixel width so we don't need to mock main-window
            config_stub.val.tabs.width = 50
            config_stub.val.tabs.position = "left"

        pinned_num = [1, num_tabs - 1]
        for tab in pinned_num:
            widget.set_tab_pinned(widget.widget(tab), True)

        first_size = widget.tabBar().tabSizeHint(0)
        first_size_min = widget.tabBar().minimumTabSizeHint(0)

        for i in range(num_tabs):
            if i in pinned_num and shrink_pinned and not vertical:
                assert (first_size.width() >
                        widget.tabBar().tabSizeHint(i).width())
                assert (first_size_min.width() <
                        widget.tabBar().minimumTabSizeHint(i).width())
            else:
                assert first_size == widget.tabBar().tabSizeHint(i)
                assert first_size_min == widget.tabBar().minimumTabSizeHint(i)

    @pytest.mark.parametrize("num_tabs", [4, 10, 50, 100])
    def test_update_tab_titles_benchmark(self, benchmark, widget,
                                         qtbot, fake_web_tab, num_tabs):
        """Benchmark for update_tab_titles."""
        for i in range(num_tabs):
            widget.addTab(fake_web_tab(), 'foobar' + str(i))

        with qtbot.waitExposed(widget):
            widget.show()

        benchmark(widget.update_tab_titles)

    def test_tab_min_width(self, widget, fake_web_tab, config_stub, qtbot):
        widget.addTab(fake_web_tab(), 'foobar')
        widget.addTab(fake_web_tab(), 'foobar1')
        min_size = widget.tabBar().tabRect(0).width() + 10
        config_stub.val.tabs.min_width = min_size
        assert widget.tabBar().tabRect(0).width() == min_size

    def test_tab_max_width(self, widget, fake_web_tab, config_stub, qtbot):
        widget.addTab(fake_web_tab(), 'foobar')
        max_size = widget.tabBar().tabRect(0).width() - 10
        config_stub.val.tabs.max_width = max_size
        assert widget.tabBar().tabRect(0).width() == max_size

    def test_tab_stays_hidden(self, widget, fake_web_tab, config_stub):
        assert widget.tabBar().isVisible()
        config_stub.val.tabs.show = "never"
        assert not widget.tabBar().isVisible()
        for i in range(12):
            widget.addTab(fake_web_tab(), 'foobar' + str(i))
        assert not widget.tabBar().isVisible()

    @pytest.mark.parametrize("num_tabs", [4, 70])
    @pytest.mark.parametrize("rev", [True, False])
    def test_add_remove_tab_benchmark(self, benchmark, widget,
                                      qtbot, fake_web_tab, num_tabs, rev):
        """Benchmark for addTab and removeTab."""
        def _run_bench():
            with qtbot.wait_exposed(widget):
                widget.show()
            for i in range(num_tabs):
                idx = i if rev else 0
                widget.insertTab(idx, fake_web_tab(), 'foobar' + str(i))

            to_del = range(num_tabs)
            if rev:
                to_del = reversed(to_del)
            for i in to_del:
                widget.removeTab(i)

        benchmark(_run_bench)

    def test_tab_pinned_benchmark(self, benchmark, widget, fake_web_tab):
        """Benchmark for _tab_pinned."""
        widget.addTab(fake_web_tab(), 'foobar')
        tab_bar = widget.tabBar()
        benchmark(functools.partial(tab_bar._tab_pinned, 0))
