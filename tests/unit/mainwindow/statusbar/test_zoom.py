"""Test Zoom widget."""

import pytest

from qutebrowser.mainwindow.statusbar.zoom import Zoom
from typing import Any
import pytestqt.qtbot


@pytest.fixture
def zoom(qtbot: pytestqt.qtbot.QtBot, config_stub: Any) -> Zoom:
    """Fixture providing a Zoom widget."""
    widget = Zoom()
    qtbot.add_widget(widget)
    return widget


@pytest.mark.parametrize('factor, show, expected', [
    (1, 'always', '[100%]'),
    (1.5, 'always', '[150%]'),
    (2, 'always', '[200%]'),
    (0.5, 'always', '[50%]'),
    (0.25, 'always', '[25%]'),
    (1, 'non-default', ''),
    (1.5, 'non-default', '[150%]'),
    (2, 'non-default', '[200%]'),
    (0.5, 'non-default', '[50%]'),
    (0.25, 'non-default', '[25%]'),
])
def test_percentage_texts(zoom: Zoom, factor: float, show: str, expected: str,
                          config_stub: Any) -> None:
    """Test text displayed by the widget based on the zoom factor of a tab and a config value.

    Args:
        factor: zoom factor of the tab as a float.
        show: config value for `statusbar.zoom.show`.
        expected: expected text given factor.
    """
    config_stub.val.statusbar.zoom.show = show
    zoom.on_zoom_changed(factor=factor)
    assert zoom.text() == expected


def test_tab_change(zoom: Zoom, fake_web_tab: Any) -> None:
    """Test zoom factor change when switching tabs."""
    zoom.on_zoom_changed(factor=2)
    assert zoom.text() == '[200%]'
    tab = fake_web_tab(zoom_factor=0.5)
    zoom.on_tab_changed(tab)
    assert zoom.text() == '[50%]'
