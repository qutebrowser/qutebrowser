# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import functools

from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QSize
from PyQt5.QtWidgets import QSizePolicy

from qutebrowser.keyinput import modeman, modeparsers
from qutebrowser.commands import cmdexc, cmdutils
from qutebrowser.misc import cmdhistory, editor
from qutebrowser.misc import miscwidgets as misc
from qutebrowser.utils import usertypes, log, objreg, message, utils
from qutebrowser.config import config


class Command(misc.MinimalLineEditMixin, misc.CommandLineEdit):

    """The commandline part of the statusbar.

    Attributes:
        _win_id: The window ID this widget is associated with.

    Signals:
        got_cmd: Emitted when a command is triggered by the user.
                 arg: The command string and also potentially the count.
        clear_completion_selection: Emitted before the completion widget is
                                    hidden.
        hide_completion: Emitted when the completion widget should be hidden.
        update_completion: Emitted when the completion should be shown/updated.
        show_cmd: Emitted when command input should be shown.
        hide_cmd: Emitted when command input can be hidden.
    """

    got_cmd = pyqtSignal([str], [str, int])
    clear_completion_selection = pyqtSignal()
    hide_completion = pyqtSignal()
    update_completion = pyqtSignal()
    show_cmd = pyqtSignal()
    hide_cmd = pyqtSignal()

    def __init__(self, *, win_id, private, parent=None):
        misc.CommandLineEdit.__init__(self, parent=parent)
        misc.MinimalLineEditMixin.__init__(self)
        self._win_id = win_id
        if not private:
            command_history = objreg.get('command-history')
            self.history.history = command_history.data
            self.history.changed.connect(command_history.changed)
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Ignored)
        self.cursorPositionChanged.connect(self.update_completion)
        self.textChanged.connect(self.update_completion)
        self.textChanged.connect(self.updateGeometry)
        self.textChanged.connect(self._incremental_search)

        self._command_dispatcher = objreg.get(
            'command-dispatcher', scope='window', window=self._win_id)

    def _handle_search(self):
        """Check if the currently entered text is a search, and if so, run it.

        Return:
            True if a search was executed, False otherwise.
        """
        search_prefixes = {
            '/': self._command_dispatcher.search,
            '?': functools.partial(
                self._command_dispatcher.search, reverse=True)
        }
        if self.prefix() in search_prefixes:
            search_fn = search_prefixes[self.prefix()]
            search_fn(self.text()[1:])
            return True
        return False

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
    @cmdutils.argument('count', count=True)
    def set_cmd_text_command(self, text, count=None, space=False, append=False,
                             run_on_count=False):
        """Preset the statusbar to some text.

        //

        Wrapper for set_cmd_text to check the arguments and allow multiple
        strings which will get joined.

        Args:
            text: The commandline to set.
            count: The count if given.
            space: If given, a space is added to the end.
            append: If given, the text is appended to the current text.
            run_on_count: If given with a count, the command is run with the
                          given count rather than setting the command text.
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
        if run_on_count and count is not None:
            self.got_cmd[str, int].emit(text, count)
        else:
            self.set_cmd_text(text)

    @cmdutils.register(instance='status-command',
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

    @cmdutils.register(instance='status-command',
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

    @cmdutils.register(instance='status-command',
                       modes=[usertypes.KeyMode.command], scope='window')
    def command_accept(self, rapid=False):
        """Execute the command currently in the commandline.

        Args:
            rapid: Run the command without closing or clearing the command bar.
        """
        text = self.text()
        self.history.append(text)

        was_search = self._handle_search()

        if not rapid:
            modeman.leave(self._win_id, usertypes.KeyMode.command,
                          'cmd accept')

        if not was_search:
            self.got_cmd[str].emit(text[1:])

    @cmdutils.register(instance='status-command', scope='window')
    def edit_command(self, run=False):
        """Open an editor to modify the current command.

        Args:
            run: Run the command if the editor exits successfully.
        """
        ed = editor.ExternalEditor(parent=self)

        def callback(text):
            """Set the commandline to the edited text."""
            if not text or text[0] not in modeparsers.STARTCHARS:
                message.error('command must start with one of {}'
                              .format(modeparsers.STARTCHARS))
                return
            self.set_cmd_text(text)
            if run:
                self.command_accept()

        ed.file_updated.connect(callback)
        ed.edit(self.text())

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
            raise utils.Unreachable("setText got called with invalid text "
                                    "'{}'!".format(text))
        super().setText(text)

    def keyPressEvent(self, e):
        """Override keyPressEvent to ignore Return key presses.

        If this widget is focused, we are in passthrough key mode, and
        Enter/Shift+Enter/etc. will cause QLineEdit to think it's finished
        without command_accept to be called.
        """
        text = self.text()
        if text in modeparsers.STARTCHARS and e.key() == Qt.Key_Backspace:
            e.accept()
            modeman.leave(self._win_id, usertypes.KeyMode.command,
                          'prefix deleted')
            return
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

    @pyqtSlot()
    def _incremental_search(self):
        if not config.val.search.incremental:
            return

        self._handle_search()
