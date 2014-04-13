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

from PyQt5.QtCore import pyqtSignal, pyqtSlot, pyqtProperty, Qt
from PyQt5.QtWidgets import (QWidget, QLineEdit, QProgressBar, QLabel,
                             QHBoxLayout, QStackedLayout, QSizePolicy,
                             QShortcut)
from PyQt5.QtGui import QPainter, QKeySequence, QValidator

from qutebrowser.config.style import set_register_stylesheet, get_stylesheet
import qutebrowser.commands.keys as keys
from qutebrowser.utils.url import urlstring
from qutebrowser.utils.usertypes import NeighborList
from qutebrowser.commands.parsers import split_cmdline


class StatusBar(QWidget):

    """The statusbar at the bottom of the mainwindow.

    Attributes:
        cmd: The Command widget in the statusbar.
        txt: The Text widget in the statusbar.
        keystring: The KeyString widget in the statusbar.
        percentage: The Percentage widget in the statusbar.
        url: The Url widget in the statusbar.
        prog: The Progress widget in the statusbar.
        _hbox: The main QHBoxLayout.
        _stack: The QStackedLayout with cmd/txt widgets.
        _error: If there currently is an error, accessed through the error
                property.
        STYLESHEET: The stylesheet template.

    Signals:
        resized: Emitted when the statusbar has resized, so the completion
                 widget can adjust its size to it.
                 arg: The new size.
        moved: Emitted when the statusbar has moved, so the completion widget
               can move the the right position.
               arg: The new position.
    """

    resized = pyqtSignal('QRect')
    moved = pyqtSignal('QPoint')
    STYLESHEET = """
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName(self.__class__.__name__)
        self.setAttribute(Qt.WA_StyledBackground)
        set_register_stylesheet(self)

        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

        self._error = False
        self._option = None

        self._hbox = QHBoxLayout(self)
        self._hbox.setContentsMargins(0, 0, 0, 0)
        self._hbox.setSpacing(5)

        self._stack = QStackedLayout()
        self._stack.setContentsMargins(0, 0, 0, 0)

        self.cmd = _Command(self)
        self._stack.addWidget(self.cmd)

        self.txt = _Text(self)
        self._stack.addWidget(self.txt)

        self.cmd.show_cmd.connect(self._show_cmd_widget)
        self.cmd.hide_cmd.connect(self._hide_cmd_widget)
        self._hide_cmd_widget()

        self._hbox.addLayout(self._stack)
        #self._hbox.addStretch()

        self.keystring = _KeyString(self)
        self._hbox.addWidget(self.keystring)

        self.url = _Url(self)
        self._hbox.addWidget(self.url)

        self.percentage = _Percentage(self)
        self._hbox.addWidget(self.percentage)

        self.prog = _Progress(self)
        self._hbox.addWidget(self.prog)

    @pyqtProperty(bool)
    def error(self):
        """Getter for self.error, so it can be used as Qt property."""
        # pylint: disable=method-hidden
        return self._error

    @error.setter
    def error(self, val):
        """Setter for self.error, so it can be used as Qt property.

        Re-set the stylesheet after setting the value, so everything gets
        updated by Qt properly.
        """
        self._error = val
        self.setStyleSheet(get_stylesheet(self.STYLESHEET))

    def _show_cmd_widget(self):
        """Show command widget instead of temporary text."""
        self._stack.setCurrentWidget(self.cmd)
        self.clear_error()

    def _hide_cmd_widget(self):
        """Show temporary text instead of command widget."""
        self._stack.setCurrentWidget(self.txt)

    @pyqtSlot(str)
    def disp_error(self, text):
        """Display an error in the statusbar."""
        self.error = True
        self.txt.errortext = text

    @pyqtSlot()
    def clear_error(self):
        """Clear a displayed error from the status bar."""
        self.error = False
        self.txt.errortext = ''

    @pyqtSlot(str)
    def disp_tmp_text(self, text):
        """Display a temporary text.

        Args:
            text: The text to display, or an empty string to clear.
        """
        self.txt.temptext = text

    @pyqtSlot()
    def clear_tmp_text(self):
        """Clear a temporary text."""
        self.disp_tmp_text('')

    @pyqtSlot('QKeyEvent')
    def keypress(self, e):
        """Hide temporary error message if a key was pressed.

        Args:
            e: The original QKeyEvent.
        """
        if e.key() in [Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta]:
            # Only modifier pressed, don't hide yet.
            return
        self.clear_tmp_text()

    def resizeEvent(self, e):
        """Extend resizeEvent of QWidget to emit a resized signal afterwards.

        Args:
            e: The QResizeEvent.

        Emit:
            resized: Always emitted.
        """
        super().resizeEvent(e)
        self.resized.emit(self.geometry())

    def moveEvent(self, e):
        """Extend moveEvent of QWidget to emit a moved signal afterwards.

        Args:
            e: The QMoveEvent.

        Emit:
            moved: Always emitted.
        """
        super().moveEvent(e)
        self.moved.emit(e.pos())


class _Command(QLineEdit):

    """The commandline part of the statusbar.

    Attributes:
        history: The command history, with newer commands at the bottom.
        _statusbar: The statusbar (parent) QWidget.
        _shortcuts: Defined QShortcuts to prevent GCing.
        _tmphist: The temporary history for history browsing as NeighborList.
        _validator: The current command validator.

    Signals:
        got_cmd: Emitted when a command is triggered by the user.
                 arg: The command string.
        got_search: Emitted when the user started a new search.
                    arg: The search term.
        got_rev_search: Emitted when the user started a new reverse search.
                        arg: The search term.
        esc_pressed: Emitted when the escape key was pressed.
        tab_pressed: Emitted when the tab key was pressed.
                     arg: Whether shift has been pressed.
        clear_completion_selection: Emitted before the completion widget is
                                    hidden.
        hide_completion: Emitted when the completion widget should be hidden.
        show_cmd: Emitted when command input should be shown.
        hide_cmd: Emitted when command input can be hidden.
    """

    # FIXME we should probably use a proper model for the command history.

    got_cmd = pyqtSignal(str)
    got_search = pyqtSignal(str)
    got_search_rev = pyqtSignal(str)
    esc_pressed = pyqtSignal()
    tab_pressed = pyqtSignal(bool)
    clear_completion_selection = pyqtSignal()
    hide_completion = pyqtSignal()
    show_cmd = pyqtSignal()
    hide_cmd = pyqtSignal()

    # FIXME won't the tab key switch to the next widget?
    # See [0] for a possible fix.
    # [0] http://www.saltycrane.com/blog/2008/01/how-to-capture-tab-key-press-event-with/ # noqa # pylint: disable=line-too-long

    def __init__(self, statusbar):
        super().__init__(statusbar)
        # FIXME
        self._statusbar = statusbar
        self._tmphist = None
        self.setStyleSheet("""
            QLineEdit {
                border: 0px;
                padding-left: 1px;
                background-color: transparent;
            }
        """)
        self._validator = _CommandValidator(self)
        self.setValidator(self._validator)
        self.returnPressed.connect(self._on_return_pressed)
        self.textEdited.connect(self._histbrowse_stop)
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Ignored)
        self.history = []

        self._shortcuts = []
        for (key, handler) in [
                (Qt.Key_Escape, self.esc_pressed),
                (Qt.Key_Up, self._on_key_up_pressed),
                (Qt.Key_Down, self._on_key_down_pressed),
                (Qt.Key_Tab | Qt.SHIFT, lambda: self.tab_pressed.emit(True)),
                (Qt.Key_Tab, lambda: self.tab_pressed.emit(False))
        ]:
            sc = QShortcut(self)
            sc.setKey(QKeySequence(key))
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.activated.connect(handler)
            self._shortcuts.append(sc)

    def _histbrowse_start(self):
        """Start browsing to the history.

        Called when the user presses the up/down key and wasn't browsing the
        history already.
        """
        pre = self.text().strip()
        logging.debug('Preset text: "{}"'.format(pre))
        if pre:
            items = [e for e in self.history if e.startswith(pre)]
        else:
            items = self.history
        if not items:
            raise ValueError("No history found!")
        self._tmphist = NeighborList(items)
        return self._tmphist.lastitem()

    @pyqtSlot()
    def _histbrowse_stop(self):
        """Stop browsing the history."""
        self._tmphist = None

    @pyqtSlot()
    def _on_key_up_pressed(self):
        """Handle Up presses (go back in history)."""
        if self._tmphist is None:
            try:
                item = self._histbrowse_start()
            except ValueError:
                # no history
                return
        else:
            try:
                item = self._tmphist.previtem()
            except IndexError:
                # at beginning of history
                return
        if item:
            self.set_cmd_text(item)

    @pyqtSlot()
    def _on_key_down_pressed(self):
        """Handle Down presses (go forward in history)."""
        if not self._tmphist:
            return
        try:
            item = self._tmphist.nextitem()
        except IndexError:
            logging.debug("At end of history")
            return
        if item:
            self.set_cmd_text(item)

    @pyqtSlot()
    def _on_return_pressed(self):
        """Handle the command in the status bar.

        Emit:
            got_cmd: If a new cmd was entered.
            got_search: If a new search was entered.
            got_search_rev: If a new reverse search was entered.
        """
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

    @pyqtSlot(str)
    def set_cmd_text(self, text):
        """Preset the statusbar to some text.

        Args:
            text: The text to set (string).
        """
        self.setText(text)
        self.setFocus()
        self.show_cmd.emit()

    @pyqtSlot(str)
    def on_change_completed_part(self, newtext):
        """Change the part we're currently completing in the commandline.

        Args:
            text: The text to set (string).
        """
        # FIXME we should consider the cursor position.
        text = self.text()
        if text[0] in ':/?':
            prefix = text[0]
            text = text[1:]
        else:
            prefix = ''
        parts = split_cmdline(text)
        parts[-1] = newtext
        self.setText(prefix + ' '.join(parts))
        self.setFocus()
        self.show_cmd.emit()

    def focusOutEvent(self, e):
        """Clear the statusbar text if it's explicitely unfocused.

        Args:
            e: The QFocusEvent.

        Emit:
            clear_completion_selection: Always emitted.
            hide_completion: Always emitted so the completion is hidden.
        """
        if e.reason() in [Qt.MouseFocusReason, Qt.TabFocusReason,
                          Qt.BacktabFocusReason, Qt.OtherFocusReason]:
            self.setText('')
            self._histbrowse_stop()
            self.hide_cmd.emit()
        self.clear_completion_selection.emit()
        self.hide_completion.emit()
        super().focusOutEvent(e)


class _CommandValidator(QValidator):

    """Validator to prevent the : from getting deleted."""

    def validate(self, string, pos):
        """Override QValidator::validate.

        Args:
            string: The string to validate.
            pos: The current curser position.

        Return:
            A tuple (status, string, pos) as a QValidator should.
        """
        if any(string.startswith(c) for c in keys.STARTCHARS):
            return (QValidator.Acceptable, string, pos)
        else:
            return (QValidator.Invalid, string, pos)


class _Progress(QProgressBar):

    """The progress bar part of the status bar.

    Attributes:
        STYLESHEET: The stylesheet template.
    """

    # FIXME for some reason, margin-left is not shown
    STYLESHEET = """
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

    def __init__(self, parent):
        super().__init__(parent)
        set_register_stylesheet(self)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Ignored)
        self.setTextVisible(False)
        self.hide()

    @pyqtSlot()
    def on_load_started(self):
        """Clear old error and show progress, used as slot to loadStarted."""
        self.setValue(0)
        self.show()


class TextBase(QLabel):

    """A text in the statusbar.

    Unlike QLabel, the text will get elided.

    Eliding is loosly based on
    http://gedgedev.blogspot.ch/2010/12/elided-labels-in-qt.html

    Attributes:
        _elidemode: Where to elide the text.
        _elided_text: The current elided text.
    """

    def __init__(self, bar, elidemode=Qt.ElideRight):
        super().__init__(bar)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self._elidemode = elidemode
        self._elided_text = ''

    def _update_elided_text(self, width):
        """Update the elided text when necessary.

        Args:
            width: The maximal width the text should take.
        """
        self._elided_text = self.fontMetrics().elidedText(
            self.text(), self._elidemode, width, Qt.TextShowMnemonic)

    def setText(self, txt):
        """Extend QLabel::setText.

        This update the elided text after setting the text, and also works
        around a weird QLabel redrawing bug where it doesn't redraw correctly
        when the text is empty -- we explicitely need to call repaint() to
        resolve this. See http://stackoverflow.com/q/21890462/2085149

        FIXME is there a nicer way to work around this?

        Args:
            txt: The text to set (string).
        """
        super().setText(txt)
        self._update_elided_text(self.geometry().width())
        if not txt:
            self.repaint()

    def resizeEvent(self, e):
        """Extend QLabel::resizeEvent to update the elided text afterwards."""
        super().resizeEvent(e)
        self._update_elided_text(e.size().width())

    def paintEvent(self, e):
        """Override QLabel::paintEvent to draw elided text."""
        if self._elidemode == Qt.ElideNone:
            super().paintEvent(e)
        else:
            painter = QPainter(self)
            painter.drawText(0, 0, self.geometry().width(),
                             self.geometry().height(), self.alignment(),
                             self._elided_text)


class _Text(TextBase):

    """Text displayed in the statusbar.

    Attributes:
        normaltext: The "permanent" text. Never automatically cleared.
        temptext: The temporary text. Cleared on a keystroke.
        errortext: The error text. Cleared on a keystroke.
        _initializing: True if we're currently in __init__ and no text should
                       be updated yet.

        The errortext has the highest priority, i.e. it will always be shown
        when it is set. The temptext is shown when there is no error, and the
        (permanent) text is shown when there is neither a temporary text nor an
        error.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._initializing = True
        self.normaltext = ''
        self.temptext = ''
        self.errortext = ''
        self._initializing = False

    def __setattr__(self, name, val):
        """Overwrite __setattr__ to call _update_text when needed."""
        super().__setattr__(name, val)
        if not name.startswith('_') and not self._initializing:
            self._update_text()

    def _update_text(self):
        """Update QLabel text when needed.

        Called from __setattr__ if a text property changed.
        """
        for text in [self.errortext, self.temptext, self.normaltext]:
            if text:
                self.setText(text)
                break
        else:
            self.setText('')

    @pyqtSlot(str)
    def set_normaltext(self, val):
        """Setter for normaltext, to be used as Qt slot."""
        self.normaltext = val

    @pyqtSlot(str)
    def set_temptext(self, val):
        """Setter for temptext, to be used as Qt slot."""
        self.temptext = val


class _KeyString(TextBase):

    """Keychain string displayed in the statusbar."""

    pass


class _Percentage(TextBase):

    """Reading percentage displayed in the statusbar."""

    def __init__(self, parent=None):
        """Constructor. Set percentage to 0%."""
        super().__init__(parent)
        self.set_perc(0, 0)

    @pyqtSlot(int, int)
    def set_perc(self, _, y):
        """Setter to be used as a Qt slot.

        Args:
            _: The x percentage (int), currently ignored.
            y: The y percentage (int)
        """
        if y == 0:
            self.setText('[top]')
        elif y == 100:
            self.setText('[bot]')
        else:
            self.setText('[{:2}%]'.format(y))


class _Url(TextBase):

    """URL displayed in the statusbar.

    Attributes:
        _old_url: The URL displayed before the hover URL.
        _old_urltype: The type of the URL displayed before the hover URL.
        _urltype: The current URL type. One of normal/ok/error/warn/hover.
                  Accessed via the urltype property.
        STYLESHEET: The stylesheet template.
    """

    STYLESHEET = """
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
        """Override TextBase::__init__ to elide in the middle by default.

        Args:
            bar: The statusbar (parent) object.
            elidemode: How to elide the text.
        """
        super().__init__(bar, elidemode)
        self.setObjectName(self.__class__.__name__)
        set_register_stylesheet(self)
        self._urltype = None
        self._old_urltype = None
        self._old_url = None

    @pyqtProperty(str)
    def urltype(self):
        """Getter for self.urltype, so it can be used as Qt property."""
        # pylint: disable=method-hidden
        return self._urltype

    @urltype.setter
    def urltype(self, val):
        """Setter for self.urltype, so it can be used as Qt property."""
        self._urltype = val
        self.setStyleSheet(get_stylesheet(self.STYLESHEET))

    @pyqtSlot(bool)
    def on_loading_finished(self, ok):
        """Slot for cur_loading_finished. Colors the URL according to ok.

        Args:
            ok: Whether loading finished successfully (True) or not (False).
        """
        # FIXME: set color to warn if there was an SSL error
        self.urltype = 'success' if ok else 'error'

    @pyqtSlot(str)
    def set_url(self, s):
        """Setter to be used as a Qt slot.

        Args:
            s: The URL to set.
        """
        self.setText(urlstring(s))
        self.urltype = 'normal'

    # pylint: disable=unused-argument
    @pyqtSlot(str, str, str)
    def set_hover_url(self, link, title, text):
        """Setter to be used as a Qt slot.

        Saves old shown URL in self._old_url and restores it later if a link is
        "un-hovered" when it gets called with empty parameters.

        Args:
            link: The link which was hovered (string)
            title: The title of the hovered link (string)
            text: The text of the hovered link (string)
        """
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
