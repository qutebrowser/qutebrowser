# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import enum
import attr
from PyQt5.QtCore import (pyqtSignal, pyqtSlot,  # type: ignore[attr-defined]
                          pyqtProperty, Qt, QSize, QTimer)
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QStackedLayout, QSizePolicy

from qutebrowser.browser import browsertab
from qutebrowser.config import config, stylesheet
from qutebrowser.keyinput import modeman
from qutebrowser.utils import usertypes, log, objreg, utils
from qutebrowser.mainwindow.statusbar import (backforward, command, progress,
                                              keystring, percentage, url,
                                              tabindex)
from qutebrowser.mainwindow.statusbar import text as textwidget


@attr.s
class ColorFlags:

    """Flags which change the appearance of the statusbar.

    Attributes:
        prompt: If we're currently in prompt-mode.
        insert: If we're currently in insert mode.
        command: If we're currently in command mode.
        mode: The current caret mode (CaretMode.off/.on/.selection).
        private: Whether this window is in private browsing mode.
        passthrough: If we're currently in passthrough-mode.
    """

    CaretMode = enum.Enum('CaretMode', ['off', 'on', 'selection'])
    prompt = attr.ib(False)
    insert = attr.ib(False)
    command = attr.ib(False)
    caret = attr.ib(CaretMode.off)
    private = attr.ib(False)
    passthrough = attr.ib(False)

    def to_stringlist(self):
        """Get a string list of set flags used in the stylesheet.

        This also combines flags in ways they're used in the sheet.
        """
        strings = []
        if self.prompt:
            strings.append('prompt')
        if self.insert:
            strings.append('insert')
        if self.command:
            strings.append('command')
        if self.private:
            strings.append('private')
        if self.passthrough:
            strings.append('passthrough')

        if self.private and self.command:
            strings.append('private-command')

        if self.caret == self.CaretMode.on:
            strings.append('caret')
        elif self.caret == self.CaretMode.selection:
            strings.append('caret-selection')
        else:
            assert self.caret == self.CaretMode.off

        return strings


def _generate_stylesheet():
    flags = [
        ('private', 'statusbar.private'),
        ('caret', 'statusbar.caret'),
        ('caret-selection', 'statusbar.caret.selection'),
        ('prompt', 'prompts'),
        ('insert', 'statusbar.insert'),
        ('command', 'statusbar.command'),
        ('passthrough', 'statusbar.passthrough'),
        ('private-command', 'statusbar.command.private'),
    ]
    qss = """
        QWidget#StatusBar,
        QWidget#StatusBar QLabel,
        QWidget#StatusBar QLineEdit {
            font: {{ conf.fonts.statusbar }};
            color: {{ conf.colors.statusbar.normal.fg }};
        }

        QWidget#StatusBar {
            background-color: {{ conf.colors.statusbar.normal.bg }};
        }
    """
    for flag, option in flags:
        qss += """
            QWidget#StatusBar[color_flags~="%s"],
            QWidget#StatusBar[color_flags~="%s"] QLabel,
            QWidget#StatusBar[color_flags~="%s"] QLineEdit {
                color: {{ conf.colors.%s }};
            }

            QWidget#StatusBar[color_flags~="%s"] {
                background-color: {{ conf.colors.%s }};
            }
        """ % (flag, flag, flag,  # noqa: S001
               option + '.fg', flag, option + '.bg')
    return qss


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

    STYLESHEET = _generate_stylesheet()

    def __init__(self, *, win_id, private, parent=None):
        super().__init__(parent)
        self.setObjectName(self.__class__.__name__)
        self.setAttribute(Qt.WA_StyledBackground)
        stylesheet.set_register(self)

        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

        self._win_id = win_id
        self._color_flags = ColorFlags()
        self._color_flags.private = private

        self._hbox = QHBoxLayout(self)
        self._set_hbox_padding()
        self._hbox.setSpacing(5)

        self._stack = QStackedLayout()
        self._hbox.addLayout(self._stack)
        self._stack.setContentsMargins(0, 0, 0, 0)

        self.cmd = command.Command(private=private, win_id=win_id)
        self._stack.addWidget(self.cmd)
        objreg.register('status-command', self.cmd, scope='window',
                        window=win_id)

        self.txt = textwidget.Text()
        self._stack.addWidget(self.txt)

        self.cmd.show_cmd.connect(self._show_cmd_widget)
        self.cmd.hide_cmd.connect(self._hide_cmd_widget)
        self._hide_cmd_widget()

        self.url = url.UrlText()
        self.percentage = percentage.Percentage()
        self.backforward = backforward.Backforward()
        self.tabindex = tabindex.TabIndex()
        self.keystring = keystring.KeyString()
        self.prog = progress.Progress(self)
        self._draw_widgets()

        config.instance.changed.connect(self._on_config_changed)
        QTimer.singleShot(0, self.maybe_hide)

    def __repr__(self):
        return utils.get_repr(self)

    @pyqtSlot(str)
    def _on_config_changed(self, option):
        if option == 'statusbar.hide':
            self.maybe_hide()
        elif option == 'statusbar.padding':
            self._set_hbox_padding()
        elif option == 'statusbar.widgets':
            self._draw_widgets()

    def _draw_widgets(self):
        """Draw statusbar widgets."""
        # Start with widgets hidden and show them when needed
        for widget in [self.url, self.percentage,
                       self.backforward, self.tabindex,
                       self.keystring, self.prog]:
            assert isinstance(widget, QWidget)
            widget.hide()
            self._hbox.removeWidget(widget)

        tab = self._current_tab()

        # Read the list and set widgets accordingly
        for segment in config.val.statusbar.widgets:
            if segment == 'url':
                self._hbox.addWidget(self.url)
                self.url.show()
            elif segment == 'scroll':
                self._hbox.addWidget(self.percentage)
                self.percentage.show()
            elif segment == 'scroll_raw':
                self._hbox.addWidget(self.percentage)
                self.percentage.set_raw()
                self.percentage.show()
            elif segment == 'history':
                self._hbox.addWidget(self.backforward)
                self.backforward.enabled = True
                if tab:
                    self.backforward.on_tab_changed(tab)
            elif segment == 'tabs':
                self._hbox.addWidget(self.tabindex)
                self.tabindex.show()
            elif segment == 'keypress':
                self._hbox.addWidget(self.keystring)
                self.keystring.show()
            elif segment == 'progress':
                self._hbox.addWidget(self.prog)
                self.prog.enabled = True
                if tab:
                    self.prog.on_tab_changed(tab)

    @pyqtSlot()
    def maybe_hide(self):
        """Hide the statusbar if it's configured to do so."""
        tab = self._current_tab()
        hide = config.val.statusbar.hide
        if hide or (tab is not None and tab.data.fullscreen):
            self.hide()
        else:
            self.show()

    def _set_hbox_padding(self):
        padding = config.val.statusbar.padding
        self._hbox.setContentsMargins(padding.left, 0, padding.right, 0)

    @pyqtProperty('QStringList')
    def color_flags(self):
        """Getter for self.color_flags, so it can be used as Qt property."""
        return self._color_flags.to_stringlist()

    def _current_tab(self):
        """Get the currently displayed tab."""
        window = objreg.get('tabbed-browser', scope='window',
                            window=self._win_id)
        return window.widget.currentWidget()

    def set_mode_active(self, mode, val):
        """Setter for self.{insert,command,caret}_active.

        Re-set the stylesheet after setting the value, so everything gets
        updated by Qt properly.
        """
        if mode == usertypes.KeyMode.insert:
            log.statusbar.debug("Setting insert flag to {}".format(val))
            self._color_flags.insert = val
        if mode == usertypes.KeyMode.passthrough:
            log.statusbar.debug("Setting passthrough flag to {}".format(val))
            self._color_flags.passthrough = val
        if mode == usertypes.KeyMode.command:
            log.statusbar.debug("Setting command flag to {}".format(val))
            self._color_flags.command = val
        elif mode in [usertypes.KeyMode.prompt, usertypes.KeyMode.yesno]:
            log.statusbar.debug("Setting prompt flag to {}".format(val))
            self._color_flags.prompt = val
        elif mode == usertypes.KeyMode.caret:
            if not val:
                # Turning on is handled in on_current_caret_selection_toggled
                log.statusbar.debug("Setting caret mode off")
                self._color_flags.caret = ColorFlags.CaretMode.off
        stylesheet.set_register(self, update=False)

    def _set_mode_text(self, mode):
        """Set the mode text."""
        if mode == 'passthrough':
            key_instance = config.key_instance
            all_bindings = key_instance.get_reverse_bindings_for('passthrough')
            bindings = all_bindings.get('leave-mode')
            if bindings:
                suffix = ' ({} to leave)'.format(' or '.join(bindings))
            else:
                suffix = ''
        else:
            suffix = ''
        text = "-- {} MODE --{}".format(mode.upper(), suffix)
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
        mode_manager = modeman.instance(self._win_id)
        if mode_manager.parsers[mode].passthrough:
            self._set_mode_text(mode.name)
        if mode in [usertypes.KeyMode.insert,
                    usertypes.KeyMode.command,
                    usertypes.KeyMode.caret,
                    usertypes.KeyMode.prompt,
                    usertypes.KeyMode.yesno,
                    usertypes.KeyMode.passthrough]:
            self.set_mode_active(mode, True)

    @pyqtSlot(usertypes.KeyMode, usertypes.KeyMode)
    def on_mode_left(self, old_mode, new_mode):
        """Clear marked mode."""
        mode_manager = modeman.instance(self._win_id)
        if mode_manager.parsers[old_mode].passthrough:
            if mode_manager.parsers[new_mode].passthrough:
                self._set_mode_text(new_mode.name)
            else:
                self.txt.set_text(self.txt.Text.normal, '')
        if old_mode in [usertypes.KeyMode.insert,
                        usertypes.KeyMode.command,
                        usertypes.KeyMode.caret,
                        usertypes.KeyMode.prompt,
                        usertypes.KeyMode.yesno,
                        usertypes.KeyMode.passthrough]:
            self.set_mode_active(old_mode, False)

    @pyqtSlot(browsertab.AbstractTab)
    def on_tab_changed(self, tab):
        """Notify sub-widgets when the tab has been changed."""
        self.url.on_tab_changed(tab)
        self.prog.on_tab_changed(tab)
        self.percentage.on_tab_changed(tab)
        self.backforward.on_tab_changed(tab)
        self.maybe_hide()
        assert tab.is_private == self._color_flags.private

    @pyqtSlot(browsertab.SelectionState)
    def on_caret_selection_toggled(self, selection_state):
        """Update the statusbar when entering/leaving caret selection mode."""
        log.statusbar.debug("Setting caret selection {}"
                            .format(selection_state))
        if selection_state is browsertab.SelectionState.normal:
            self._set_mode_text("caret selection")
            self._color_flags.caret = ColorFlags.CaretMode.selection
        elif selection_state is browsertab.SelectionState.line:
            self._set_mode_text("caret line selection")
            self._color_flags.caret = ColorFlags.CaretMode.selection
        else:
            self._set_mode_text("caret")
            self._color_flags.caret = ColorFlags.CaretMode.on
        stylesheet.set_register(self, update=False)

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
        padding = config.cache['statusbar.padding']
        width = super().minimumSizeHint().width()
        height = self.fontMetrics().height() + padding.top + padding.bottom
        return QSize(width, height)
