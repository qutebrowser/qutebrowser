# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Widgets needed in the qutebrowser statusbar."""

import logging

from PyQt5.QtCore import pyqtSignal, Qt, pyqtProperty
from PyQt5.QtWidgets import (QLineEdit, QShortcut, QHBoxLayout, QWidget,
                             QSizePolicy, QProgressBar, QLabel, QStyle,
                             QStyleOption)
from PyQt5.QtGui import QValidator, QKeySequence, QPainter

import qutebrowser.utils.config as config
import qutebrowser.commands.keys as keys
from qutebrowser.utils.url import urlstring


class StatusBar(QWidget):

    """The statusbar at the bottom of the mainwindow."""

    hbox = None
    cmd = None
    txt = None
    keystring = None
    percentage = None
    url = None
    prog = None
    resized = pyqtSignal('QRect')
    moved = pyqtSignal('QPoint')
    _error = False
    _option = None
    _stylesheet = """
        QWidget#StatusBar[error="false"] {{
            {color[statusbar.bg]}
        }}

        QWidget#StatusBar[error="true"] {{
            {color[statusbar.bg.error]}
        }}

        QWidget {{
            {color[statusbar.fg]}
            {font[statusbar]}
        }}
    """

    # TODO: the statusbar should be a bit smaller
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName(self.__class__.__name__)
        self.setStyleSheet(config.get_stylesheet(self._stylesheet))

        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

        self.hbox = QHBoxLayout(self)
        self.hbox.setContentsMargins(0, 0, 0, 0)
        self.hbox.setSpacing(5)

        self.cmd = Command(self)
        self.hbox.addWidget(self.cmd)

        self.txt = Text(self)
        self.hbox.addWidget(self.txt)
        self.hbox.addStretch()

        self.keystring = KeyString(self)
        self.hbox.addWidget(self.keystring)

        self.url = Url(self)
        self.hbox.addWidget(self.url)

        self.percentage = Percentage(self)
        self.hbox.addWidget(self.percentage)

        self.prog = Progress(self)
        self.hbox.addWidget(self.prog)

    @pyqtProperty(bool)
    def error(self):
        """Getter for self.error, so it can be used as Qt property."""
        # pylint: disable=method-hidden
        return self._error

    @error.setter
    def error(self, val):
        """Setter for self.error, so it can be used as Qt property.

        Re-sets the stylesheet after setting the value, so everything gets
        updated by Qt properly.

        """
        self._error = val
        self.setStyleSheet(config.get_stylesheet(self._stylesheet))

    def paintEvent(self, e):
        """Override QWIidget.paintEvent to handle stylesheets."""
        # pylint: disable=unused-argument
        self._option = QStyleOption()
        self._option.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, self._option,
                                   painter, self)

    def disp_error(self, text):
        """Displaysan error in the statusbar."""
        self.error = True
        self.txt.set_error(text)

    def clear_error(self):
        """Clear a displayed error from the status bar."""
        self.error = False
        self.txt.clear_error()

    def resizeEvent(self, e):
        """Extend resizeEvent of QWidget to emit a resized signal afterwards.

        e -- The QResizeEvent.

        """
        super().resizeEvent(e)
        self.resized.emit(self.geometry())

    def moveEvent(self, e):
        """Extend moveEvent of QWidget to emit a moved signal afterwards.

        e -- The QMoveEvent.

        """
        super().moveEvent(e)
        self.moved.emit(e.pos())


class Command(QLineEdit):

    """The commandline part of the statusbar."""

    # Emitted when a command is triggered by the user
    got_cmd = pyqtSignal(str)
    # Emitted for searches triggered by the user
    got_search = pyqtSignal(str)
    got_search_rev = pyqtSignal(str)
    statusbar = None  # The status bar object
    esc_pressed = pyqtSignal()  # Emitted when escape is pressed
    tab_pressed = pyqtSignal(bool)  # Emitted when tab is pressed (arg: shift)
    hide_completion = pyqtSignal()  # Hide completion window
    history = []  # The command history, with newer commands at the bottom
    _shortcuts = []
    _tmphist = []
    _histpos = None

    # FIXME won't the tab key switch to the next widget?
    # See [0] for a possible fix.
    # [0] http://www.saltycrane.com/blog/2008/01/how-to-capture-tab-key-press-event-with/ # noqa # pylint: disable=line-too-long

    def __init__(self, statusbar):
        super().__init__(statusbar)
        # FIXME
        self.statusbar = statusbar
        self.setStyleSheet("""
            QLineEdit {
                border: 0px;
                padding-left: 1px;
                background-color: transparent;
            }
        """)
        self.setValidator(CommandValidator())
        self.returnPressed.connect(self.process_cmdline)
        self.textEdited.connect(self._histbrowse_stop)
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Ignored)

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
            self._shortcuts.append(sc)

    def process_cmdline(self):
        """Handle the command in the status bar."""
        signals = {
            ':': self.got_cmd,
            '/': self.got_search,
            '?': self.got_search_rev,
        }
        self._histbrowse_stop()
        text = self.text()
        if not self.history or text != self.history[-1]:
            self.history.append(text)
        self.setText('')
        if text[0] in signals:
            signals[text[0]].emit(text.lstrip(text[0]))

    def set_cmd(self, text):
        """Preset the statusbar to some text."""
        self.setText(text)
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
        pre = self.text().strip()
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


class CommandValidator(QValidator):

    """Validator to prevent the : from getting deleted."""

    def validate(self, string, pos):
        """Override QValidator::validate.

        string -- The string to validate.
        pos -- The current curser position.

        Return a tuple (status, string, pos) as a QValidator should.

        """
        if any(string.startswith(c) for c in keys.startchars):
            return (QValidator.Acceptable, string, pos)
        else:
            return (QValidator.Invalid, string, pos)


class Progress(QProgressBar):

    """The progress bar part of the status bar."""

    statusbar = None
    # FIXME for some reason, margin-left is not shown
    _stylesheet = """
        QProgressBar {{
            border-radius: 0px;
            border: 2px solid transparent;
            margin-left: 1px;
            background-color: transparent;
        }}

        QProgressBar::chunk {{
            {color[statusbar.progress.bg]}
        }}
    """

    def __init__(self, statusbar):
        super().__init__(statusbar)
        self.statusbar = statusbar
        self.setStyleSheet(config.get_stylesheet(self._stylesheet))
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Ignored)
        self.setTextVisible(False)
        self.hide()

    def on_load_started(self):
        """Clear old error and show progress, used as slot to loadStarted."""
        self.setValue(0)
        self.show()


class TextBase(QLabel):

    """A text in the statusbar.

    Unlike QLabel, the text will get elided.

    Eliding is loosly based on
    http://gedgedev.blogspot.ch/2010/12/elided-labels-in-qt.html

    """

    elidemode = None
    _elided_text = None

    def __init__(self, bar, elidemode=Qt.ElideRight):
        super().__init__(bar)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self.elidemode = elidemode

    def setText(self, txt):
        """Extend QLabel::setText to update the elided text afterwards."""
        super().setText(txt)
        self._update_elided_text(self.geometry().width())

    def resizeEvent(self, e):
        """Extend QLabel::resizeEvent to update the elided text afterwards."""
        super().resizeEvent(e)
        self._update_elided_text(e.size().width())

    def _update_elided_text(self, width):
        """Update the elided text when necessary.

        width -- The maximal width the text should take.

        """
        self._elided_text = self.fontMetrics().elidedText(
            self.text(), self.elidemode, width, Qt.TextShowMnemonic)

    def paintEvent(self, e):
        """Override QLabel::paintEvent to draw elided text."""
        if self.elidemode == Qt.ElideNone:
            super().paintEvent(e)
        else:
            painter = QPainter(self)
            painter.drawText(0, 0, self.geometry().width(),
                             self.geometry().height(), self.alignment(),
                             self._elided_text)


class Text(TextBase):

    """Text displayed in the statusbar."""

    old_text = ''

    def set_error(self, text):
        """Display an error message and save current text in old_text."""
        self.old_text = self.text()
        self.setText(text)

    def clear_error(self):
        """Clear a displayed error message."""
        self.setText(self.old_text)


class KeyString(TextBase):

    """Keychain string displayed in the statusbar."""

    pass


class Percentage(TextBase):

    """Reading percentage displayed in the statusbar."""

    def set_perc(self, x, y):
        """Setter to be used as a Qt slot."""
        # pylint: disable=unused-argument
        if y == 0:
            self.setText('[top]')
        elif y == 100:
            self.setText('[bot]')
        else:
            self.setText('[{:2}%]'.format(y))


class Url(TextBase):

    """URL displayed in the statusbar."""

    _old_url = None
    _old_urltype = None
    _urltype = None  # 'normal', 'ok', 'error', 'warn, 'hover'

    _stylesheet = """
        QLabel#Url[urltype="normal"] {{
            {color[statusbar.url.fg]}
        }}

        QLabel#Url[urltype="success"] {{
            {color[statusbar.url.fg.success]}
        }}

        QLabel#Url[urltype="error"] {{
            {color[statusbar.url.fg.error]}
        }}

        QLabel#Url[urltype="warn"] {{
            {color[statusbar.url.fg.warn]}
        }}

        QLabel#Url[urltype="hover"] {{
            {color[statusbar.url.fg.hover]}
        }}
    """

    def __init__(self, bar, elidemode=Qt.ElideMiddle):
        """Override TextBase::__init__ to elide in the middle by default."""
        super().__init__(bar, elidemode)
        self.setObjectName(self.__class__.__name__)
        self.setStyleSheet(config.get_stylesheet(self._stylesheet))

    @pyqtProperty(str)
    def urltype(self):
        """Getter for self.urltype, so it can be used as Qt property."""
        # pylint: disable=method-hidden
        return self._urltype

    @urltype.setter
    def urltype(self, val):
        """Setter for self.urltype, so it can be used as Qt property."""
        self._urltype = val
        self.setStyleSheet(config.get_stylesheet(self._stylesheet))

    def on_loading_finished(self, ok):
        """Slot for cur_loading_finished. Colors the URL according to ok."""
        # FIXME: set color to warn if there was an SSL error
        self.urltype = 'success' if ok else 'error'

    def set_url(self, s):
        """Setter to be used as a Qt slot."""
        self.setText(urlstring(s))
        self.urltype = 'normal'

    def set_hover_url(self, link, title, text):
        """Setter to be used as a Qt slot.

        Saves old shown URL in self._old_url and restores it later if a link is
        "un-hovered" when it gets called with empty parameters.

        """
        # pylint: disable=unused-argument
        if link:
            if self._old_url is None:
                self._old_url = self.text()
            if self._old_urltype is None:
                self._old_urltype = self._urltype
            self.urltype = 'hover'
            self.setText(link)
        else:
            self.setText(self._old_url)
            self.urltype = self._old_urltype
            self._old_url = None
            self._old_urltype = None
