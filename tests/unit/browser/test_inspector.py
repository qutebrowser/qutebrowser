# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2020-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

import pytest

from PyQt5.QtWidgets import QWidget

from qutebrowser.browser import inspector
from qutebrowser.misc import miscwidgets


class FakeInspector(inspector.AbstractWebInspector):

    def __init__(self,
                 inspector_widget: QWidget,
                 splitter: miscwidgets.InspectorSplitter,
                 win_id: int,
                 parent: QWidget = None) -> None:
        super().__init__(splitter, win_id, parent)
        self._set_widget(inspector_widget)
        self._inspected_page = None
        self.needs_recreate = False

    def inspect(self, page):
        self._inspected_page = page

    def _needs_recreate(self):
        return self.needs_recreate


@pytest.fixture
def webview_widget(blue_widget):
    return blue_widget


@pytest.fixture
def inspector_widget(red_widget):
    return red_widget


@pytest.fixture
def splitter(qtbot, webview_widget):
    splitter = miscwidgets.InspectorSplitter(
        win_id=0, main_webview=webview_widget)
    qtbot.add_widget(splitter)
    return splitter


@pytest.fixture
def fake_inspector(qtbot, splitter, inspector_widget,
                   state_config, mode_manager):
    insp = FakeInspector(inspector_widget=inspector_widget,
                         splitter=splitter,
                         win_id=0)
    qtbot.add_widget(insp)
    return insp


@pytest.mark.parametrize('position, splitter_count, window_visible', [
    (inspector.Position.window, 1, True),
    (inspector.Position.left, 2, False),
    (inspector.Position.top, 2, False),
])
def test_set_position(position, splitter_count, window_visible,
                      fake_inspector, splitter):
    fake_inspector.set_position(position)
    assert splitter.count() == splitter_count
    assert (fake_inspector.isWindow() and
            fake_inspector.isVisible()) == window_visible


def test_toggle_window(fake_inspector):
    fake_inspector.set_position(inspector.Position.window)
    for visible in [True, False, True]:
        assert (fake_inspector.isWindow() and
                fake_inspector.isVisible()) == visible
        fake_inspector.toggle()


def test_toggle_docked(fake_inspector, splitter, inspector_widget):
    fake_inspector.set_position(inspector.Position.right)
    splitter.show()
    for visible in [True, False, True]:
        assert inspector_widget.isVisible() == visible
        fake_inspector.toggle()


def test_implicit_toggling(fake_inspector, splitter, inspector_widget):
    fake_inspector.set_position(inspector.Position.right)
    splitter.show()
    assert inspector_widget.isVisible()
    fake_inspector.set_position(None)
    assert not inspector_widget.isVisible()


def test_position_saving(fake_inspector, state_config):
    assert 'position' not in state_config['inspector']
    fake_inspector.set_position(inspector.Position.left)
    assert state_config['inspector']['position'] == 'left'


@pytest.mark.parametrize('config_value, expected', [
    (None, inspector.Position.right),
    ('top', inspector.Position.top),
])
def test_position_loading(config_value, expected,
                          fake_inspector, state_config):
    if config_value is None:
        assert 'position' not in state_config['inspector']
    else:
        state_config['inspector']['position'] = config_value

    fake_inspector.set_position(None)
    assert fake_inspector._position == expected


@pytest.mark.parametrize('hidden_again', [True, False])
@pytest.mark.parametrize('needs_recreate', [True, False])
def test_detach_after_toggling(hidden_again, needs_recreate,
                               fake_inspector, inspector_widget, splitter,
                               qtbot):
    """Make sure we can still detach into a window after showing inline."""
    fake_inspector.set_position(inspector.Position.right)
    splitter.show()
    assert inspector_widget.isVisible()

    if hidden_again:
        fake_inspector.toggle()
        assert not inspector_widget.isVisible()

    if needs_recreate:
        fake_inspector.needs_recreate = True
        with qtbot.wait_signal(fake_inspector.recreate):
            fake_inspector.set_position(inspector.Position.window)
    else:
        with qtbot.assert_not_emitted(fake_inspector.recreate):
            fake_inspector.set_position(inspector.Position.window)
        assert fake_inspector.isVisible() and fake_inspector.isWindow()
