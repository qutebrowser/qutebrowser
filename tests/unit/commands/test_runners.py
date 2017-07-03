# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
from qutebrowser.config import configtypes


class TestCommandParser:

    def test_parse_all(self, cmdline_test):
        """Test parsing of commands.

        See https://github.com/qutebrowser/qutebrowser/issues/615

        Args:
            cmdline_test: A pytest fixture which provides testcases.
        """
        parser = runners.CommandParser()
        if cmdline_test.valid:
            parser.parse_all(cmdline_test.cmd, aliases=False)
        else:
            with pytest.raises(cmdexc.NoSuchCommandError):
                parser.parse_all(cmdline_test.cmd, aliases=False)

    def test_parse_all_with_alias(self, cmdline_test, monkeypatch, config_stub):
        if not cmdline_test.cmd:
            pytest.skip("Empty command")

        monkeypatch.setattr(configtypes.Command, 'unvalidated', True)
        config_stub.val.aliases = {'alias_name': cmdline_test.cmd}

        parser = runners.CommandParser()
        if cmdline_test.valid:
            assert len(parser.parse_all("alias_name")) > 0
        else:
            with pytest.raises(cmdexc.NoSuchCommandError):
                parser.parse_all("alias_name")

    @pytest.mark.parametrize('command', ['', ' '])
    def test_parse_empty_with_alias(self, command):
        """An empty command should not crash.

        See https://github.com/qutebrowser/qutebrowser/issues/1690
        and https://github.com/qutebrowser/qutebrowser/issues/1773
        """
        parser = runners.CommandParser()
        with pytest.raises(cmdexc.NoSuchCommandError):
            parser.parse_all(command)

    def test_partial_parsing(self):
        """Test partial parsing with a runner where it's enabled.

        The same with it being disabled is tested by test_parse_all.
        """
        parser = runners.CommandParser(partial_match=True)
        result = parser.parse('message-i')
        assert result.cmd.name == 'message-info'
