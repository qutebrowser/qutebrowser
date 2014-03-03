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
import logging
import functools

from PyQt5.QtCore import pyqtSlot, pyqtSignal, QObject
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebKitWidgets import QWebPage

import qutebrowser.config.config as config
from qutebrowser.commands.command import Command
from qutebrowser.commands.exceptions import (ArgumentCountError,
                                             NoSuchCommandError)

# A mapping from command-strings to command objects.
cmd_dict = {}


class register:
    """Decorator to register a new command handler.

    This could also be a function, but as a class (with a "wrong" name) it's
    much cleaner to implement.

    """

    def __init__(self, instance=None, name=None, nargs=None, split_args=True,
                 hide=False):
        self.name = name
        self.split_args = split_args
        self.hide = hide
        self.nargs = nargs
        self.instance = instance

    def __call__(self, func):
        global cmd_dict
        names = []
        name = func.__name__.lower() if self.name is None else self.name
        if isinstance(name, str):
            mainname = name
            names.append(name)
        else:
            mainname = name[0]
            names += name
        count, nargs = self._get_nargs_count(func)
        desc = func.__doc__.splitlines()[0].strip().rstrip('.')
        cmd = Command(name=mainname, split_args=self.split_args,
                      hide=self.hide, nargs=nargs, count=count, desc=desc,
                      instance=self.instance, handler=func)
        for name in names:
            cmd_dict[name] = cmd
        return func


    def _get_nargs_count(self, func):
        """Get the number of command-arguments and count-support for a func.

        Args:
            func: The function to get the argcount for.

        Return:
            A (count, (minargs, maxargs)) tuple, with maxargs=None if there are
            infinite args. count is True if the function supports count, else
            False.

            Mapping from old nargs format to (minargs, maxargs):
                ?   (0, 1)
                N   (N, N)
                +   (1, None)
                *   (0, None)

        """
        # We could use inspect.signature maybe, but that's python >= 3.3 only.
        spec = inspect.getfullargspec(func)
        count = 'count' in spec.args
        # we assume count always has a default (and it should!)
        if self.nargs is not None:
            # If nargs is overriden, use that.
            if isinstance(self.nargs, int):
                # Single int
                minargs, maxargs = self.nargs, self.nargs
            else:
                # Tuple (min, max)
                minargs, maxargs = self.nargs
        else:
            defaultcount = (len(spec.defaults) if spec.defaults is not None
                                               else 0)
            argcount = len(spec.args)
            if 'self' in spec.args:
                argcount -= 1
            minargs = argcount - defaultcount
            if spec.varargs is not None:
                maxargs = None
            else:
                maxargs = len(spec.args) - int(count)  # -1 if count is defined
        return (count, (minargs, maxargs))


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

    def _search(self, text, rev=False):
        """Search for a text on the current page.

        Args:
            text: The text to search for.
            rev: Search direction, True if reverse, else False.

        Emit:
            do_search: If a search should be started.

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

    @pyqtSlot(str)
    def search(self, text):
        """Search for a text on a website.

        Args:
            text: The text to search for.

        """
        self._search(text)

    @pyqtSlot(str)
    def search_rev(self, text):
        """Search for a text on a website in reverse direction.

        Args:
            text: The text to search for.

        """
        self._search(text, rev=True)

    @register(instance='searchparser', hide=True)
    def nextsearch(self, count=1):
        """Continue the search to the ([count]th) next term.

        Args:
            count: How many elements to ignore.

        Emit:
            do_search: If a search should be started.

        """
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

    def _parse(self, text, aliases=True):
        """Split the commandline text into command and arguments.

        Args:
            text: Text to parse.
            aliases: Whether to handle aliases.

        Raise:
            NoSuchCommandError if a command wasn't found.

        """
        parts = text.strip().split(maxsplit=1)
        if not parts:
            raise NoSuchCommandError("No command given")
        cmdstr = parts[0]
        if aliases:
            try:
                alias = config.config.get('aliases', cmdstr)
            except config.NoOptionError:
                pass
            else:
                return self._parse(alias, aliases=False)
        try:
            cmd = cmd_dict[cmdstr]
        except KeyError:
            raise NoSuchCommandError("Command {} not found.".format(cmdstr))

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
        """Run a command with an optional count.

        Args:
            count: Count to pass to the command.

        """
        if count is not None:
            self._cmd.run(self._args, count=count)
        else:
            self._cmd.run(self._args)

    @pyqtSlot(str, int, bool)
    def run(self, text, count=None, ignore_exc=True):
        """Parse a command from a line of text.

        If ignore_exc is True, ignore exceptions and return True/False.

        Args:
            text: The text to parse.
            count: The count to pass to the command.
            ignore_exc: Ignore exceptions and return False instead.

        Raise:
            NoSuchCommandError: if a command wasn't found.
            ArgumentCountError: if a command was called with the wrong count of
            arguments.

        Return:
            True if command was called (handler returnstatus is ignored!).
            False if command wasn't called (there was an ignored exception).

        Emit:
            error: If there was an error parsing a command.

        """
        if ';;' in text:
            retvals = []
            for sub in text.split(';;'):
                retvals.append(self.run(sub, count, ignore_exc))
            return all(retvals)
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
        return True
