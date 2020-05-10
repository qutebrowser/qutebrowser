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

"""Module containing command managers (SearchRunner and CommandRunner)."""

import traceback
import re
import typing
import contextlib

import attr
from PyQt5.QtCore import pyqtSlot, QUrl, QObject

from qutebrowser.api import cmdutils
from qutebrowser.config import config
from qutebrowser.commands import cmdexc
from qutebrowser.utils import message, objreg, qtutils, usertypes, utils
from qutebrowser.misc import split, objects
from qutebrowser.keyinput import macros, modeman

if typing.TYPE_CHECKING:
    from qutebrowser.mainwindow import tabbedbrowser
_ReplacementFunction = typing.Callable[['tabbedbrowser.TabbedBrowser'], str]


last_command = {}


@attr.s
class ParseResult:

    """The result of parsing a commandline."""

    cmd = attr.ib()
    args = attr.ib()
    cmdline = attr.ib()


def _url(tabbed_browser):
    """Convenience method to get the current url."""
    try:
        return tabbed_browser.current_url()
    except qtutils.QtValueError as e:
        msg = "Current URL is invalid"
        if e.reason:
            msg += " ({})".format(e.reason)
        msg += "!"
        raise cmdutils.CommandError(msg)


def _init_variable_replacements() -> typing.Mapping[str, _ReplacementFunction]:
    """Return a dict from variable replacements to fns processing them."""
    replacements = {
        'url': lambda tb: _url(tb).toString(
            QUrl.FullyEncoded | QUrl.RemovePassword),
        'url:pretty': lambda tb: _url(tb).toString(
            QUrl.DecodeReserved | QUrl.RemovePassword),
        'url:domain': lambda tb: "{}://{}{}".format(
            _url(tb).scheme(), _url(tb).host(),
            ":" + str(_url(tb).port()) if _url(tb).port() != -1 else ""),
        'url:auth': lambda tb: "{}:{}@".format(
            _url(tb).userName(),
            _url(tb).password()) if _url(tb).userName() else "",
        'url:scheme': lambda tb: _url(tb).scheme(),
        'url:username': lambda tb: _url(tb).userName(),
        'url:password': lambda tb: _url(tb).password(),
        'url:host': lambda tb: _url(tb).host(),
        'url:port': lambda tb: str(
            _url(tb).port()) if _url(tb).port() != -1 else "",
        'url:path': lambda tb: _url(tb).path(),
        'url:query': lambda tb: _url(tb).query(),
        'title': lambda tb: tb.widget.page_title(tb.widget.currentIndex()),
        'clipboard': lambda _: utils.get_clipboard(),
        'primary': lambda _: utils.get_clipboard(selection=True),
    }  # type: typing.Dict[str, _ReplacementFunction]

    for key in list(replacements):
        modified_key = '{' + key + '}'
        # x = modified_key is to avoid binding x as a closure
        replacements[modified_key] = (
            lambda _, x=modified_key: x)  # type: ignore[misc]
    return replacements


VARIABLE_REPLACEMENTS = _init_variable_replacements()
# A regex matching all variable replacements
VARIABLE_REPLACEMENT_PATTERN = re.compile(
    "{(?P<var>" + "|".join(VARIABLE_REPLACEMENTS.keys()) + ")}")


def replace_variables(win_id, arglist):
    """Utility function to replace variables like {url} in a list of args."""
    tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                window=win_id)
    values = {}  # type: typing.MutableMapping[str, str]
    args = []

    def repl_cb(matchobj):
        """Return replacement for given match."""
        var = matchobj.group("var")
        if var not in values:
            values[var] = VARIABLE_REPLACEMENTS[var](tabbed_browser)
        return values[var]

    try:
        for arg in arglist:
            # using re.sub with callback function replaces all variables in a
            # single pass and avoids expansion of nested variables (e.g.
            # "{url}" from clipboard is not expanded)
            args.append(VARIABLE_REPLACEMENT_PATTERN.sub(repl_cb, arg))
    except utils.ClipboardError as e:
        raise cmdutils.CommandError(e)
    return args


class CommandParser:

    """Parse qutebrowser commandline commands.

    Attributes:
        _partial_match: Whether to allow partial command matches.
    """

    def __init__(self, partial_match=False):
        self._partial_match = partial_match

    def _get_alias(self, text, default=None):
        """Get an alias from the config.

        Args:
            text: The text to parse.
            default : Default value to return when alias was not found.

        Return:
            The new command string if an alias was found. Default value
            otherwise.
        """
        parts = text.strip().split(maxsplit=1)
        aliases = config.cache['aliases']
        if parts[0] not in aliases:
            return default
        alias = aliases[parts[0]]

        try:
            new_cmd = '{} {}'.format(alias, parts[1])
        except IndexError:
            new_cmd = alias
        if text.endswith(' '):
            new_cmd += ' '
        return new_cmd

    def _parse_all_gen(self, text, *args, aliases=True, **kwargs):
        """Split a command on ;; and parse all parts.

        If the first command in the commandline is a non-split one, it only
        returns that.

        Args:
            text: Text to parse.
            aliases: Whether to handle aliases.
            *args/**kwargs: Passed to parse().

        Yields:
            ParseResult tuples.
        """
        text = text.strip().lstrip(':').strip()
        if not text:
            raise cmdexc.NoSuchCommandError("No command given")

        if aliases:
            text = self._get_alias(text, text)

        if ';;' in text:
            # Get the first command and check if it doesn't want to have ;;
            # split.
            first = text.split(';;')[0]
            result = self.parse(first, *args, **kwargs)
            if result.cmd.no_cmd_split:
                sub_texts = [text]
            else:
                sub_texts = [e.strip() for e in text.split(';;')]
        else:
            sub_texts = [text]
        for sub in sub_texts:
            yield self.parse(sub, *args, **kwargs)

    def parse_all(self, *args, **kwargs):
        """Wrapper over _parse_all_gen."""
        return list(self._parse_all_gen(*args, **kwargs))

    def parse(self, text, *, fallback=False, keep=False):
        """Split the commandline text into command and arguments.

        Args:
            text: Text to parse.
            fallback: Whether to do a fallback splitting when the command was
                      unknown.
            keep: Whether to keep special chars and whitespace

        Return:
            A ParseResult tuple.
        """
        cmdstr, sep, argstr = text.partition(' ')

        if not cmdstr and not fallback:
            raise cmdexc.NoSuchCommandError("No command given")

        if self._partial_match:
            cmdstr = self._completion_match(cmdstr)

        try:
            cmd = objects.commands[cmdstr]
        except KeyError:
            if not fallback:
                raise cmdexc.NoSuchCommandError(
                    '{}: no such command'.format(cmdstr))
            cmdline = split.split(text, keep=keep)
            return ParseResult(cmd=None, args=None, cmdline=cmdline)

        args = self._split_args(cmd, argstr, keep)
        if keep and args:
            cmdline = [cmdstr, sep + args[0]] + args[1:]
        elif keep:
            cmdline = [cmdstr, sep]
        else:
            cmdline = [cmdstr] + args[:]

        return ParseResult(cmd=cmd, args=args, cmdline=cmdline)

    def _completion_match(self, cmdstr):
        """Replace cmdstr with a matching completion if there's only one match.

        Args:
            cmdstr: The string representing the entered command so far

        Return:
            cmdstr modified to the matching completion or unmodified
        """
        matches = [cmd for cmd in sorted(objects.commands, key=len)
                   if cmdstr in cmd]
        if len(matches) == 1:
            cmdstr = matches[0]
        elif len(matches) > 1 and config.val.completion.use_best_match:
            cmdstr = matches[0]
        return cmdstr

    def _split_args(self, cmd, argstr, keep):
        """Split the arguments from an arg string.

        Args:
            cmd: The command we're currently handling.
            argstr: An argument string.
            keep: Whether to keep special chars and whitespace

        Return:
            A list containing the split strings.
        """
        if not argstr:
            return []
        elif cmd.maxsplit is None:
            return split.split(argstr, keep=keep)
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
                    if arg in cmd.flags_with_args:
                        flag_arg_count += 1
                else:
                    maxsplit = i + cmd.maxsplit + flag_arg_count
                    return split.simple_split(argstr, keep=keep,
                                              maxsplit=maxsplit)

            # If there are only flags, we got it right on the first try
            # already.
            return split_args


class AbstractCommandRunner(QObject):

    """Abstract base class for CommandRunner."""

    def run(self, text, count=None, *, safely=False):
        raise NotImplementedError

    @pyqtSlot(str, int)
    @pyqtSlot(str)
    def run_safely(self, text, count=None):
        """Run a command and display exceptions in the statusbar."""
        self.run(text, count, safely=True)


class CommandRunner(AbstractCommandRunner):

    """Parse and run qutebrowser commandline commands.

    Attributes:
        _win_id: The window this CommandRunner is associated with.
    """

    def __init__(self, win_id, partial_match=False, parent=None):
        super().__init__(parent)
        self._parser = CommandParser(partial_match=partial_match)
        self._win_id = win_id

    @contextlib.contextmanager
    def _handle_error(self, safely: bool) -> typing.Iterator[None]:
        """Show exceptions as errors if safely=True is given."""
        try:
            yield
        except cmdexc.Error as e:
            if safely:
                message.error(str(e), stack=traceback.format_exc())
            else:
                raise

    def run(self, text, count=None, *, safely=False):
        """Parse a command from a line of text and run it.

        Args:
            text: The text to parse.
            count: The count to pass to the command.
            safely: Show CmdError exceptions as messages.
        """
        record_last_command = True
        record_macro = True

        mode_manager = modeman.instance(self._win_id)
        cur_mode = mode_manager.mode

        parsed = None
        with self._handle_error(safely):
            parsed = self._parser.parse_all(text)

        if parsed is None:
            return

        for result in parsed:
            with self._handle_error(safely):
                if result.cmd.no_replace_variables:
                    args = result.args
                else:
                    args = replace_variables(self._win_id, result.args)

                result.cmd.run(self._win_id, args, count=count)

            if result.cmdline[0] == 'repeat-command':
                record_last_command = False

            if result.cmdline[0] in ['record-macro', 'run-macro',
                                     'set-cmd-text']:
                record_macro = False

        if record_last_command:
            last_command[cur_mode] = (text, count)

        if record_macro and cur_mode == usertypes.KeyMode.normal:
            macros.macro_recorder.record_command(text, count)
