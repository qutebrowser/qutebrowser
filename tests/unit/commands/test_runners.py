# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from qutebrowser.misc import objects
from qutebrowser.commands import runners, cmdexc


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

    def test_parse_all_with_alias(self, cmdline_test, monkeypatch,
                                  config_stub):
        if not cmdline_test.cmd:
            pytest.skip("Empty command")

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


class TestCompletions:

    """Tests for completions.use_best_match."""

    @pytest.fixture(autouse=True)
    def cmdutils_stub(self, monkeypatch, stubs):
        """Patch the cmdutils module to provide fake commands."""
        monkeypatch.setattr(objects, 'commands', {
            'one': stubs.FakeCommand(name='one'),
            'two': stubs.FakeCommand(name='two'),
            'two-foo': stubs.FakeCommand(name='two-foo'),
        })

    def test_partial_parsing(self, config_stub):
        """Test partial parsing with a runner where it's enabled.

        The same with it being disabled is tested by test_parse_all.
        """
        parser = runners.CommandParser(partial_match=True)
        result = parser.parse('on')
        assert result.cmd.name == 'one'

    def test_dont_use_best_match(self, config_stub):
        """Test multiple completion options with use_best_match set to false.

        Should raise NoSuchCommandError
        """
        config_stub.val.completion.use_best_match = False
        parser = runners.CommandParser(partial_match=True)

        with pytest.raises(cmdexc.NoSuchCommandError):
            parser.parse('tw')

    def test_use_best_match(self, config_stub):
        """Test multiple completion options with use_best_match set to true.

        The resulting command should be the best match
        """
        config_stub.val.completion.use_best_match = True
        parser = runners.CommandParser(partial_match=True)

        result = parser.parse('tw')
        assert result.cmd.name == 'two'
