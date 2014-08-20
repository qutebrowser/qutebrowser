# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Make sure open() has an encoding set."""

from pylint.interfaces import IAstroidChecker
from pylint.checkers import BaseChecker
from pylint.checkers import utils


class OpenEncodingChecker(BaseChecker):

    """Checker to check open() has an encoding set."""

    __implements__ = IAstroidChecker
    name = 'open-encoding'

    msgs = {
        'W9400': ('open() called without encoding', 'open-without-encoding',
                  None),
    }

    @utils.check_messages('open-without-encoding')
    def visit_callfunc(self, node):
        """Visit a CallFunc node."""
        if hasattr(node, 'func'):
            infer = utils.safe_infer(node.func)
            if infer and infer.root().name == '_io':
                if getattr(node.func, 'name', None) in ('open', 'file'):
                    self._check_open_encoding(node)

    def _check_open_encoding(self, node):
        """Check that an open() call always has an encoding set."""
        try:
            _encoding = utils.get_argument_from_call(node, position=3,
                                                     keyword='encoding')
        except utils.NoSuchArgumentError:
            self.add_message('open-without-encoding', node=node)


def register(linter):
    """Register this checker."""
    linter.register_checker(OpenEncodingChecker(linter))
