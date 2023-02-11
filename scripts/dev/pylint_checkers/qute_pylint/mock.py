# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Custom astroid checker for mock calls."""

from qutebrowser.utils import utils

import astroid.nodes
from pylint import checkers


def is_patch_multiple_call(node):
    if not hasattr(node, "func"):
        return False

    if isinstance(node.func, astroid.nodes.Name):
        return node.func.name == 'multiple' and node.func.as_string().endswith("patch.multiple")
    elif isinstance(node.func, astroid.nodes.Attribute):
        return node.func.attrname == 'multiple' and node.func.as_string().endswith("patch.multiple")

    for child in node.get_children():
        return is_patch_call(child)

    raise utils.Unreachable()


def is_patch_object_call(node):
    if not hasattr(node, "func"):
        return False

    if isinstance(node.func, astroid.nodes.Name):
        return node.func.name == 'object' and node.func.as_string().endswith("patch.object")
    elif isinstance(node.func, astroid.nodes.Attribute):
        return node.func.attrname == 'object' and node.func.as_string().endswith("patch.object")

    for child in node.get_children():
        return is_patch_call(child)

    raise utils.Unreachable()


def is_patch_call(node):
    if not hasattr(node, "func"):
        return False

    if isinstance(node.func, astroid.nodes.Name):
        return node.func.name == 'patch'
    elif isinstance(node.func, astroid.nodes.Attribute):
        return node.func.attrname == 'patch'

    for child in node.get_children():
        return is_patch_call(child)

    raise utils.Unreachable()


def is_mock_call(node):
    if not hasattr(node, "func"):
        return False

    if isinstance(node.func, astroid.nodes.Name):
        return node.func.name in ('Mock', 'MagicMock')
    elif isinstance(node.func, astroid.nodes.Attribute):
        return node.func.attrname in ('Mock', 'MagicMock')

    for child in node.get_children():
        return is_patch_call(child)

    raise utils.Unreachable()


class MockChecker(checkers.BaseChecker):

    """Custom astroid checker for mock calls."""

    name = 'mock'
    msgs = {
        'E9997': ('Call should have the spec keyword argument',  # flake8: disable=S001
                  'mock-missing-spec',
                  None),
    }
    priority = -1
    printed_warning = False

    def visit_call(self, node: astroid.nodes.Call):
        """Emit a message for mock calls without a spec.

        A spec can be provided to a Mock() call via the following arguments:
        * spec
        * spec_set

        Args:
            node: the currently visited node
        """
        if not is_mock_call(node):
            return

        has_spec_arg = len(node.args) >= 1
        spec_keywords = (kw for kw in node.keywords if kw.arg in ("spec", "spec_set"))
        if has_spec_arg or any(spec_keywords):
            return

        self.add_message('mock-missing-spec', node=node)


class PatchChecker(checkers.BaseChecker):

    """Custom astroid checker for patch calls."""

    name = 'patch'
    msgs = {
        'E9996': ('Call should have the spec or autospec keyword argument',  # flake8: disable=S001
                  'patch-missing-spec',
                  None),
    }
    priority = -1
    printed_warning = False

    def visit_call(self, node: astroid.nodes.Call):
        """Emit a message for patch calls without a spec.

        A spec can be provided to the patch call using the following arguments:
        - spec
        - autospec
        - new
        - new_callable

        Args:
            node: the currently visited node
        """
        if not (is_patch_call(node) or
                is_patch_object_call(node) or
                is_patch_multiple_call(node)):
            return

        spec_keywords = [kw
                         for kw in node.keywords
                         if kw.arg in ('spec',
                                       'autospec',
                                       'new',
                                       'new_callable')]
        if any(spec_keywords):
            return

        # patch.multiple() has now positional argument `new`
        has_new_arg = ((is_patch_call(node) and len(node.args) >= 2) or
                       (is_patch_object_call(node) and len(node.args) >= 3))
        if has_new_arg:
            return

        self.add_message('patch-missing-spec', node=node)


def register(linter):
    """Register this checker."""
    linter.register_checker(MockChecker(linter))
    linter.register_checker(PatchChecker(linter))
