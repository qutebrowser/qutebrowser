# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Custom astroid checker for config calls."""

import sys
import pathlib

import yaml
import astroid
from pylint import interfaces, checkers
from pylint.checkers import utils


OPTIONS = None
FAILED_LOAD = False


class ConfigChecker(checkers.BaseChecker):

    """Custom astroid checker for config calls."""

    name = 'config'
    msgs = {
        'E9998': ('%s is no valid config option.',  # flake8: disable=S001
                  'bad-config-option',
                  None),
    }
    priority = -1
    printed_warning = False

    @utils.only_required_for_messages('bad-config-option')
    def visit_attribute(self, node):
        """Visit a getattr node."""
        # We're only interested in the end of a config.val.foo.bar chain
        if isinstance(node.parent, astroid.Attribute):
            return

        if isinstance(node.parent, astroid.Call):
            # Skip dynamic getattr()
            func = node.parent.func
            if isinstance(func, astroid.Name) and func.name == 'getattr':
                return
            # Handle .items() / .values()
            if node.attrname in ['items', 'values']:
                node = node.expr

        # FIXME:conf do some proper check for this...
        node_str = node.as_string()
        prefix = 'config.val.'
        if node_str.startswith(prefix):
            self._check_config(node, node_str.removeprefix(prefix))

    def _check_config(self, node, name):
        """Check that we're accessing proper config options."""
        if FAILED_LOAD:
            if not ConfigChecker.printed_warning:
                print("[WARN] Could not find configdata.yml. Please run "
                      "pylint from qutebrowser root.", file=sys.stderr)
                print("Skipping some checks...", file=sys.stderr)
                ConfigChecker.printed_warning = True
            return
        if name not in OPTIONS:
            self.add_message('bad-config-option', node=node, args=name)


def register(linter):
    """Register this checker."""
    linter.register_checker(ConfigChecker(linter))
    global OPTIONS
    global FAILED_LOAD
    yaml_file = pathlib.Path('qutebrowser') / 'config' / 'configdata.yml'
    if not yaml_file.exists():
        OPTIONS = None
        FAILED_LOAD = True
        return
    with yaml_file.open(mode='r', encoding='utf-8') as f:
        OPTIONS = list(yaml.safe_load(f))
