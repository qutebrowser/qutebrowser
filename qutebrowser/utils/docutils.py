# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Utilities used for the documentation and built-in help."""

import re
import sys
import inspect
import os.path
import collections
import enum
import typing

import qutebrowser
from qutebrowser.utils import log, utils


def is_git_repo() -> bool:
    """Check if we're running from a git repository."""
    gitfolder = os.path.join(qutebrowser.basedir, os.path.pardir, '.git')
    return os.path.isdir(gitfolder)


def docs_up_to_date(path: str) -> bool:
    """Check if the generated html documentation is up to date.

    Args:
        path: The path of the document to check.

    Return:
        True if they are up to date or we couldn't check.
        False if they are outdated.
    """
    if hasattr(sys, 'frozen') or not is_git_repo():
        return True
    html_path = os.path.join(qutebrowser.basedir, 'html', 'doc', path)
    filename = os.path.splitext(path)[0]
    asciidoc_path = os.path.join(qutebrowser.basedir, os.path.pardir,
                                 'doc', 'help', filename + '.asciidoc')
    try:
        html_time = os.path.getmtime(html_path)
        asciidoc_time = os.path.getmtime(asciidoc_path)
    except FileNotFoundError:
        return True
    return asciidoc_time <= html_time


class DocstringParser:

    """Generate documentation based on a docstring of a command handler.

    The docstring needs to follow the format described in doc/contributing.

    Attributes:
        _state: The current state of the parser state machine.
        _cur_arg_name: The name of the argument we're currently handling.
        _short_desc_parts: The short description of the function as list.
        _long_desc_parts: The long description of the function as list.
        short_desc: The short description of the function.
        long_desc: The long description of the function.
        arg_descs: A dict of argument names to their descriptions
    """

    State = enum.Enum('State', ['short', 'desc', 'desc_hidden',
                                'arg_start', 'arg_inside', 'misc'])

    def __init__(self, func: typing.Callable) -> None:
        """Constructor.

        Args:
            func: The function to parse the docstring for.
        """
        self._state = self.State.short
        self._cur_arg_name = None  # type: typing.Optional[str]
        self._short_desc_parts = []  # type: typing.List[str]
        self._long_desc_parts = []  # type: typing.List[str]
        self.arg_descs = collections.OrderedDict(
        )  # type: typing.Dict[str, typing.Union[str, typing.List[str]]]
        doc = inspect.getdoc(func)
        handlers = {
            self.State.short: self._parse_short,
            self.State.desc: self._parse_desc,
            self.State.desc_hidden: self._skip,
            self.State.arg_start: self._parse_arg_start,
            self.State.arg_inside: self._parse_arg_inside,
            self.State.misc: self._skip,
        }
        if doc is None:
            if sys.flags.optimize < 2:
                log.commands.warning(
                    "Function {}() from {} has no docstring".format(
                        utils.qualname(func),
                        inspect.getsourcefile(func)))
            self.long_desc = ""
            self.short_desc = ""
            return
        for line in doc.splitlines():
            handler = handlers[self._state]
            stop = handler(line)
            if stop:
                break
        for k, v in self.arg_descs.items():
            desc = ' '.join(v)
            desc = re.sub(r', or None($|\.)', r'\1', desc)
            desc = re.sub(r', or None', r', or not given', desc)
            self.arg_descs[k] = desc
        self.long_desc = ' '.join(self._long_desc_parts)
        self.short_desc = ' '.join(self._short_desc_parts)

    def _process_arg(self, line: str) -> None:
        """Helper method to process a line like 'fooarg: Blah blub'."""
        self._cur_arg_name, argdesc = line.split(':', maxsplit=1)
        self._cur_arg_name = self._cur_arg_name.strip().lstrip('*')
        self.arg_descs[self._cur_arg_name] = [argdesc.strip()]

    def _skip(self, line: str) -> None:
        """Handler to ignore everything until we get 'Args:'."""
        if line.startswith('Args:'):
            self._state = self.State.arg_start

    def _parse_short(self, line: str) -> None:
        """Parse the short description (first block) in the docstring."""
        if not line:
            self._state = self.State.desc
        else:
            self._short_desc_parts.append(line.strip())

    def _parse_desc(self, line: str) -> None:
        """Parse the long description in the docstring."""
        if line.startswith('Args:'):
            self._state = self.State.arg_start
        elif line.strip() == '//' or line.startswith('Attributes:'):
            self._state = self.State.desc_hidden
        elif line.strip():
            self._long_desc_parts.append(line.strip())

    def _parse_arg_start(self, line: str) -> None:
        """Parse first argument line."""
        self._process_arg(line)
        self._state = self.State.arg_inside

    def _parse_arg_inside(self, line: str) -> bool:
        """Parse subsequent argument lines."""
        argname = self._cur_arg_name
        assert argname is not None

        descs = self.arg_descs[argname]
        assert isinstance(descs, list)

        if re.fullmatch(r'[A-Z][a-z]+:', line):
            if not descs[-1].strip():
                del descs[-1]
                return True
        elif not line.strip():
            descs.append('\n\n')
        elif line[4:].startswith(' '):
            descs.append(line.strip() + '\n')
        else:
            self._process_arg(line)
        return False
