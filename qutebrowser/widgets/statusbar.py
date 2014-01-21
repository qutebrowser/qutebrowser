import logging

from PyQt5.QtWidgets import (QLineEdit, QHBoxLayout, QLabel, QWidget,
                             QShortcut, QProgressBar, QSizePolicy)
from PyQt5.QtCore import pyqtSignal, Qt, QSize
from PyQt5.QtGui import QValidator, QKeySequence

class StatusBar(QWidget):
    """The statusbar at the bottom of the mainwindow"""
    hbox = None
    cmd = None
    txt = None
    prog = None
    fgcolor = 'white'
    bgcolor = 'black'
    font = 'Monospace, Courier'
    _stylesheet = """
        * {{
            background: {self.bgcolor};
            color: {self.fgcolor};
            font-family: {self.font};
        }}
    """

    def __setattr__(self, name, value):
        """Update the stylesheet if relevant attributes have been changed"""
        super().__setattr__(name, value)
        if name in ['fgcolor', 'bgcolor', 'font']:
            self.setStyleSheet(self._stylesheet.strip().format(self=self))

    # TODO: the statusbar should be a bit smaller
    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet(self._stylesheet.strip().format(self=self))
        self.hbox = QHBoxLayout(self)
        self.hbox.setContentsMargins(0, 0, 0, 0)
        self.hbox.setSpacing(0)

        self.cmd = StatusCommand(self)
        self.hbox.addWidget(self.cmd)

        self.txt = StatusText(self)
        self.hbox.addWidget(self.txt)

        self.prog = StatusProgress(self)
        self.hbox.addWidget(self.prog)

    def disp_error(self, text):
        """Displays an error in the statusbar"""
        self.bgcolor = 'red'
        self.txt.error = text

    def clear_error(self):
        """Clears a displayed error from the status bar"""
        self.bgcolor = 'black'
        self.txt.error = ''

class StatusProgress(QProgressBar):
    """ The progress bar part of the status bar"""
    bar = None
    _stylesheet = """
        QProgressBar {
            border-radius: 0px;
            border: 2px solid transparent;
            margin-left: 1px;
        }

        QProgressBar::chunk {
            background-color: white;
        }
    """

    def __init__(self, bar):
        self.bar = bar
        super().__init__(bar)

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setTextVisible(False)
        self.setStyleSheet(self._stylesheet.strip())
        self.hide()

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
            self.hide()
        else:
            self.setValue(prog)
            self.show()

    def load_finished(self, ok):
        self.hide()

class StatusText(QLabel):
    """The text part of the status bar, composed of several 'widgets'"""
    keystring = ''
    error = ''
    text = ''
    scrollperc = ''

    def __init__(self, bar):
        super().__init__(bar)
        self.setStyleSheet("padding-right: 1px")

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        self.update()

    def set_keystring(self, s):
        """Setter to be used as a Qt slot"""
        self.keystring = s

    def set_perc(self, x, y):
        """Setter to be used as a Qt slot"""
        if y == 0:
            self.scrollperc = '[top]'
        elif y == 100:
            self.scrollperc = '[bot]'
        else:
            self.scrollperc = '[{}%]'.format(y)

    def update(self):
        """Update the text displayed"""
        self.setText(' '.join([self.keystring, self.error, self.text,
                               self.scrollperc]))


class StatusCommand(QLineEdit):
    """The commandline part of the statusbar"""
    class CmdValidator(QValidator):
        """Validator to prevent the : from getting deleted"""
        def validate(self, string, pos):
            if string.startswith(':'):
                return (QValidator.Acceptable, string, pos)
            else:
                return (QValidator.Invalid, string, pos)

    got_cmd = pyqtSignal(str) # Emitted when a command is triggered by the user
    bar = None # The status bar object
    esc_pressed = pyqtSignal() # Emitted when escape is pressed
    history = [] # The command history, with newer commands at the bottom
    _tmphist = []
    _histpos = None

    def __init__(self, bar):
        super().__init__(bar)
        self.bar = bar
        self.setStyleSheet("border: 0px; padding-left: 1px")
        self.setValidator(self.CmdValidator())
        self.returnPressed.connect(self.process_cmd)
        self.textEdited.connect(self._histbrowse_stop)

        for (key, handler) in [(Qt.Key_Escape, self.esc_pressed),
                               (Qt.Key_Up, self.key_up_handler),
                               (Qt.Key_Down, self.key_down_handler),
                               (Qt.Key_Tab, self.key_tab_handler)]:
            sc = QShortcut(self)
            sc.setKey(QKeySequence(key))
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.activated.connect(handler)

    def process_cmd(self):
        """Handle the command in the status bar"""
        self._histbrowse_stop()
        text = self.text().lstrip(':')
        if not self.history or text != self.history[-1]:
            self.history.append(text)
        self.setText('')
        self.got_cmd.emit(text)

    def set_cmd(self, text):
        """Preset the statusbar to some text"""
        self.setText(':' + text)
        self.setFocus()

    def focusOutEvent(self, e):
        """Clear the statusbar text if it's explicitely unfocused"""
        if e.reason() in [Qt.MouseFocusReason, Qt.TabFocusReason,
                          Qt.BacktabFocusReason, Qt.OtherFocusReason]:
            self.setText('')
            self._histbrowse_stop()
        super().focusOutEvent(e)

    def focusInEvent(self, e):
        """Clear error message when the statusbar is focused"""
        self.bar.clear_error()
        super().focusInEvent(e)

    def _histbrowse_start(self):
        pre = self.text().strip().lstrip(':')
        logging.debug('Preset text: "{}"'.format(pre))
        if pre:
            self._tmphist = [e for e in self.history if e.startswith(pre)]
        else:
            self._tmphist = self.history
        self._histpos = len(self._tmphist) - 1

    def _histbrowse_stop(self):
        self._histpos = None

    def key_up_handler(self):
        logging.debug("history up [pre]: pos {}".format(self._histpos))
        if self._histpos is None:
            self._histbrowse_start()
        elif self._histpos <= 0:
            return
        else:
            self._histpos -= 1
        if not self._tmphist:
            return
        logging.debug("history up: {} / len {} / pos {}".format(
            self._tmphist, len(self._tmphist), self._histpos))
        self.set_cmd(self._tmphist[self._histpos])

    def key_down_handler(self):
        logging.debug("history up [pre]: pos {}".format(self._histpos,
            self._tmphist, len(self._tmphist), self._histpos))
        if (self._histpos is None or
                self._histpos >= len(self._tmphist) - 1 or
                not self._tmphist):
            return
        self._histpos += 1
        logging.debug("history up: {} / len {} / pos {}".format(
            self._tmphist, len(self._tmphist), self._histpos))
        self.set_cmd(self._tmphist[self._histpos])

    def key_tab_handler(self):
        # TODO implement tab completion
        logging.debug('tab pressed')
