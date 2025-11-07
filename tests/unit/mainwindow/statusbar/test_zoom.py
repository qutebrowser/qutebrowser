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


@pytest.mark.parametrize('factor, expected', [
    (0.25, '[25%]'),
    (0.5, '[50%]'),
    (0.75, '[75%]'),
    (1.5, '[150%]'),
    (2, '[200%]'),
    (3, '[300%]'),
    (4, '[400%]'),
    (5, '[500%]'),
])
@pytest.mark.parametrize("show", ["non-default", "always"])
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


@pytest.mark.parametrize('show, expected', [
    ("always", '[100%]'),
    ("non-default", ''),
])
def test_default_percentage_text(zoom: Zoom, show: str, expected: str,
                          config_stub: Any) -> None:
    """Test default percentage text based on a config value.

    Args:
        show: config value for `statusbar.zoom.show`.
        expected: expected text given show config value.
    """
    config_stub.val.statusbar.zoom.show = show
    zoom.on_zoom_changed(factor=1)
    assert zoom.text() == expected


def test_tab_change(zoom: Zoom, fake_web_tab: Any) -> None:
    """Test zoom factor change when switching tabs."""
    zoom.on_zoom_changed(factor=2)
    assert zoom.text() == '[200%]'
    tab = fake_web_tab(zoom_factor=0.5)
    zoom.on_tab_changed(tab)
    assert zoom.text() == '[50%]'
