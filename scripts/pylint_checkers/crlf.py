# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

"""Checker for CRLF in files."""

from pylint import interfaces, checkers


class CrlfChecker(checkers.BaseChecker):

    """Check for CRLF in files."""

    __implements__ = interfaces.IRawChecker

    name = 'crlf'
    msgs = {'W9001': ('Uses CRLFs', 'crlf', None)}
    options = ()
    priority = -1

    def process_module(self, node):
        """Process the module."""
        for (lineno, line) in enumerate(node.file_stream):
            if b'\r\n' in line:
                self.add_message('crlf', line=lineno)
                return


def register(linter):
    """Register the checker."""
    linter.register_checker(CrlfChecker(linter))
