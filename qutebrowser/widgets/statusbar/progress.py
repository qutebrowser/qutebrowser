from PyQt5.QtWidgets import QProgressBar, QSizePolicy
from PyQt5.QtCore import QSize

class Progress(QProgressBar):
    """ The progress bar part of the status bar"""
    bar = None
    color = 'white'
    _stylesheet = """
        QProgressBar {{
            border-radius: 0px;
            border: 2px solid transparent;
            margin-left: 1px;
        }}

        QProgressBar::chunk {{
            background-color: {self.color};
        }}
    """

    def __init__(self, bar):
        self.bar = bar
        super().__init__(bar)

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setTextVisible(False)
        self.setStyleSheet(self._stylesheet.strip().format(self=self))
        self.hide()

    def __setattr__(self, name, value):
        """Update the stylesheet if relevant attributes have been changed"""
        super().__setattr__(name, value)
        if name == 'color':
            self.setStyleSheet(self._stylesheet.strip().format(self=self))

    def minimumSizeHint(self):
        status_size = self.bar.size()
        return QSize(100, status_size.height())

    def sizeHint(self):
        return self.minimumSizeHint()

    def set_progress(self, prog):
        """Sets the progress of the bar and shows/hides it if necessary"""
        # TODO display failed loading in some meaningful way?
        if prog == 100:
            self.setValue(prog)
        else:
            if self.color != 'white':
                self.color = 'white'
            self.setValue(prog)
            self.show()

    def load_finished(self, ok):
        if ok:
            self.hide()
        else:
            self.color = 'red'
