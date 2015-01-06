# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import re

from PyQt5.QtCore import pyqtSlot, pyqtSignal, QObject, QUrl
from PyQt5.QtWebKitWidgets import QWebPage

from qutebrowser.config import config, configexc
from qutebrowser.commands import cmdexc, cmdutils
from qutebrowser.utils import message, log, utils, objreg
from qutebrowser.misc import split


def replace_variables(win_id, arglist):
    """Utility function to replace variables like {url} in a list of args."""
    args = []
    tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                window=win_id)
    for arg in arglist:
        if arg == '{url}':
            # Note we have to do this in here as the user gets an error message
            # by current_url if no URL is open yet.
            url = tabbed_browser.current_url().toString(QUrl.FullyEncoded |
                                                        QUrl.RemovePassword)
            args.append(url)
        else:
            args.append(arg)
    return args


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
        return utils.get_repr(self, text=self._text, flags=self._flags)

    def _search(self, text, rev=False):
        """Search for a text on the current page.

        Args:
            text: The text to search for.
            rev: Search direction, True if reverse, else False.
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

    @cmdutils.register(instance='search-runner', hide=True, scope='window')
    def search_next(self, count: {'special': 'count'}=1):
        """Continue the search to the ([count]th) next term.

        Args:
            count: How many elements to ignore.
        """
        if self._text is not None:
            for _ in range(count):
                self.do_search.emit(self._text, self._flags)

    @cmdutils.register(instance='search-runner', hide=True, scope='window')
    def search_prev(self, count: {'special': 'count'}=1):
        """Continue the search to the ([count]th) previous term.

        Args:
            count: How many elements to ignore.
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


class CommandRunner(QObject):

    """Parse and run qutebrowser commandline commands.

    Attributes:
        _cmd: The command which was parsed.
        _args: The arguments which were parsed.
        _win_id: The window this CommandRunner is associated with.
    """

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        self._cmd = None
        self._args = []
        self._win_id = win_id

    def _get_alias(self, text):
        """Get an alias from the config.

        Args:
            text: The text to parse.

        Return:
            None if no alias was found.
            The new command string if an alias was found.
        """
        parts = text.strip().split(maxsplit=1)
        try:
            alias = config.get('aliases', parts[0])
        except (configexc.NoOptionError, configexc.NoSectionError):
            return None
        try:
            new_cmd = '{} {}'.format(alias, parts[1])
        except IndexError:
            new_cmd = alias
        if text.endswith(' '):
            new_cmd += ' '
        return new_cmd

    def parse(self, text, aliases=True, fallback=False, keep=False):
        """Split the commandline text into command and arguments.

        Args:
            text: Text to parse.
            aliases: Whether to handle aliases.
            fallback: Whether to do a fallback splitting when the command was
                      unknown.
            keep: Whether to keep special chars and whitespace

        Return:
            A split string commandline, e.g ['open', 'www.google.com']
        """
        cmdstr, sep, argstr = text.partition(' ')
        if not cmdstr and not fallback:
            raise cmdexc.NoSuchCommandError("No command given")
        if aliases:
            new_cmd = self._get_alias(text)
            if new_cmd is not None:
                log.commands.debug("Re-parsing with '{}'.".format(new_cmd))
                return self.parse(new_cmd, aliases=False, fallback=fallback,
                                  keep=keep)
        try:
            self._cmd = cmdutils.cmd_dict[cmdstr]
        except KeyError:
            if fallback and keep:
                cmdstr, sep, argstr = text.partition(' ')
                return [cmdstr, sep] + argstr.split()
            elif fallback:
                return text.split()
            else:
                raise cmdexc.NoSuchCommandError(
                    '{}: no such command'.format(cmdstr))
        self._split_args(argstr, keep)
        retargs = self._args[:]
        if keep and retargs:
            return [cmdstr, sep + retargs[0]] + retargs[1:]
        elif keep:
            return [cmdstr, sep]
        else:
            return [cmdstr] + retargs

    def _split_args(self, argstr, keep):
        """Split the arguments from an arg string.

        Args:
            argstr: An argument string.
            keep: Whether to keep special chars and whitespace

        Return:
            A list containing the splitted strings.
        """
        if not argstr:
            self._args = []
        elif self._cmd.maxsplit is None:
            self._args = split.split(argstr, keep=keep)
        else:
            # If split=False, we still want to split the flags, but not
            # everything after that.
            # We first split the arg string and check the index of the first
            # non-flag args, then we re-split again properly.
            # example:
            #
            # input: "--foo -v bar baz"
            # first split: ['--foo', '-v', 'bar', 'baz']
            #                0        1     2      3
            # second split: ['--foo', '-v', 'bar baz']
            # (maxsplit=2)
            split_args = split.simple_split(argstr, keep=keep)
            flag_arg_count = 0
            for i, arg in enumerate(split_args):
                arg = arg.strip()
                if arg.startswith('-'):
                    if arg.lstrip('-') in self._cmd.flags_with_args:
                        flag_arg_count += 1
                else:
                    self._args = []
                    maxsplit = i + self._cmd.maxsplit + flag_arg_count
                    args = split.simple_split(argstr, keep=keep,
                                              maxsplit=maxsplit)
                    for s in args:
                        # remove quotes and replace \" by "
                        if s == '""' or s == "''":
                            s = ''
                        else:
                            s = re.sub(r"""(^|[^\\])["']""", r'\1', s)
                            s = re.sub(r"""\\(["'])""", r'\1', s)
                        self._args.append(s)
                    break
            else:
                # If there are only flags, we got it right on the first try
                # already.
                self._args = split_args

    def run(self, text, count=None):
        """Parse a command from a line of text and run it.

        Args:
            text: The text to parse.
            count: The count to pass to the command.
        """
        if ';;' in text:
            for sub in text.split(';;'):
                self.run(sub, count)
            return
        self.parse(text)
        args = replace_variables(self._win_id, self._args)
        if count is not None:
            self._cmd.run(self._win_id, args, count=count)
        else:
            self._cmd.run(self._win_id, args)

    @pyqtSlot(str, int)
    def run_safely(self, text, count=None):
        """Run a command and display exceptions in the statusbar."""
        try:
            self.run(text, count)
        except (cmdexc.CommandMetaError, cmdexc.CommandError) as e:
            message.error(self._win_id, e, immediately=True)

    @pyqtSlot(str, int)
    def run_safely_init(self, text, count=None):
        """Run a command and display exceptions in the statusbar.

        Contrary to run_safely, error messages are queued so this is more
        suitable to use while initializing."""
        try:
            self.run(text, count)
        except (cmdexc.CommandMetaError, cmdexc.CommandError) as e:
            message.error(self._win_id, e)
