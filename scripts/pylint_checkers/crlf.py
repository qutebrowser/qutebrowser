"""Checker for CRLF in files."""

from pylint.interfaces import IRawChecker
from pylint.checkers import BaseChecker


class CrlfChecker(BaseChecker):

    """Check for CRLF in files."""

    __implements__ = IRawChecker

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
