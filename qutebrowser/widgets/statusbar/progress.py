"""Widget to show the percentage of the page load in the statusbar."""

import qutebrowser.utils.config as config

from PyQt5.QtWidgets import QProgressBar, QSizePolicy


class Progress(QProgressBar):
    """The progress bar part of the status bar."""
    statusbar = None
    color = None
    _stylesheet = """
        QProgressBar {{
            border-radius: 0px;
            border: 2px solid transparent;
            margin-left: 1px;
        }}

        QProgressBar::chunk {{
            {color[statusbar.progress.bg.__cur__]}
        }}
    """

    def __init__(self, statusbar):
        self.statusbar = statusbar
        super().__init__(statusbar)

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Ignored)
        self.setTextVisible(False)
        self.color = config.colordict.getraw('statusbar.progress.bg')
        self.hide()

    def __setattr__(self, name, value):
        """Update the stylesheet if relevant attributes have been changed."""
        super().__setattr__(name, value)
        if name == 'color' and value is not None:
            config.colordict['statusbar.progress.bg.__cur__'] = value
            self.setStyleSheet(config.get_stylesheet(self._stylesheet))

    def set_progress(self, prog):
        """Set the progress of the bar and show/hide it if necessary."""
        # TODO display failed loading in some meaningful way?
        if prog == 100:
            self.setValue(prog)
        else:
            color = config.colordict.getraw('status.progress.bg')
            if self.color != color:
                self.color = color
            self.setValue(prog)
            self.show()

    def load_finished(self, ok):

        """Hide the progress bar or color it red, depending on ok.

        Slot for the loadFinished signal of a QWebView.
        """

        if ok:
            self.color = config.colordict.getraw('status.progress.bg')
            self.hide()
        else:
            self.color = config.colordict.getraw('statusbar.progress.bg.error')
