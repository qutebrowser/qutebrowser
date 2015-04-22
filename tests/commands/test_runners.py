# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for qutebrowser.commands.runners."""

import pytest

from qutebrowser.commands import runners, cmdexc


class TestCommandRunner:

    """Tests for CommandRunner."""

    def test_parse_all(self, cmdline_test):
        """Test parsing of commands.

        See https://github.com/The-Compiler/qutebrowser/issues/615

        Args:
            cmdline_test: A pytest fixture which provides testcases.
        """
        cr = runners.CommandRunner(0)
        if cmdline_test.valid:
            list(cr.parse_all(cmdline_test.cmd, aliases=False))
        else:
            with pytest.raises(cmdexc.NoSuchCommandError):
                list(cr.parse_all(cmdline_test.cmd, aliases=False))
