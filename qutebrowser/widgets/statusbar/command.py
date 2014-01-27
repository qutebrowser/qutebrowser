import logging

from PyQt5.QtWidgets import QLineEdit, QShortcut
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QValidator, QKeySequence

from qutebrowser.commands.utils import CommandCompletionModel

class Command(QLineEdit):
    """The commandline part of the statusbar"""

    got_cmd = pyqtSignal(str) # Emitted when a command is triggered by the user
    bar = None # The status bar object
    esc_pressed = pyqtSignal() # Emitted when escape is pressed
    tab_pressed = pyqtSignal(bool) # Emitted when tab is pressed (arg: shift)
    hide_completion = pyqtSignal() # Hide completion window
    history = [] # The command history, with newer commands at the bottom
    _tmphist = []
    _histpos = None

    # FIXME won't the tab key switch to the next widget?
    # See http://www.saltycrane.com/blog/2008/01/how-to-capture-tab-key-press-event-with/
    # for a possible fix.

    def __init__(self, bar):
        super().__init__(bar)
        # FIXME
        self.bar = bar
        self.setStyleSheet("border: 0px; padding-left: 1px")
        self.setValidator(Validator())
        self.returnPressed.connect(self.process_cmd)
        self.textEdited.connect(self._histbrowse_stop)

        for (key, handler) in [(Qt.Key_Escape, self.esc_pressed),
                               (Qt.Key_Up, self.key_up_handler),
                               (Qt.Key_Down, self.key_down_handler),
                               (Qt.Key_Tab | Qt.SHIFT, self.key_stab_handler),
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

    def append_cmd(self, text):
        """Append text to the commandline"""
        # FIXME do the right thing here
        self.setText(':' + text)
        self.setFocus()

    def focusOutEvent(self, e):
        """Clear the statusbar text if it's explicitely unfocused"""
        if e.reason() in [Qt.MouseFocusReason, Qt.TabFocusReason,
                          Qt.BacktabFocusReason, Qt.OtherFocusReason]:
            self.setText('')
            self._histbrowse_stop()
        self.hide_completion.emit()
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
        self.tab_pressed.emit(False)

    def key_stab_handler(self):
        self.tab_pressed.emit(True)

class Validator(QValidator):
    """Validator to prevent the : from getting deleted"""
    def validate(self, string, pos):
        if string.startswith(':'):
            return (QValidator.Acceptable, string, pos)
        else:
            return (QValidator.Invalid, string, pos)

