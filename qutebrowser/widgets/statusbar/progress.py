import qutebrowser.utils.config as config

from PyQt5.QtWidgets import QProgressBar, QSizePolicy
from PyQt5.QtCore import QSize


class Progress(QProgressBar):
    """ The progress bar part of the status bar"""
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

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setTextVisible(False)
        self.color = config.colordict.getraw('statusbar.progress.bg')
        self.hide()

    def __setattr__(self, name, value):
        """Update the stylesheet if relevant attributes have been changed"""
        super().__setattr__(name, value)
        if name == 'color' and value is not None:
            config.colordict['statusbar.progress.bg.__cur__'] = value
            self.setStyleSheet(config.get_stylesheet(self._stylesheet))

    def minimumSizeHint(self):
        status_size = self.statusbar.size()
        return QSize(100, status_size.height())

    def sizeHint(self):
        return self.minimumSizeHint()

    def set_progress(self, prog):
        """Sets the progress of the bar and shows/hides it if necessary"""
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
        if ok:
            self.hide()
        else:
            self.color = config.colordict.getraw('statusbar.progress.bg.error')
