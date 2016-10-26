# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from PyQt5.QtCore import pyqtSignal, pyqtSlot, pyqtProperty, Qt, QSize, QTimer
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QStackedLayout, QSizePolicy

from qutebrowser.config import config, style
from qutebrowser.utils import usertypes, log, objreg, utils
from qutebrowser.mainwindow.statusbar import (command, progress, keystring,
                                              percentage, url, tabindex)
from qutebrowser.mainwindow.statusbar import text as textwidget


CaretMode = usertypes.enum('CaretMode', ['off', 'on', 'selection'])


class StatusBar(QWidget):

    """The statusbar at the bottom of the mainwindow.

    Attributes:
        txt: The Text widget in the statusbar.
        keystring: The KeyString widget in the statusbar.
        percentage: The Percentage widget in the statusbar.
        url: The UrlText widget in the statusbar.
        prog: The Progress widget in the statusbar.
        cmd: The Command widget in the statusbar.
        _hbox: The main QHBoxLayout.
        _stack: The QStackedLayout with cmd/txt widgets.
        _win_id: The window ID the statusbar is associated with.

    Class attributes:
        _prompt_active: If we're currently in prompt-mode.

                        For some reason we need to have this as class attribute
                        so pyqtProperty works correctly.

        _insert_active: If we're currently in insert mode.

                        For some reason we need to have this as class attribute
                        so pyqtProperty works correctly.

        _command_active: If we're currently in command mode.

                         For some reason we need to have this as class
                         attribute so pyqtProperty works correctly.

        _caret_mode: The current caret mode (off/on/selection).

                     For some reason we need to have this as class attribute
                     so pyqtProperty works correctly.

    Signals:
        resized: Emitted when the statusbar has resized, so the completion
                 widget can adjust its size to it.
                 arg: The new size.
        moved: Emitted when the statusbar has moved, so the completion widget
               can move to the right position.
               arg: The new position.
    """

    resized = pyqtSignal('QRect')
    moved = pyqtSignal('QPoint')
    _severity = None
    _prompt_active = False
    _insert_active = False
    _command_active = False
    _caret_mode = CaretMode.off

    STYLESHEET = """

        QWidget#StatusBar,
        QWidget#StatusBar QLabel,
        QWidget#StatusBar QLineEdit {
            font: {{ font['statusbar'] }};
            background-color: {{ color['statusbar.bg'] }};
            color: {{ color['statusbar.fg'] }};
        }

        QWidget#StatusBar[caret_mode="on"],
        QWidget#StatusBar[caret_mode="on"] QLabel,
        QWidget#StatusBar[caret_mode="on"] QLineEdit {
            color: {{ color['statusbar.fg.caret'] }};
            background-color: {{ color['statusbar.bg.caret'] }};
        }

        QWidget#StatusBar[caret_mode="selection"],
        QWidget#StatusBar[caret_mode="selection"] QLabel,
        QWidget#StatusBar[caret_mode="selection"] QLineEdit {
            color: {{ color['statusbar.fg.caret-selection'] }};
            background-color: {{ color['statusbar.bg.caret-selection'] }};
        }

        QWidget#StatusBar[prompt_active="true"],
        QWidget#StatusBar[prompt_active="true"] QLabel,
        QWidget#StatusBar[prompt_active="true"] QLineEdit {
            color: {{ color['prompts.fg'] }};
            background-color: {{ color['prompts.bg'] }};
        }

        QWidget#StatusBar[insert_active="true"],
        QWidget#StatusBar[insert_active="true"] QLabel,
        QWidget#StatusBar[insert_active="true"] QLineEdit {
            color: {{ color['statusbar.fg.insert'] }};
            background-color: {{ color['statusbar.bg.insert'] }};
        }

        QWidget#StatusBar[command_active="true"],
        QWidget#StatusBar[command_active="true"] QLabel,
        QWidget#StatusBar[command_active="true"] QLineEdit {
            color: {{ color['statusbar.fg.command'] }};
            background-color: {{ color['statusbar.bg.command'] }};
        }

    """

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        objreg.register('statusbar', self, scope='window', window=win_id)
        self.setObjectName(self.__class__.__name__)
        self.setAttribute(Qt.WA_StyledBackground)
        style.set_register_stylesheet(self)

        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

        self._win_id = win_id
        self._option = None

        self._hbox = QHBoxLayout(self)
        self.set_hbox_padding()
        objreg.get('config').changed.connect(self.set_hbox_padding)
        self._hbox.setSpacing(5)

        self._stack = QStackedLayout()
        self._hbox.addLayout(self._stack)
        self._stack.setContentsMargins(0, 0, 0, 0)

        self.cmd = command.Command(win_id)
        self._stack.addWidget(self.cmd)
        objreg.register('status-command', self.cmd, scope='window',
                        window=win_id)

        self.txt = textwidget.Text()
        self._stack.addWidget(self.txt)

        self.cmd.show_cmd.connect(self._show_cmd_widget)
        self.cmd.hide_cmd.connect(self._hide_cmd_widget)
        self._hide_cmd_widget()

        self.keystring = keystring.KeyString()
        self._hbox.addWidget(self.keystring)

        self.url = url.UrlText()
        self._hbox.addWidget(self.url)

        self.percentage = percentage.Percentage()
        self._hbox.addWidget(self.percentage)

        self.tabindex = tabindex.TabIndex()
        self._hbox.addWidget(self.tabindex)

        # We add a parent to Progress here because it calls self.show() based
        # on some signals, and if that happens before it's added to the layout,
        # it will quickly blink up as independent window.
        self.prog = progress.Progress(self)
        self._hbox.addWidget(self.prog)

        objreg.get('config').changed.connect(self.maybe_hide)
        QTimer.singleShot(0, self.maybe_hide)

    def __repr__(self):
        return utils.get_repr(self)

    @config.change_filter('ui', 'hide-statusbar')
    def maybe_hide(self):
        """Hide the statusbar if it's configured to do so."""
        hide = config.get('ui', 'hide-statusbar')
        if hide:
            self.hide()
        else:
            self.show()

    @config.change_filter('ui', 'statusbar-padding')
    def set_hbox_padding(self):
        padding = config.get('ui', 'statusbar-padding')
        self._hbox.setContentsMargins(padding.left, 0, padding.right, 0)

    @pyqtProperty(bool)
    def prompt_active(self):
        """Getter for self.prompt_active, so it can be used as Qt property."""
        return self._prompt_active

    @pyqtProperty(bool)
    def command_active(self):
        """Getter for self.command_active, so it can be used as Qt property."""
        return self._command_active

    @pyqtProperty(bool)
    def insert_active(self):
        """Getter for self.insert_active, so it can be used as Qt property."""
        return self._insert_active

    @pyqtProperty(str)
    def caret_mode(self):
        """Getter for self._caret_mode, so it can be used as Qt property."""
        return self._caret_mode.name

    def set_mode_active(self, mode, val):
        """Setter for self.{insert,command,caret}_active.

        Re-set the stylesheet after setting the value, so everything gets
        updated by Qt properly.
        """
        if mode == usertypes.KeyMode.insert:
            log.statusbar.debug("Setting insert_active to {}".format(val))
            self._insert_active = val
        if mode == usertypes.KeyMode.command:
            log.statusbar.debug("Setting command_active to {}".format(val))
            self._command_active = val
        elif mode in [usertypes.KeyMode.prompt, usertypes.KeyMode.yesno]:
            log.statusbar.debug("Setting prompt_active to {}".format(val))
            self._prompt_active = val
        elif mode == usertypes.KeyMode.caret:
            tab = objreg.get('tabbed-browser', scope='window',
                             window=self._win_id).currentWidget()
            log.statusbar.debug("Setting caret_mode - val {}, selection "
                                "{}".format(val, tab.caret.selection_enabled))
            if val:
                if tab.caret.selection_enabled:
                    self._set_mode_text("{} selection".format(mode.name))
                    self._caret_mode = CaretMode.selection
                else:
                    self._set_mode_text(mode.name)
                    self._caret_mode = CaretMode.on
            else:
                self._caret_mode = CaretMode.off
        self.setStyleSheet(style.get_stylesheet(self.STYLESHEET))

    def _set_mode_text(self, mode):
        """Set the mode text."""
        text = "-- {} MODE --".format(mode.upper())
        self.txt.set_text(self.txt.Text.normal, text)

    def _show_cmd_widget(self):
        """Show command widget instead of temporary text."""
        self._stack.setCurrentWidget(self.cmd)
        self.show()

    def _hide_cmd_widget(self):
        """Show temporary text instead of command widget."""
        log.statusbar.debug("Hiding cmd widget")
        self._stack.setCurrentWidget(self.txt)
        self.maybe_hide()

    @pyqtSlot(str)
    def set_text(self, val):
        """Set a normal (persistent) text in the status bar."""
        self.txt.set_text(self.txt.Text.normal, val)

    @pyqtSlot(usertypes.KeyMode)
    def on_mode_entered(self, mode):
        """Mark certain modes in the commandline."""
        keyparsers = objreg.get('keyparsers', scope='window',
                                window=self._win_id)
        if keyparsers[mode].passthrough:
            self._set_mode_text(mode.name)
        if mode in [usertypes.KeyMode.insert,
                    usertypes.KeyMode.command,
                    usertypes.KeyMode.caret,
                    usertypes.KeyMode.prompt,
                    usertypes.KeyMode.yesno]:
            self.set_mode_active(mode, True)

    @pyqtSlot(usertypes.KeyMode, usertypes.KeyMode)
    def on_mode_left(self, old_mode, new_mode):
        """Clear marked mode."""
        keyparsers = objreg.get('keyparsers', scope='window',
                                window=self._win_id)
        if keyparsers[old_mode].passthrough:
            if keyparsers[new_mode].passthrough:
                self._set_mode_text(new_mode.name)
            else:
                self.txt.set_text(self.txt.Text.normal, '')
        if old_mode in [usertypes.KeyMode.insert,
                        usertypes.KeyMode.command,
                        usertypes.KeyMode.caret,
                        usertypes.KeyMode.prompt,
                        usertypes.KeyMode.yesno]:
            self.set_mode_active(old_mode, False)

    def resizeEvent(self, e):
        """Extend resizeEvent of QWidget to emit a resized signal afterwards.

        Args:
            e: The QResizeEvent.
        """
        super().resizeEvent(e)
        self.resized.emit(self.geometry())

    def moveEvent(self, e):
        """Extend moveEvent of QWidget to emit a moved signal afterwards.

        Args:
            e: The QMoveEvent.
        """
        super().moveEvent(e)
        self.moved.emit(e.pos())

    def minimumSizeHint(self):
        """Set the minimum height to the text height plus some padding."""
        padding = config.get('ui', 'statusbar-padding')
        width = super().minimumSizeHint().width()
        height = self.fontMetrics().height() + padding.top + padding.bottom
        return QSize(width, height)
