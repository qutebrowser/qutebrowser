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

"""The main statusbar widget."""

from collections import deque
from datetime import datetime

from PyQt5.QtCore import pyqtSignal, pyqtSlot, pyqtProperty, Qt, QTimer
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QStackedLayout, QSizePolicy

import qutebrowser.keyinput.modeman as modeman
import qutebrowser.config.config as config
from qutebrowser.utils.log import statusbar as logger
from qutebrowser.widgets.statusbar._command import Command
from qutebrowser.widgets.statusbar._progress import Progress
from qutebrowser.widgets.statusbar._text import Text
from qutebrowser.widgets.statusbar._keystring import KeyString
from qutebrowser.widgets.statusbar._percentage import Percentage
from qutebrowser.widgets.statusbar._url import Url
from qutebrowser.widgets.statusbar._prompt import Prompt
from qutebrowser.config.style import set_register_stylesheet, get_stylesheet


class StatusBar(QWidget):

    """The statusbar at the bottom of the mainwindow.

    Class attributes:
        STYLESHEET: The stylesheet template.

    Attributes:
        cmd: The Command widget in the statusbar.
        txt: The Text widget in the statusbar.
        keystring: The KeyString widget in the statusbar.
        percentage: The Percentage widget in the statusbar.
        url: The Url widget in the statusbar.
        prog: The Progress widget in the statusbar.
        _hbox: The main QHBoxLayout.
        _stack: The QStackedLayout with cmd/txt widgets.
        _text_queue: A deque of (error, text) tuples to be displayed.
                     error: True if message is an error, False otherwise
        _text_pop_timer: A QTimer displaying the error messages.
        _last_text_time: The timestamp where a message was last displayed.
        _timer_was_active: Whether the _text_pop_timer was active before hiding
                           the command widget.

    Class attributes:
        _error: If there currently is an error, accessed through the error
                property.

                For some reason we need to have this as class attribute so
                pyqtProperty works correctly.

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
    _error = False

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

        self._option = None
        self._last_text_time = None

        self._hbox = QHBoxLayout(self)
        self._hbox.setContentsMargins(0, 0, 0, 0)
        self._hbox.setSpacing(5)

        self._stack = QStackedLayout()
        self._stack.setContentsMargins(0, 0, 0, 0)

        self.cmd = Command(self)
        self._stack.addWidget(self.cmd)

        self.txt = Text(self)
        self._stack.addWidget(self.txt)
        self._timer_was_active = False
        self._text_queue = deque()
        self._text_pop_timer = QTimer()
        self._text_pop_timer.setInterval(config.get('ui', 'message-timeout'))
        self._text_pop_timer.timeout.connect(self._pop_text)

        self.prompt = Prompt(self)
        self._stack.addWidget(self.prompt)

        self.cmd.show_cmd.connect(self._show_cmd_widget)
        self.cmd.hide_cmd.connect(self._hide_cmd_widget)
        self._hide_cmd_widget()
        self.prompt.show_prompt.connect(self._show_prompt_widget)
        self.prompt.hide_prompt.connect(self._hide_prompt_widget)
        self._hide_prompt_widget()

        self._hbox.addLayout(self._stack)

        self.keystring = KeyString(self)
        self._hbox.addWidget(self.keystring)

        self.url = Url(self)
        self._hbox.addWidget(self.url)

        self.percentage = Percentage(self)
        self._hbox.addWidget(self.percentage)

        self.prog = Progress(self)
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

    def _pop_text(self):
        """Display a text in the statusbar and pop it from _text_queue."""
        try:
            error, text = self._text_queue.popleft()
        except IndexError:
            self.error = False
            self.txt.temptext = ''
            self._text_pop_timer.stop()
            return
        logger.debug("Displaying {} message: {}".format(
            'error' if error else 'text', text))
        logger.debug("Remaining: {}".format(self._text_queue))
        self.error = error
        self.txt.temptext = text

    def _show_cmd_widget(self):
        """Show command widget instead of temporary text."""
        self.error = False
        if self._text_pop_timer.isActive():
            self._timer_was_active = True
        self._text_pop_timer.stop()
        self._stack.setCurrentWidget(self.cmd)

    def _hide_cmd_widget(self):
        """Show temporary text instead of command widget."""
        logger.debug("Hiding cmd widget, queue: {}".format(self._text_queue))
        if self._timer_was_active:
            # Restart the text pop timer if it was active before hiding.
            self._pop_text()
            self._text_pop_timer.start()
            self._timer_was_active = False
        self._stack.setCurrentWidget(self.txt)

    def _show_prompt_widget(self):
        """Show prompt widget instead of temporary text."""
        self.error = False
        if self._text_pop_timer.isActive():
            self._timer_was_active = True
        self._text_pop_timer.stop()
        self._stack.setCurrentWidget(self.prompt)

    def _hide_prompt_widget(self):
        """Show temporary text instead of prompt widget."""
        logger.debug("Hiding prompt widget, queue: {}".format(
            self._text_queue))
        if self._timer_was_active:
            # Restart the text pop timer if it was active before hiding.
            self._pop_text()
            self._text_pop_timer.start()
            self._timer_was_active = False
        self._stack.setCurrentWidget(self.txt)

    def _disp_text(self, text, error, queue=False):
        """Inner logic for disp_error and disp_temp_text.

        Args:
            text: The message to display.
            error: Whether it's an error message (True) or normal text (False)
            queue: If set, message gets queued rather than being displayed
                   immediately.
        """
        logger.debug("Displaying text: {} (error={})".format(text, error))
        now = datetime.now()
        mindelta = config.get('ui', 'message-timeout')
        delta = (None if self._last_text_time is None
                 else now - self._last_text_time)
        self._last_text_time = now
        logger.debug("queue: {} / delta: {}".format(self._text_queue, delta))
        if not self._text_queue and (delta is None or delta.total_seconds() *
                                     1000.0 > mindelta):
            # If the queue is empty and we didn't print messages for long
            # enough, we can take the short route and display the message
            # immediately. We then start the pop_timer only to restore the
            # normal state in 2 seconds.
            logger.debug("Displaying immediately")
            self.error = error
            self.txt.temptext = text
            self._text_pop_timer.start()
        elif self._text_queue and self._text_queue[-1] == (error, text):
            # If we get the same message multiple times in a row and we're
            # still displaying it *anyways* we ignore the new one
            logger.debug("ignoring")
        elif not queue:
            # This message is a reaction to a keypress and should be displayed
            # immediately, temporarely interrupting the message queue.
            # We display this immediately and restart the timer.to clear it and
            # display the rest of the queue later.
            logger.debug("Moving to beginning of queue")
            self.error = error
            self.txt.temptext = text
            self._text_pop_timer.start()
        else:
            # There are still some messages to be displayed, so we queue this
            # up.
            logger.debug("queueing")
            self._text_queue.append((error, text))
            self._text_pop_timer.start()

    @pyqtSlot(str, bool)
    def disp_error(self, text, queue=False):
        """Display an error in the statusbar.

        Args:
            text: The message to display.
            queue: If set, message gets queued rather than being displayed
                   immediately.
        """
        self._disp_text(text, True, queue)

    @pyqtSlot(str, bool)
    def disp_temp_text(self, text, queue):
        """Display a temporary text in the statusbar.

        Args:
            text: The message to display.
            queue: If set, message gets queued rather than being displayed
                   immediately.
        """
        self._disp_text(text, False, queue)

    @pyqtSlot(str)
    def set_text(self, val):
        """Set a normal (persistent) text in the status bar."""
        self.txt.normaltext = val

    @pyqtSlot(str)
    def on_mode_entered(self, mode):
        """Mark certain modes in the commandline."""
        if mode in modeman.instance().passthrough:
            self.txt.normaltext = "-- {} MODE --".format(mode.upper())

    @pyqtSlot(str)
    def on_mode_left(self, mode):
        """Clear marked mode."""
        if mode in modeman.instance().passthrough:
            self.txt.normaltext = ""

    @pyqtSlot(str)
    def on_statusbar_message(self, val):
        """Called when javascript tries to set a statusbar message.

        For some reason, this is emitted a lot with an empty string during page
        load, so we currently ignore these and thus don't support clearing the
        message, which is a bit unfortunate...
        """
        if val:
            self.txt.temptext = val

    @pyqtSlot(str, str)
    def on_config_changed(self, section, option):
        """Update message timeout when config changed."""
        if section == 'ui' and option == 'message-timeout':
            self._text_pop_timer.setInterval(config.get('ui',
                                                        'message-timeout'))

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
