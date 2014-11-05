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

"""Our own fork of shlex.split with some added and removed features."""

from qutebrowser.utils import log


class ShellLexer:

    """A lexical analyzer class for simple shell-like syntaxes.

    Based on Python's shlex, but cleaned up, removed some features, and added
    some features useful for qutebrowser.

    Attributes:
        FIXME
    """

    def __init__(self, s):
        self.iterator = iter(s)
        self.whitespace = ' \t\r'
        self.quotes = '\'"'
        self.escape = '\\'
        self.escapedquotes = '"'
        self.keep = False

    def read_token(self):
        """Read a raw token from the input stream."""
        quoted = False
        escapedstate = ' '
        token = ''
        state = ' '
        while True:
            try:
                nextchar = next(self.iterator)
            except StopIteration:
                nextchar = None
            log.shlexer.vdebug("in state {!r} I see character: {!r}".format(
                state, nextchar))
            if state is None:
                # past end of file
                token = None
                break
            elif state == ' ':
                if nextchar is None:
                    state = None
                    break
                elif nextchar in self.whitespace:
                    log.shlexer.vdebug("I see whitespace in whitespace state")
                    if self.keep:
                        token += nextchar
                    if token or quoted:
                        # emit current token
                        break
                    else:
                        continue
                elif nextchar in self.escape:
                    if self.keep:
                        token += nextchar
                    escapedstate = 'a'
                    state = nextchar
                elif nextchar in self.quotes:
                    if self.keep:
                        token += nextchar
                    state = nextchar
                else:
                    token = nextchar
                    state = 'a'
            elif state in self.quotes:
                quoted = True
                if nextchar is None:
                    log.shlexer.vdebug("I see EOF in quotes state")
                    state = None
                    break
                if nextchar == state:
                    if self.keep:
                        token += nextchar
                    state = 'a'
                elif (nextchar in self.escape and
                        state in self.escapedquotes):
                    if self.keep:
                        token += nextchar
                    escapedstate = state
                    state = nextchar
                else:
                    token += nextchar
            elif state in self.escape:
                if nextchar is None:
                    log.shlexer.vdebug("I see EOF in escape state")
                    if not self.keep:
                        token += state
                    state = None
                    break
                # In posix shells, only the quote itself or the escape
                # character may be escaped within quotes.
                if (escapedstate in self.quotes and nextchar != state and
                        nextchar != escapedstate and not self.keep):
                    token += state
                token += nextchar
                state = escapedstate
            elif state == 'a':
                if nextchar is None:
                    state = None
                    break
                elif nextchar in self.whitespace:
                    log.shlexer.vdebug("shlex: I see whitespace in word state")
                    state = ' '
                    if self.keep:
                        token += nextchar
                    if token or quoted:
                        break   # emit current token
                    else:
                        continue
                elif nextchar in self.quotes:
                    if self.keep:
                        token += nextchar
                    state = nextchar
                elif nextchar in self.escape:
                    if self.keep:
                        token += nextchar
                    escapedstate = 'a'
                    state = nextchar
                else:
                    token += nextchar
        if not quoted and token == '':
            token = None
        log.shlexer.vdebug("token={!r}".format(token))
        return token

    def __iter__(self):
        while True:
            token = self.read_token()
            if token is None:
                return
            else:
                yield token


def split(s, keep=False):
    """Split a string via ShellLexer.

    Args:
        keep: Whether to keep are special chars in the split output.
    """
    lexer = ShellLexer(s)
    lexer.keep = keep
    tokens = list(lexer)
    out = []
    if tokens[0].isspace():
        out.append(tokens[0] + tokens[1])
        tokens = tokens[2:]
    for t in tokens:
        if t.isspace():
            out[-1] += t
        else:
            out.append(t)
    return out
