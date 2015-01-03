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

"""Checker for vim modelines in files."""

import os.path

from pylint import interfaces, checkers


class ModelineChecker(checkers.BaseChecker):

    """Check for vim modelines in files."""

    __implements__ = interfaces.IRawChecker

    name = 'modeline'
    msgs = {'W9002': ('Does not have vim modeline', 'modeline-missing', None),
            'W9003': ('Modeline is invalid', 'invalid-modeline', None),
            'W9004': ('Modeline position is wrong', 'modeline-position', None)}
    options = ()
    priority = -1

    def process_module(self, node):
        """Process the module."""
        if os.path.basename(os.path.splitext(node.file)[0]) == '__init__':
            return
        max_lineno = 1
        for (lineno, line) in enumerate(node.file_stream):
            if lineno == 1 and line.startswith(b'#!'):
                max_lineno += 1
                continue
            elif line.startswith(b'# vim:'):
                if lineno > max_lineno:
                    self.add_message('modeline-position', line=lineno)
                if (line.rstrip() !=
                        b'# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:'):
                    self.add_message('invalid-modeline', line=lineno)
                break
        else:
            self.add_message('modeline-missing', line=1)


def register(linter):
    """Register the checker."""
    linter.register_checker(ModelineChecker(linter))
