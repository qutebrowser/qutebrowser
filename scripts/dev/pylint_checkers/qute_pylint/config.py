# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import yaml
import astroid
from pylint import interfaces, checkers
from pylint.checkers import utils


OPTIONS = None


class ConfigChecker(checkers.BaseChecker):

    """Custom astroid checker for config calls."""

    __implements__ = interfaces.IAstroidChecker
    name = 'config'
    msgs = {
        'E9998': ('%s is no valid config option.',  # flake8: disable=S001
                  'bad-config-call',
                  None),
        'E9999': ('old config call',  # flake8: disable=S001
                  'old-config-call',
                  None),
    }
    priority = -1

    @utils.check_messages('bad-config-call')
    def visit_attribute(self, node):
        """Visit a getattr node."""
        # At the end of a config.val.foo.bar chain
        if not isinstance(node.parent, astroid.Attribute):
            # FIXME do some proper check for this...
            node_str = node.as_string()
            prefix = 'config.val.'
            if node_str.startswith(prefix):
                self._check_config(node, node_str[len(prefix):])

    def _check_config(self, node, name):
        """Check that we're accessing proper config options."""
        if name not in OPTIONS:
            self.add_message('bad-config-call', node=node, args=name)


def register(linter):
    """Register this checker."""
    linter.register_checker(ConfigChecker(linter))
    global OPTIONS
    yaml_file = os.path.join('qutebrowser', 'config', 'configdata.yml')
    with open(yaml_file, 'r', encoding='utf-8') as f:
        OPTIONS = list(yaml.load(f))
