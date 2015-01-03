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

"""Custom astroid checker for set_trace calls."""

from pylint.interfaces import IAstroidChecker
from pylint.checkers import BaseChecker, utils


class SetTraceChecker(BaseChecker):

    """Custom astroid checker for set_trace calls."""

    __implements__ = IAstroidChecker
    name = 'settrace'
    msgs = {
        'E9101': ('set_trace call found', 'set-trace', None),
    }
    priority = -1

    @utils.check_messages('set-trace')
    def visit_callfunc(self, node):
        """Visit a CallFunc node."""
        if hasattr(node, 'func'):
            infer = utils.safe_infer(node.func)
            if infer:
                if getattr(node.func, 'name', None) == 'set_trace':
                    self.add_message('set-trace', node=node)


def register(linter):
    """Register this checker."""
    linter.register_checker(SetTraceChecker(linter))
