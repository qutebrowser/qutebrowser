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

"""Contains various command utils, and the CommandParser."""

import shlex
import inspect

from PyQt5.QtCore import pyqtSlot, pyqtSignal, QObject
from PyQt5.QtWebKitWidgets import QWebPage

import qutebrowser.commands.commands
import qutebrowser.utils.config as config
from qutebrowser.commands.exceptions import (ArgumentCountError,
                                             NoSuchCommandError)

# A mapping from command-strings to command objects.
cmd_dict = {}


def register_all():
    """Register and initialize all commands."""
    for (name, cls) in inspect.getmembers(  # pylint: disable=unused-variable
            qutebrowser.commands.commands,
            (lambda o: inspect.isclass(o) and o.__module__ ==
             'qutebrowser.commands.commands')):
        obj = cls()
        if isinstance(obj.name, str):
            names = [obj.name]
        else:
            names = obj.name
        for n in names:
            cmd_dict[n] = obj


class SearchParser(QObject):

    """Parse qutebrowser searches.

    Attributes:
        _text: The text from the last search.
        _flags: The flags from the last search.

    Signals:
        do_search: Emitted when a search should be started.
                   arg 1: Search string.
                   arg 2: Flags to use.

    """

    do_search = pyqtSignal(str, 'QWebPage::FindFlags')

    def __init__(self, parent=None):
        self._text = None
        self._flags = 0
        super().__init__(parent)

    @pyqtSlot(str)
    def search(self, text):
        """Search for a text on a website.

        text -- The text to search for.

        """
        self._search(text)

    @pyqtSlot(str)
    def search_rev(self, text):
        """Search for a text on a website in reverse direction.

        text -- The text to search for.

        """
        self._search(text, rev=True)

    def _search(self, text, rev=False):
        """Search for a text on the current page.

        text -- The text to search for.
        rev -- Search direction.

        """
        if self._text is not None and self._text != text:
            self.do_search.emit('', 0)
        self._text = text
        self._flags = 0
        if config.config.getboolean('general', 'ignorecase', fallback=True):
            self._flags |= QWebPage.FindCaseSensitively
        if config.config.getboolean('general', 'wrapsearch', fallback=True):
            self._flags |= QWebPage.FindWrapsAroundDocument
        if rev:
            self._flags |= QWebPage.FindBackward
        self.do_search.emit(self._text, self._flags)

    def nextsearch(self, count=1):
        """Continue the search to the ([count]th) next term."""
        if self._text is not None:
            for i in range(count):  # pylint: disable=unused-variable
                self.do_search.emit(self._text, self._flags)


class CommandParser(QObject):

    """Parse qutebrowser commandline commands.

    Attributes:
        _cmd: The command which was parsed.
        _args: The arguments which were parsed.

    Signals:
        error: Emitted if there was an error.
               arg: The error message.

    """

    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cmd = None
        self._args = []

    def _parse(self, text):
        """Split the commandline text into command and arguments.

        Raise NoSuchCommandError if a command wasn't found.

        """
        parts = text.strip().split(maxsplit=1)
        if not parts:
            raise NoSuchCommandError
        cmdstr = parts[0]
        try:
            cmd = cmd_dict[cmdstr]
        except KeyError:
            raise NoSuchCommandError(cmdstr)

        if len(parts) == 1:
            args = []
        elif cmd.split_args:
            args = shlex.split(parts[1])
        else:
            args = [parts[1]]
        self._cmd = cmd
        self._args = args

    def _check(self):
        """Check if the argument count for the command is correct."""
        self._cmd.check(self._args)

    def _run(self, count=None):
        """Run a command with an optional count."""
        if count is not None:
            self._cmd.run(self._args, count=count)
        else:
            self._cmd.run(self._args)

    @pyqtSlot(str, int, bool)
    def run(self, text, count=None, ignore_exc=True):
        """Parse a command from a line of text.

        If ignore_exc is True, ignore exceptions and return True/False.

        Raise NoSuchCommandError if a command wasn't found, and
        ArgumentCountError if a command was called with the wrong count of
        arguments.

        """
        if ';;' in text:
            for sub in text.split(';;'):
                self.run(sub, count, ignore_exc)
            return
        try:
            self._parse(text)
            self._check()
        except ArgumentCountError:
            if ignore_exc:
                self.error.emit("{}: invalid argument count".format(
                    self._cmd.mainname))
                return False
            else:
                raise
        except NoSuchCommandError as e:
            if ignore_exc:
                self.error.emit("{}: no such command".format(e))
                return False
            else:
                raise
        self._run(count=count)
