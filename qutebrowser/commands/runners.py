# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

"""Module containing command managers (SearchRunner and CommandRunner)."""

from PyQt5.QtCore import pyqtSlot, pyqtSignal, QObject
from PyQt5.QtWebKitWidgets import QWebPage

import qutebrowser.config.config as config
import qutebrowser.commands.utils as cmdutils
import qutebrowser.utils.message as message
from qutebrowser.commands.exceptions import (NoSuchCommandError,
                                             CommandMetaError, CommandError)
from qutebrowser.utils.misc import safe_shlex_split
from qutebrowser.utils.log import commands as logger


class SearchRunner(QObject):

    """Run searches on webpages.

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
        super().__init__(parent)
        self._text = None
        self._flags = 0

    def __repr__(self):
        return '<{} text={}>'.format(self.__class__.__name__, self._text)

    def _search(self, text, rev=False):
        """Search for a text on the current page.

        Args:
            text: The text to search for.
            rev: Search direction, True if reverse, else False.

        Emit:
            do_search: If a search should be started.
        """
        if self._text is not None and self._text != text:
            # We first clear the marked text, then the highlights
            self.do_search.emit('', 0)
            self.do_search.emit('', QWebPage.HighlightAllOccurrences)
        self._text = text
        self._flags = 0
        ignore_case = config.get('general', 'ignore-case')
        if ignore_case == 'smart':
            if not text.islower():
                self._flags |= QWebPage.FindCaseSensitively
        elif not ignore_case:
            self._flags |= QWebPage.FindCaseSensitively
        if config.get('general', 'wrap-search'):
            self._flags |= QWebPage.FindWrapsAroundDocument
        if rev:
            self._flags |= QWebPage.FindBackward
        # We actually search *twice* - once to highlight everything, then again
        # to get a mark so we can navigate.
        self.do_search.emit(self._text, self._flags)
        self.do_search.emit(self._text, self._flags |
                            QWebPage.HighlightAllOccurrences)

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

    @cmdutils.register(instance='searchrunner', hide=True)
    def search_next(self, count=1):
        """Continue the search to the ([count]th) next term.

        Args:
            count: How many elements to ignore.

        Emit:
            do_search: If a search should be started.
        """
        if self._text is not None:
            for _ in range(count):
                self.do_search.emit(self._text, self._flags)

    @cmdutils.register(instance='searchrunner', hide=True)
    def search_prev(self, count=1):
        """Continue the search to the ([count]th) previous term.

        Args:
            count: How many elements to ignore.

        Emit:
            do_search: If a search should be started.
        """
        if self._text is None:
            return
        # The int() here serves as a QFlags constructor to create a copy of the
        # QFlags instance rather as a reference. I don't know why it works this
        # way, but it does.
        flags = int(self._flags)
        if flags & QWebPage.FindBackward:
            flags &= ~QWebPage.FindBackward
        else:
            flags |= QWebPage.FindBackward
        for _ in range(count):
            self.do_search.emit(self._text, flags)


class CommandRunner:

    """Parse and run qutebrowser commandline commands.

    Attributes:
        _cmd: The command which was parsed.
        _args: The arguments which were parsed.
    """

    def __init__(self):
        self._cmd = None
        self._args = []

    def _get_alias(self, text, alias_no_args):
        """Get an alias from the config.

        Args:
            text: The text to parse.
            alias_no_args: Whether to apply an alias if there are no arguments.

        Return:
            None if no alias was found.
            The new command string if an alias was found.
        """
        parts = text.strip().split(maxsplit=1)
        try:
            alias = config.get('aliases', parts[0])
        except (config.NoOptionError, config.NoSectionError):
            return None
        try:
            new_cmd = '{} {}'.format(alias, parts[1])
        except IndexError:
            if alias_no_args:
                new_cmd = alias
            else:
                new_cmd = parts[0]
        if text.endswith(' '):
            new_cmd += ' '
        return new_cmd

    def parse(self, text, aliases=True, fallback=False, alias_no_args=True):
        """Split the commandline text into command and arguments.

        Args:
            text: Text to parse.
            aliases: Whether to handle aliases.
            fallback: Whether to do a fallback splitting when the command was
                      unknown.
            alias_no_args: Whether to apply an alias if there are no arguments.

        Raise:
            NoSuchCommandError if a command wasn't found.

        Return:
            A split string commandline, e.g ['open', 'www.google.com']
        """
        parts = text.strip().split(maxsplit=1)
        if not parts:
            raise NoSuchCommandError("No command given")
        cmdstr = parts[0]
        if aliases:
            new_cmd = self._get_alias(text, alias_no_args)
            if new_cmd is not None:
                logger.debug("Re-parsing with '{}'.".format(new_cmd))
                return self.parse(new_cmd, aliases=False)
        try:
            cmd = cmdutils.cmd_dict[cmdstr]
        except KeyError:
            if fallback:
                parts = text.split(' ')
                if text.endswith(' '):
                    parts.append('')
                return parts
            else:
                raise NoSuchCommandError('{}: no such command'.format(cmdstr))
        if len(parts) == 1:
            args = []
        elif cmd.split:
            args = safe_shlex_split(parts[1])
        else:
            args = parts[1].split(maxsplit=cmd.nargs[0] - 1)
        self._cmd = cmd
        self._args = args
        retargs = args[:]
        if text.endswith(' '):
            retargs.append('')
        return [cmdstr] + retargs

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

    def run(self, text, count=None):
        """Parse a command from a line of text.

        Args:
            text: The text to parse.
            count: The count to pass to the command.
        """
        if ';;' in text:
            for sub in text.split(';;'):
                self.run(sub, count)
            return
        self.parse(text)
        self._check()
        self._run(count=count)

    @pyqtSlot(str, int)
    def run_safely(self, text, count=None):
        """Run a command and display exceptions in the statusbar."""
        try:
            self.run(text, count)
        except (CommandMetaError, CommandError) as e:
            message.error(e, immediately=True)

    @pyqtSlot(str, int)
    def run_safely_init(self, text, count=None):
        """Run a command and display exceptions in the statusbar.

        Contrary to run_safely, error messages are queued so this is more
        suitable to use while initializing."""
        try:
            self.run(text, count)
        except (CommandMetaError, CommandError) as e:
            message.error(e)
