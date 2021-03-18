# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2021 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Module for parsing commands entered into the browser."""

import dataclasses
from typing import List, Iterator

from qutebrowser.commands import cmdexc, command
from qutebrowser.misc import split, objects
from qutebrowser.config import config


@dataclasses.dataclass
class ParseResult:

    """The result of parsing a commandline."""

    cmd: command.Command
    args: List[str]
    cmdline: List[str]


class CommandParser:

    """Parse qutebrowser commandline commands.

    Attributes:
        _partial_match: Whether to allow partial command matches.
    """

    def __init__(self, partial_match: bool = False) -> None:
        self._partial_match = partial_match

    def _get_alias(self, text: str, *, default: str) -> str:
        """Get an alias from the config.

        Args:
            text: The text to parse.
            aliases: A map of aliases to commands.
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

    def _parse_all_gen(
            self,
            text: str,
            aliases: bool = True,
            **kwargs: bool,
    ) -> Iterator[ParseResult]:
        """Split a command on ;; and parse all parts.

        If the first command in the commandline is a non-split one, it only
        returns that.

        Args:
            text: Text to parse.
            aliases: Whether to handle aliases.
            **kwargs: Passed to parse().

        Yields:
            ParseResult tuples.
        """
        text = text.strip().lstrip(':').strip()
        if not text:
            raise cmdexc.NoSuchCommandError("No command given")

        if aliases:
            text = self._get_alias(text, default=text)

        if ';;' in text:
            # Get the first command and check if it doesn't want to have ;;
            # split.
            first = text.split(';;')[0]
            result = self.parse(first, **kwargs)
            if result.cmd.no_cmd_split:
                sub_texts = [text]
            else:
                sub_texts = [e.strip() for e in text.split(';;')]
        else:
            sub_texts = [text]
        for sub in sub_texts:
            yield self.parse(sub, **kwargs)

    def parse_all(self, text: str, **kwargs: bool) -> List[ParseResult]:
        """Wrapper over _parse_all_gen."""
        return list(self._parse_all_gen(text, **kwargs))

    def parse(self, text: str, *, keep: bool = False) -> ParseResult:
        """Split the commandline text into command and arguments.

        Args:
            text: Text to parse.
            keep: Whether to keep special chars and whitespace.
        """
        cmdstr, sep, argstr = text.partition(' ')

        if not cmdstr:
            raise cmdexc.NoSuchCommandError("No command given")

        if self._partial_match:
            cmdstr = self._completion_match(cmdstr)

        try:
            cmd = objects.commands[cmdstr]
        except KeyError:
            raise cmdexc.NoSuchCommandError(f'{cmdstr}: no such command')

        args = self._split_args(cmd, argstr, keep)
        if keep and args:
            cmdline = [cmdstr, sep + args[0]] + args[1:]
        elif keep:
            cmdline = [cmdstr, sep]
        else:
            cmdline = [cmdstr] + args[:]

        return ParseResult(cmd=cmd, args=args, cmdline=cmdline)

    def _completion_match(self, cmdstr: str) -> str:
        """Replace cmdstr with a matching completion if there's only one match.

        Args:
            cmdstr: The string representing the entered command so far.

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

    def _split_args(self, cmd: command.Command, argstr: str, keep: bool) -> List[str]:
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
