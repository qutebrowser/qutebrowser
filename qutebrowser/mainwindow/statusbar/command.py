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

"""The commandline in the statusbar."""

from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QSize
from PyQt5.QtWidgets import QSizePolicy

from qutebrowser.keyinput import modeman, modeparsers
from qutebrowser.commands import cmdexc, cmdutils
from qutebrowser.misc import cmdhistory
from qutebrowser.misc import miscwidgets as misc
from qutebrowser.utils import usertypes, log, objreg


class Command(misc.MinimalLineEditMixin, misc.CommandLineEdit):

    """The commandline part of the statusbar.

    Attributes:
        _win_id: The window ID this widget is associated with.

    Signals:
        got_cmd: Emitted when a command is triggered by the user.
                 arg: The command string.
        clear_completion_selection: Emitted before the completion widget is
                                    hidden.
        hide_completion: Emitted when the completion widget should be hidden.
        update_completion: Emitted when the completion should be shown/updated.
        show_cmd: Emitted when command input should be shown.
        hide_cmd: Emitted when command input can be hidden.
    """

    got_cmd = pyqtSignal(str)
    clear_completion_selection = pyqtSignal()
    hide_completion = pyqtSignal()
    update_completion = pyqtSignal()
    show_cmd = pyqtSignal()
    hide_cmd = pyqtSignal()

    def __init__(self, win_id, parent=None):
        misc.CommandLineEdit.__init__(self, parent)
        misc.MinimalLineEditMixin.__init__(self)
        self._win_id = win_id
        command_history = objreg.get('command-history')
        self.history.handle_private_mode = True
        self.history.history = command_history.data
        self.history.changed.connect(command_history.changed)
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Ignored)
        self.cursorPositionChanged.connect(self.update_completion)
        self.textChanged.connect(self.update_completion)
        self.textChanged.connect(self.updateGeometry)

    def prefix(self):
        """Get the currently entered command prefix."""
        text = self.text()
        if not text:
            return ''
        elif text[0] in modeparsers.STARTCHARS:
            return text[0]
        else:
            return ''

    def set_cmd_text(self, text):
        """Preset the statusbar to some text.

        Args:
            text: The text to set as string.
        """
        self.setText(text)
        log.modes.debug("Setting command text, focusing {!r}".format(self))
        modeman.enter(self._win_id, usertypes.KeyMode.command, 'cmd focus')
        self.setFocus()
        self.show_cmd.emit()

    @cmdutils.register(instance='status-command', name='set-cmd-text',
                       scope='window', maxsplit=0)
    def set_cmd_text_command(self, text, space=False, append=False):
        """Preset the statusbar to some text.

        //

        Wrapper for set_cmd_text to check the arguments and allow multiple
        strings which will get joined.

        Args:
            text: The commandline to set.
            space: If given, a space is added to the end.
            append: If given, the text is appended to the current text.
        """
        if space:
            text += ' '
        if append:
            if not self.text():
                raise cmdexc.CommandError("No current text!")
            text = self.text() + text

        if not text or text[0] not in modeparsers.STARTCHARS:
            raise cmdexc.CommandError(
                "Invalid command text '{}'.".format(text))
        self.set_cmd_text(text)

    @cmdutils.register(instance='status-command', hide=True,
                       modes=[usertypes.KeyMode.command], scope='window')
    def command_history_prev(self):
        """Go back in the commandline history."""
        try:
            if not self.history.is_browsing():
                item = self.history.start(self.text().strip())
            else:
                item = self.history.previtem()
        except (cmdhistory.HistoryEmptyError,
                cmdhistory.HistoryEndReachedError):
            return
        if item:
            self.set_cmd_text(item)

    @cmdutils.register(instance='status-command', hide=True,
                       modes=[usertypes.KeyMode.command], scope='window')
    def command_history_next(self):
        """Go forward in the commandline history."""
        if not self.history.is_browsing():
            return
        try:
            item = self.history.nextitem()
        except cmdhistory.HistoryEndReachedError:
            return
        if item:
            self.set_cmd_text(item)

    @cmdutils.register(instance='status-command', hide=True,
                       modes=[usertypes.KeyMode.command], scope='window')
    def command_accept(self):
        """Execute the command currently in the commandline."""
        prefixes = {
            ':': '',
            '/': 'search -- ',
            '?': 'search -r -- ',
        }
        text = self.text()
        self.history.append(text)
        modeman.leave(self._win_id, usertypes.KeyMode.command, 'cmd accept')
        self.got_cmd.emit(prefixes[text[0]] + text[1:])

    @pyqtSlot(usertypes.KeyMode)
    def on_mode_left(self, mode):
        """Clear up when command mode was left.

        - Clear the statusbar text if it's explicitly unfocused.
        - Clear completion selection
        - Hide completion

        Args:
            mode: The mode which was left.
        """
        if mode == usertypes.KeyMode.command:
            self.setText('')
            self.history.stop()
            self.hide_cmd.emit()
            self.clear_completion_selection.emit()
            self.hide_completion.emit()

    def setText(self, text):
        """Extend setText to set prefix and make sure the prompt is ok."""
        if not text:
            pass
        elif text[0] in modeparsers.STARTCHARS:
            super().set_prompt(text[0])
        else:
            raise AssertionError("setText got called with invalid text "
                                 "'{}'!".format(text))
        super().setText(text)

    def keyPressEvent(self, e):
        """Override keyPressEvent to ignore Return key presses.

        If this widget is focused, we are in passthrough key mode, and
        Enter/Shift+Enter/etc. will cause QLineEdit to think it's finished
        without command_accept to be called.
        """
        if e.key() == Qt.Key_Return:
            e.ignore()
            return
        else:
            super().keyPressEvent(e)

    def sizeHint(self):
        """Dynamically calculate the needed size."""
        height = super().sizeHint().height()
        text = self.text()
        if not text:
            text = 'x'
        width = self.fontMetrics().width(text)
        return QSize(width, height)
