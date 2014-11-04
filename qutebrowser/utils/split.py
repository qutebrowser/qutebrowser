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

from io import StringIO

from qutebrowser.utils import log


class ShellLexer:

    """A lexical analyzer class for simple shell-like syntaxes.

    Based on Python's shlex, but cleaned up, removed some features, and added
    some features useful for qutebrowser.

    Attributes:
        FIXME
    """

    def __init__(self, s):
        self.instream = StringIO(s)
        self.whitespace = ' \t\r\n'
        self.quotes = '\'"'
        self.escape = '\\'
        self.escapedquotes = '"'
        self.state = ' '
        self.token = ''

    def read_token(self):
        """Read a raw token from the input stream."""
        quoted = False
        escapedstate = ' '
        while True:
            nextchar = self.instream.read(1)
            log.shlexer.vdebug("in state {!r} I see character: {!r}".format(
                self.state, nextchar))
            if self.state is None:
                self.token = None        # past end of file
                break
            elif self.state == ' ':
                if not nextchar:
                    self.state = None  # end of file
                    break
                elif nextchar in self.whitespace:
                    log.shlexer.vdebug("I see whitespace in whitespace state")
                    if self.token or quoted:
                        break   # emit current token
                    else:
                        continue
                elif nextchar in self.escape:
                    escapedstate = 'a'
                    self.state = nextchar
                elif nextchar in self.quotes:
                    self.state = nextchar
                else:
                    self.token = nextchar
                    self.state = 'a'
            elif self.state in self.quotes:
                quoted = True
                if not nextchar:      # end of file
                    log.shlexer.vdebug("I see EOF in quotes state")
                    # XXX what error should be raised here?
                    raise ValueError("No closing quotation")
                if nextchar == self.state:
                    self.state = 'a'
                elif (nextchar in self.escape and
                        self.state in self.escapedquotes):
                    escapedstate = self.state
                    self.state = nextchar
                else:
                    self.token = self.token + nextchar
            elif self.state in self.escape:
                if not nextchar:      # end of file
                    log.shlexer.vdebug("I see EOF in escape state")
                    # XXX what error should be raised here?
                    raise ValueError("No escaped character")
                # In posix shells, only the quote itself or the escape
                # character may be escaped within quotes.
                if escapedstate in self.quotes and \
                   nextchar != self.state and nextchar != escapedstate:
                    self.token = self.token + self.state
                self.token = self.token + nextchar
                self.state = escapedstate
            elif self.state == 'a':
                if not nextchar:
                    self.state = None   # end of file
                    break
                elif nextchar in self.whitespace:
                    log.shlexer.vdebug("shlex: I see whitespace in word state")
                    self.state = ' '
                    if self.token or quoted:
                        break   # emit current token
                    else:
                        continue
                elif nextchar in self.quotes:
                    self.state = nextchar
                elif nextchar in self.escape:
                    escapedstate = 'a'
                    self.state = nextchar
                else:
                    self.token = self.token + nextchar
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


def _get_lexer(s):
    """Get an shlex lexer for split."""
    if s is None:
        raise TypeError("Refusing to create a lexer with s=None!")
    lexer = ShellLexer(s)
    return lexer


def split(s):
    r"""Split a string via shlex safely (don't bail out on unbalanced quotes).

    We split while the user is typing (for completion), and as
    soon as ", ' or \ is typed, the string is invalid for shlex,
    because it encounters EOF while in quote/escape state.

    Here we fix this error temporarily so shlex doesn't blow up,
    and then retry splitting again.

    Since shlex raises ValueError in both cases we unfortunately
    have to parse the exception string...

    We try 3 times so multiple errors can be fixed.
    """
    orig_s = s
    for i in range(3):
        lexer = _get_lexer(s)
        try:
            tokens = list(lexer)
        except ValueError as e:
            if str(e) not in ("No closing quotation", "No escaped character"):
                raise
            # eggs "bacon ham -> eggs "bacon ham"
            # eggs\ -> eggs\\
            if lexer.state not in lexer.escape + lexer.quotes:
                raise AssertionError(
                    "Lexer state is >{}< while parsing >{}< (attempted fixup: "
                    ">{}<)".format(lexer.state, orig_s, s))
            s += lexer.state
        else:
            return tokens
    # We should never arrive here.
    raise AssertionError(
        "Gave up splitting >{}< after {} tries. Attempted fixup: >{}<.".format(
            orig_s, i, s))  # pylint: disable=undefined-loop-variable
