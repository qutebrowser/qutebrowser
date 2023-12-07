# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The main statusbar widget."""

import enum
import dataclasses

from qutebrowser.qt.core import pyqtSignal, pyqtProperty, pyqtSlot, Qt, QSize, QTimer
from qutebrowser.qt.widgets import QWidget, QHBoxLayout, QStackedLayout, QSizePolicy

from qutebrowser.browser import browsertab
from qutebrowser.config import config, stylesheet
from qutebrowser.keyinput import modeman
from qutebrowser.utils import usertypes, log, objreg, utils
from qutebrowser.mainwindow.statusbar import (backforward, command, progress,
                                              keystring, percentage, url,
                                              tabindex, textbase, clock, searchmatch)


@dataclasses.dataclass
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

    class CaretMode(enum.Enum):

        """The current caret "sub-mode" we're in."""

        off = enum.auto()
        on = enum.auto()
        selection = enum.auto()

    prompt: bool = False
    insert: bool = False
    command: bool = False
    caret: CaretMode = CaretMode.off
    private: bool = False
    passthrough: bool = False

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
        search_match: The SearchMatch widget in the statusbar.
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
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        stylesheet.set_register(self)

        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

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

        self.txt = textbase.TextBase()
        self._stack.addWidget(self.txt)

        self.cmd.show_cmd.connect(self._show_cmd_widget)
        self.cmd.hide_cmd.connect(self._hide_cmd_widget)
        self._hide_cmd_widget()

        self.search_match = searchmatch.SearchMatch()

        self.url = url.UrlText()
        self.percentage = percentage.Percentage()
        self.backforward = backforward.Backforward()
        self.tabindex = tabindex.TabIndex()
        self.keystring = keystring.KeyString()
        self.prog = progress.Progress(self)
        self.clock = clock.Clock()
        self._text_widgets = []
        self._draw_widgets()

        config.instance.changed.connect(self._on_config_changed)
        QTimer.singleShot(0, self.maybe_hide)

    def __repr__(self):
        return utils.get_repr(self)

    def _get_widget_from_config(self, key):
        """Return the widget that fits with config string key."""
        if key == 'url':
            return self.url
        elif key == 'scroll':
            return self.percentage
        elif key == 'scroll_raw':
            return self.percentage
        elif key == 'history':
            return self.backforward
        elif key == 'tabs':
            return self.tabindex
        elif key == 'keypress':
            return self.keystring
        elif key == 'progress':
            return self.prog
        elif key == 'search_match':
            return self.search_match
        elif key.startswith('text:'):
            new_text_widget = textbase.TextBase()
            self._text_widgets.append(new_text_widget)
            return new_text_widget
        elif key.startswith('clock:') or key == 'clock':
            return self.clock
        else:
            raise utils.Unreachable(key)

    @pyqtSlot(str)
    def _on_config_changed(self, option):
        if option == 'statusbar.show':
            self.maybe_hide()
        elif option == 'statusbar.padding':
            self._set_hbox_padding()
        elif option == 'statusbar.widgets':
            self._draw_widgets()

    def _draw_widgets(self):
        """Draw statusbar widgets."""
        self._clear_widgets()

        tab = self._current_tab()

        # Read the list and set widgets accordingly
        for segment in config.val.statusbar.widgets:
            widget = self._get_widget_from_config(segment)
            self._hbox.addWidget(widget)

            if segment == 'scroll_raw':
                widget.set_raw()
            elif segment in ('history', 'progress'):
                widget.enabled = True
                if tab:
                    widget.on_tab_changed(tab)

                # Do not call .show() for these widgets. They are not always shown, and
                # dynamically show/hide themselves in their on_tab_changed() methods.
                continue
            elif segment.startswith('text:'):
                widget.setText(segment.split(':', maxsplit=1)[1])
            elif segment.startswith('clock:') or segment == 'clock':
                split_segment = segment.split(':', maxsplit=1)
                if len(split_segment) == 2 and split_segment[1]:
                    widget.format = split_segment[1]
                else:
                    widget.format = '%X'

            widget.show()

    def _clear_widgets(self):
        """Clear widgets before redrawing them."""
        # Start with widgets hidden and show them when needed
        for widget in [self.url, self.percentage,
                       self.backforward, self.tabindex,
                       self.keystring, self.prog, self.clock, *self._text_widgets]:
            assert isinstance(widget, QWidget)
            if widget in [self.prog, self.backforward]:
                widget.enabled = False  # type: ignore[attr-defined]
            widget.hide()
            self._hbox.removeWidget(widget)
        self._text_widgets.clear()

    @pyqtSlot()
    def maybe_hide(self):
        """Hide the statusbar if it's configured to do so."""
        strategy = config.val.statusbar.show
        tab = self._current_tab()
        if tab is not None and tab.data.fullscreen:
            self.hide()
        elif strategy == 'never':
            self.hide()
        elif strategy == 'in-mode':
            try:
                mode_manager = modeman.instance(self._win_id)
            except modeman.UnavailableError:
                self.hide()
            else:
                if mode_manager.mode == usertypes.KeyMode.normal:
                    self.hide()
                else:
                    self.show()
        elif strategy == 'always':
            self.show()
        else:
            raise utils.Unreachable

    def _set_hbox_padding(self):
        padding = config.val.statusbar.padding
        self._hbox.setContentsMargins(padding.left, 0, padding.right, 0)

    @pyqtProperty('QStringList')  # type: ignore[type-var]
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
            bindings = all_bindings.get('mode-leave')
            if bindings:
                suffix = ' ({} to leave)'.format(' or '.join(bindings))
            else:
                suffix = ''
        else:
            suffix = ''
        text = "-- {} MODE --{}".format(mode.upper(), suffix)
        self.txt.setText(text)

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
    def set_text(self, text):
        """Set a normal (persistent) text in the status bar."""
        log.message.debug(text)
        self.txt.setText(text)

    @pyqtSlot(usertypes.KeyMode)
    def on_mode_entered(self, mode):
        """Mark certain modes in the commandline."""
        if config.val.statusbar.show == 'in-mode' and mode != usertypes.KeyMode.command:
            # Showing in command mode is handled via _show_cmd_widget()
            self.show()

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
        if config.val.statusbar.show == 'in-mode' and old_mode != usertypes.KeyMode.command:
            # Hiding in command mode is handled via _hide_cmd_widget()
            self.hide()

        mode_manager = modeman.instance(self._win_id)
        if mode_manager.parsers[old_mode].passthrough:
            if mode_manager.parsers[new_mode].passthrough:
                self._set_mode_text(new_mode.name)
            else:
                self.txt.setText('')
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
