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
        self.whitespace = ' \t\r\n'
        self.quotes = '\'"'
        self.escape = '\\'
        self.escapedquotes = '"'
        self.state = ' '
        self.token = ''
        self.keep = False

    def read_token(self):
        """Read a raw token from the input stream."""
        quoted = False
        escapedstate = ' '
        while True:
            try:
                nextchar = next(self.iterator)
            except StopIteration:
                nextchar = None
            log.shlexer.vdebug("in state {!r} I see character: {!r}".format(
                self.state, nextchar))
            if self.state is None:
                # past end of file
                self.token = None
                break
            elif self.state == ' ':
                if nextchar is None:
                    self.state = None
                    break
                elif nextchar in self.whitespace:
                    log.shlexer.vdebug("I see whitespace in whitespace state")
                    if self.keep:
                        self.token += nextchar
                    if self.token or quoted:
                        # emit current token
                        break
                    else:
                        continue
                elif nextchar in self.escape:
                    if self.keep:
                        self.token += nextchar
                    escapedstate = 'a'
                    self.state = nextchar
                elif nextchar in self.quotes:
                    if self.keep:
                        self.token += nextchar
                    self.state = nextchar
                else:
                    self.token = nextchar
                    self.state = 'a'
            elif self.state in self.quotes:
                quoted = True
                if nextchar is None:
                    log.shlexer.vdebug("I see EOF in quotes state")
                    self.state = None
                    break
                if nextchar == self.state:
                    if self.keep:
                        self.token += nextchar
                    self.state = 'a'
                elif (nextchar in self.escape and
                        self.state in self.escapedquotes):
                    if self.keep:
                        self.token += nextchar
                    escapedstate = self.state
                    self.state = nextchar
                else:
                    self.token += nextchar
            elif self.state in self.escape:
                if nextchar is None:
                    log.shlexer.vdebug("I see EOF in escape state")
                    if not self.keep:
                        self.token += self.state
                    self.state = None
                    break
                # In posix shells, only the quote itself or the escape
                # character may be escaped within quotes.
                if (escapedstate in self.quotes and nextchar != self.state and
                        nextchar != escapedstate and not self.keep):
                    self.token += self.state
                self.token += nextchar
                self.state = escapedstate
            elif self.state == 'a':
                if nextchar is None:
                    self.state = None
                    break
                elif nextchar in self.whitespace:
                    log.shlexer.vdebug("shlex: I see whitespace in word state")
                    self.state = ' '
                    if self.keep:
                        self.token += nextchar
                    if self.token or quoted:
                        break   # emit current token
                    else:
                        continue
                elif nextchar in self.quotes:
                    if self.keep:
                        self.token += nextchar
                    self.state = nextchar
                elif nextchar in self.escape:
                    if self.keep:
                        self.token += nextchar
                    escapedstate = 'a'
                    self.state = nextchar
                else:
                    self.token += nextchar
        result = self.token
        self.token = ''
        if not quoted and result == '':
            result = None
        log.shlexer.debug("token={!r}".format(result))
        return result

    def __iter__(self):
        return self

    def __next__(self):
        token = self.read_token()
        if token is None:
            raise StopIteration
        return token


def split(s, keep=False):
    """Split a string via ShellLexer.

    Args:
        keep: Whether to keep are special chars in the split output.
    """
    lexer = ShellLexer(s)
    lexer.keep = keep
    return list(lexer)
