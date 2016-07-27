# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

    def test_parse_all_with_alias(self, cmdline_test, config_stub):
        config_stub.data = {'aliases': {'alias_name': cmdline_test.cmd}}

        cr = runners.CommandRunner(0)
        if cmdline_test.valid:
            assert len(list(cr.parse_all("alias_name"))) > 0
        else:
            with pytest.raises(cmdexc.NoSuchCommandError):
                list(cr.parse_all("alias_name"))

    def test_parse_empty_with_alias(self):
        """An empty command should not crash.

        See https://github.com/The-Compiler/qutebrowser/issues/1690
        """
        cr = runners.CommandRunner(0)
        with pytest.raises(cmdexc.NoSuchCommandError):
            list(cr.parse_all(''))

    def test_parse_with_count(self):
        """Test parsing of commands with a count."""
        cr = runners.CommandRunner(0)
        result = cr.parse('20:scroll down')
        assert result.cmd.name == 'scroll'
        assert result.count == 20
        assert result.args == ['down']
        assert result.cmdline == ['scroll', 'down']

    def test_partial_parsing(self):
        """Test partial parsing with a runner where it's enabled.

        The same with it being disabled is tested by test_parse_all.
        """
        cr = runners.CommandRunner(0, partial_match=True)
        result = cr.parse('message-i')
        assert result.cmd.name == 'message-info'
