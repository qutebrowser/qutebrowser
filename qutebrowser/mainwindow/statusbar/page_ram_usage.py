"""Page RAM usage displayed in the statusbar."""

import psutil
from typing import Optional

from qutebrowser.utils import qtutils
from qutebrowser.browser import browsertab
from qutebrowser.misc import throttle
from qutebrowser.qt.core import Qt
from qutebrowser.qt.widgets import QWidget
from qutebrowser.qt.gui import QHideEvent, QShowEvent

from qutebrowser.mainwindow.statusbar import textbase
from qutebrowser.utils import usertypes
from qutebrowser.utils import log


class PageRamUsage(textbase.TextBase):
    """Show memory usage of the renderer process."""

    UPDATE_DELAY = 1000  # ms

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, elidemode=Qt.TextElideMode.ElideNone)
        self._set_text = throttle.Throttle(self.setText, 100, parent=self)
        self.timer = usertypes.Timer(self)
        self.timer.timeout.connect(self._show_ram_usage)
        self.current_tab: Optional[browsertab.AbstractTab] = None

    def _show_ram_usage(self) -> None:
        """Set text to current time, using self.format as format-string."""
        usage = "N/A"
        if self.current_tab is None:
            return
        rppid = self.current_tab.renderer_process_pid()
        if rppid == 0:
            return

        try:
            mi = psutil.Process(pid=rppid).memory_info()
            usage_mb = mi.rss / (1024*1024)
            usage = "%.2f" % usage_mb
            self._set_text(f"RAM: {usage} MB")
        except Exception:
            log.statusbar.exception("failed to get memory usage")

    def on_tab_changed(self, tab: browsertab.AbstractTab) -> None:
        """Update page ram usage if possible."""
        try:
            self.current_tab = tab
            self._show_ram_usage()
        except Exception:
            log.statusbar.exception("failed to get tab pid or show ram usage")

    def hideEvent(self, event: Optional[QHideEvent]) -> None:
        """Stop timer when widget is hidden."""
        self.timer.stop()
        super().hideEvent(qtutils.remove_optional(event))

    def showEvent(self, event: Optional[QShowEvent]) -> None:
        """Override showEvent to show time and start self.timer for updating."""
        self.timer.start(PageRamUsage.UPDATE_DELAY)
        self._show_ram_usage()
        super().showEvent(qtutils.remove_optional(event))
