"""The commandline part of the statusbar."""
import logging

from PyQt5.QtWidgets import QLineEdit, QShortcut
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QValidator, QKeySequence


class Command(QLineEdit):
    """The commandline part of the statusbar."""
    # Emitted when a command is triggered by the user
    got_cmd = pyqtSignal(str)
    statusbar = None  # The status bar object
    esc_pressed = pyqtSignal()  # Emitted when escape is pressed
    tab_pressed = pyqtSignal(bool)  # Emitted when tab is pressed (arg: shift)
    hide_completion = pyqtSignal()  # Hide completion window
    history = []  # The command history, with newer commands at the bottom
    _tmphist = []
    _histpos = None

    # FIXME won't the tab key switch to the next widget?
    # See [0] for a possible fix.
    # [0] http://www.saltycrane.com/blog/2008/01/how-to-capture-tab-key-press-event-with/ # noqa # pylint: disable=line-too-long

    def __init__(self, statusbar):
        super().__init__(statusbar)
        # FIXME
        self.statusbar = statusbar
        self.setStyleSheet("border: 0px; padding-left: 1px")
        self.setValidator(Validator())
        self.returnPressed.connect(self.process_cmd)
        self.textEdited.connect(self._histbrowse_stop)

        for (key, handler) in [
                (Qt.Key_Escape, self.esc_pressed),
                (Qt.Key_Up, self.key_up_handler),
                (Qt.Key_Down, self.key_down_handler),
                (Qt.Key_Tab | Qt.SHIFT, lambda: self.tab_pressed.emit(True)),
                (Qt.Key_Tab, lambda: self.tab_pressed.emit(False))
        ]:
            sc = QShortcut(self)
            sc.setKey(QKeySequence(key))
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.activated.connect(handler)

    def process_cmd(self):
        """Handle the command in the status bar."""
        self._histbrowse_stop()
        text = self.text().lstrip(':')
        if not self.history or text != self.history[-1]:
            self.history.append(text)
        self.setText('')
        self.got_cmd.emit(text)

    def set_cmd(self, text):
        """Preset the statusbar to some text."""
        self.setText(':' + text)
        self.setFocus()

    def append_cmd(self, text):
        """Append text to the commandline."""
        # FIXME do the right thing here
        self.setText(':' + text)
        self.setFocus()

    def focusOutEvent(self, e):
        """Clear the statusbar text if it's explicitely unfocused."""
        if e.reason() in [Qt.MouseFocusReason, Qt.TabFocusReason,
                          Qt.BacktabFocusReason, Qt.OtherFocusReason]:
            self.setText('')
            self._histbrowse_stop()
        self.hide_completion.emit()
        super().focusOutEvent(e)

    def focusInEvent(self, e):
        """Clear error message when the statusbar is focused."""
        self.statusbar.clear_error()
        super().focusInEvent(e)

    def _histbrowse_start(self):

        """Start browsing to the history.

        Called when the user presses the up/down key and wasn't browsing the
        history already.
        """

        pre = self.text().strip().lstrip(':')
        logging.debug('Preset text: "{}"'.format(pre))
        if pre:
            self._tmphist = [e for e in self.history if e.startswith(pre)]
        else:
            self._tmphist = self.history
        self._histpos = len(self._tmphist) - 1

    def _histbrowse_stop(self):
        """Stop browsing the history."""
        self._histpos = None

    def key_up_handler(self):
        """Handle Up presses (go back in history)."""
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
        """Handle Down presses (go forward in history)."""
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


class Validator(QValidator):
    """Validator to prevent the : from getting deleted"""

    def validate(self, string, pos):

        """Overrides QValidator::validate.

        string -- The string to validate.
        pos -- The current curser position.

        Returns a tuple (status, string, pos) as a QValidator should.\
        """

        if string.startswith(':'):
            return (QValidator.Acceptable, string, pos)
        else:
            return (QValidator.Invalid, string, pos)
