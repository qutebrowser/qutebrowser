# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


"""Test Progress widget."""

import pytest

from qutebrowser.mainwindow.statusbar import progress
from qutebrowser.utils import usertypes, utils


@pytest.fixture
def progress_widget(qtbot, config_stub):
    """Create a Progress widget and checks its initial state."""
    widget = progress.Progress()
    widget.enabled = True
    qtbot.add_widget(widget)
    assert not widget.isVisible()
    assert not widget.isTextVisible()
    return widget


def test_load_started(progress_widget):
    """Ensure the Progress widget reacts properly when the page starts loading.

    Args:
        progress_widget: Progress widget that will be tested.
    """
    progress_widget.on_load_started()
    assert progress_widget.value() == 0
    assert progress_widget.isVisible()


@pytest.mark.parametrize('progress, load_status, expected_visible', [
    (15, usertypes.LoadStatus.loading, True),
    (100, usertypes.LoadStatus.success, False),
    (100, usertypes.LoadStatus.error, False),
    (100, usertypes.LoadStatus.warn, False),
    (100, usertypes.LoadStatus.none, False),
])
def test_tab_changed(fake_web_tab, progress_widget, progress, load_status,
                     expected_visible):
    """Test that progress widget value and visibility state match expectations.

    Args:
        progress_widget: Progress widget that will be tested.
    """
    tab = fake_web_tab(progress=progress, load_status=load_status)
    progress_widget.on_tab_changed(tab)
    actual = progress_widget.value(), progress_widget.isVisible()
    expected = tab.progress(), expected_visible
    assert actual == expected


def test_progress_affecting_statusbar_height(config_stub, fake_statusbar,
                                             progress_widget):
    """Make sure the statusbar stays the same height when progress is shown.

    https://github.com/qutebrowser/qutebrowser/issues/886
    https://github.com/qutebrowser/qutebrowser/pull/890
    """
    if not utils.is_mac:
        # There is a difference depending on the font. This seems to avoid
        # this, but on macOS, we get a warning about the font not being found.
        config_stub.val.fonts.statusbar = '8pt Monospace'

    fake_statusbar.container.expose()

    expected_height = fake_statusbar.fontMetrics().height()
    assert fake_statusbar.height() == expected_height

    fake_statusbar.hbox.addWidget(progress_widget)
    progress_widget.show()

    assert fake_statusbar.height() == expected_height


def test_progress_big_statusbar(qtbot, fake_statusbar, progress_widget):
    """Make sure the progress bar is small with a big statusbar.

    https://github.com/qutebrowser/qutebrowser/commit/46d1760798b730852e2207e2cdc05a9308e44f80
    """
    fake_statusbar.hbox.addWidget(progress_widget)
    progress_widget.show()
    expected_height = progress_widget.height()
    fake_statusbar.hbox.addStrut(50)
    assert progress_widget.height() == expected_height
