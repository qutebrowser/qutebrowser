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

"""Custom astroid checker for config calls."""

import sys
import os
import os.path

import astroid
from pylint import interfaces, checkers
from pylint.checkers import utils

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))

from qutebrowser.config import configdata


class ConfigChecker(checkers.BaseChecker):

    """Custom astroid checker for config calls."""

    __implements__ = interfaces.IAstroidChecker
    name = 'config'
    msgs = {
        'E0000': ('"%s -> %s" is no valid config option.', 'bad-config-call',
                  None),
    }
    priority = -1

    @utils.check_messages('bad-config-call')
    def visit_callfunc(self, node):
        """Visit a CallFunc node."""
        if hasattr(node, 'func'):
            infer = utils.safe_infer(node.func)
            if infer and infer.root().name == 'qutebrowser.config.config':
                if getattr(node.func, 'attrname', None) in ('get', 'set'):
                    self._check_config(node)

    def _check_config(self, node):
        """Check that the arguments to config.get(...) are valid.

        FIXME: We should check all ConfigManager calls.
        https://github.com/The-Compiler/qutebrowser/issues/107
        """
        try:
            sect_arg = utils.get_argument_from_call(node, position=0,
                                                    keyword='sectname')
            opt_arg = utils.get_argument_from_call(node, position=1,
                                                   keyword='optname')
        except utils.NoSuchArgumentError:
            return
        sect_arg = utils.safe_infer(sect_arg)
        opt_arg = utils.safe_infer(opt_arg)
        if not (isinstance(sect_arg, astroid.Const) and
                isinstance(opt_arg, astroid.Const)):
            return
        try:
            configdata.DATA[sect_arg.value][opt_arg.value]
        except KeyError:
            self.add_message('bad-config-call', node=node,
                             args=(sect_arg.value, opt_arg.value))


def register(linter):
    """Register this checker."""
    linter.register_checker(ConfigChecker(linter))
