"""Test Zoom widget."""

import pytest

from qutebrowser.mainwindow.statusbar.zoom import Zoom
from typing import Any
import pytestqt.qtbot


@pytest.fixture
def zoom(qtbot: pytestqt.qtbot.QtBot) -> Zoom:
    """Fixture providing a Percentage widget."""
    widget = Zoom()
    qtbot.add_widget(widget)
    return widget


@pytest.mark.parametrize('factor, expected', [
    (1, '100%'),
    (1.5, '150%'),
    (2, '200%'),
    (0.5, '50%'),
    (0.25, '25%'),
])
def test_percentage_texts(zoom: Zoom, factor: float, expected: str) -> None:
    """Test text displayed by the widget based on the zoom factor of a tab.

    Args:
        factor: zoom factor of the tab as a float.
        expected: expected text given factor.
    """
    zoom.on_zoom_changed(factor=factor)
    assert zoom.text() == expected


def test_tab_change(zoom: Zoom, fake_web_tab: Any) -> None:
    """Test zoom factor change when switching tabs."""
    zoom.on_zoom_changed(factor=2)
    assert zoom.text() == '200%'
    tab = fake_web_tab(zoom_factor=0.5)
    zoom.on_tab_changed(tab)
    assert zoom.text() == '50%'
