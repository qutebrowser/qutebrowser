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

"""Our own fork of shlex.split with some added and removed features."""

import re

from qutebrowser.utils import log


class ShellLexer:

    """A lexical analyzer class for simple shell-like syntaxes.

    Based on Python's shlex, but cleaned up, removed some features, and added
    some features useful for qutebrowser.

    Attributes:
        FIXME
    """

    def __init__(self, s):
        self.string = s
        self.whitespace = ' \t\r'
        self.quotes = '\'"'
        self.escape = '\\'
        self.escapedquotes = '"'
        self.keep = False
        self.quoted = None
        self.escapedstate = None
        self.token = None
        self.state = None
        self.reset()

    def reset(self):
        """Reset the state machine state to the defaults."""
        self.quoted = False
        self.escapedstate = ' '
        self.token = ''
        self.state = ' '

    def __iter__(self):  # pragma: no mccabe
        """Read a raw token from the input stream."""
        # pylint: disable=too-many-branches,too-many-statements
        self.reset()
        for nextchar in self.string:
            if self.state == ' ':
                if self.keep:
                    self.token += nextchar
                if nextchar in self.whitespace:
                    if self.token or self.quoted:
                        yield self.token
                        self.reset()
                elif nextchar in self.escape:
                    self.escapedstate = 'a'
                    self.state = nextchar
                elif nextchar in self.quotes:
                    self.state = nextchar
                else:
                    self.token = nextchar
                    self.state = 'a'
            elif self.state in self.quotes:
                self.quoted = True
                if nextchar == self.state:
                    if self.keep:
                        self.token += nextchar
                    self.state = 'a'
                elif (nextchar in self.escape and
                      self.state in self.escapedquotes):
                    if self.keep:
                        self.token += nextchar
                    self.escapedstate = self.state
                    self.state = nextchar
                else:
                    self.token += nextchar
            elif self.state in self.escape:
                # In posix shells, only the quote itself or the escape
                # character may be escaped within quotes.
                if (self.escapedstate in self.quotes and
                        nextchar != self.state and
                        nextchar != self.escapedstate and not self.keep):
                    self.token += self.state
                self.token += nextchar
                self.state = self.escapedstate
            elif self.state == 'a':
                if nextchar in self.whitespace:
                    self.state = ' '
                    assert self.token or self.quoted
                    yield self.token
                    self.reset()
                    if self.keep:
                        yield nextchar
                elif nextchar in self.quotes:
                    if self.keep:
                        self.token += nextchar
                    self.state = nextchar
                elif nextchar in self.escape:
                    if self.keep:
                        self.token += nextchar
                    self.escapedstate = 'a'
                    self.state = nextchar
                else:
                    self.token += nextchar
            else:
                raise AssertionError("Invalid state {!r}!".format(self.state))
        if self.state in self.escape and not self.keep:
            self.token += self.state
        if self.token or self.quoted:
            yield self.token


def split(s, keep=False):
    """Split a string via ShellLexer.

    Args:
        keep: Whether to keep special chars in the split output.
    """
    lexer = ShellLexer(s)
    lexer.keep = keep
    tokens = list(lexer)
    if not tokens:
        return []
    out = []
    spaces = ""

    log.shlexer.vdebug("{!r} -> {!r}".format(s, tokens))

    for t in tokens:
        if t.isspace():
            spaces += t
        else:
            out.append(spaces + t)
            spaces = ""
    if spaces:
        out.append(spaces)

    return out


def _combine_ws(parts, whitespace):
    """Combine whitespace in a list with the element following it.

    Args:
        parts: A list of strings.
        whitespace: A string containing what's considered whitespace.

    Return:
        The modified list.
    """
    out = []
    ws = ''
    for part in parts:
        if not part:
            continue
        elif part in whitespace:
            ws += part
        else:
            out.append(ws + part)
            ws = ''
    if ws:
        out.append(ws)
    return out


def simple_split(s, keep=False, maxsplit=None):
    """Split a string on whitespace, optionally keeping the whitespace.

    Args:
        s: The string to split.
        keep: Whether to keep whitespace.
        maxsplit: The maximum count of splits.

    Return:
        A list of split strings.
    """
    whitespace = '\n\t '
    if maxsplit == 0:
        # re.split with maxsplit=0 splits everything, while str.split splits
        # nothing (which is the behavior we want).
        if keep:
            return [s]
        else:
            return [s.strip(whitespace)]
    elif maxsplit is None:
        maxsplit = 0

    if keep:
        pattern = '([' + whitespace + '])'
        parts = re.split(pattern, s, maxsplit)
        return _combine_ws(parts, whitespace)
    else:
        pattern = '[' + whitespace + ']'
        parts = re.split(pattern, s, maxsplit)
        parts[-1] = parts[-1].rstrip()
        return [p for p in parts if p]
