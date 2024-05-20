from qutebrowser.mainwindow.statusbar.widget import StatusBarWidget

import pytest


class TestCreateWidget:
    def test_scroll_raw(self, qtbot, config_stub):
        segment = 'scroll_raw'
        widget = StatusBarWidget.from_config(segment)

        # Force immediate update of percentage widget
        widget._set_text.set_delay(-1)
        widget.set_perc(0, 50)

        assert widget.text() == '[50]'

    def test_text(self, qtbot, config_stub):
        segment = 'text:some text'
        widget = StatusBarWidget.from_config(segment)

        assert widget.text() == 'some text'

    @pytest.mark.parametrize(
        "segment,format_",
        [
            ('clock:%H:%s', '%H:%s'),
            ('clock', '%X'),
        ]
    )
    def test_clock(self, segment, format_, qtbot, config_stub):
        widget = StatusBarWidget.from_config(segment)

        assert widget.format == format_
