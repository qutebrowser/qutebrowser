# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for qutebrowser.commands.parser."""

import pytest

from qutebrowser.misc import objects
from qutebrowser.commands import parser, cmdexc


class TestCommandParser:

    def test_parse_all(self, cmdline_test):
        """Test parsing of commands.

        See https://github.com/qutebrowser/qutebrowser/issues/615

        Args:
            cmdline_test: A pytest fixture which provides testcases.
        """
        p = parser.CommandParser()
        if cmdline_test.valid:
            p.parse_all(cmdline_test.cmd, aliases=False)
        else:
            with pytest.raises(cmdexc.NoSuchCommandError):
                p.parse_all(cmdline_test.cmd, aliases=False)

    def test_parse_all_with_alias(self, cmdline_test, monkeypatch,
                                  config_stub):
        if not cmdline_test.cmd:
            pytest.skip("Empty command")

        config_stub.val.aliases = {'alias_name': cmdline_test.cmd}

        p = parser.CommandParser()
        if cmdline_test.valid:
            assert len(p.parse_all("alias_name")) > 0
        else:
            with pytest.raises(cmdexc.NoSuchCommandError):
                p.parse_all("alias_name")

    @pytest.mark.parametrize('command', ['', ' '])
    def test_parse_empty_with_alias(self, command):
        """An empty command should not crash.

        See https://github.com/qutebrowser/qutebrowser/issues/1690
        and https://github.com/qutebrowser/qutebrowser/issues/1773
        """
        p = parser.CommandParser()
        with pytest.raises(cmdexc.NoSuchCommandError):
            p.parse_all(command)

    @pytest.mark.parametrize('command, name, args', [
        ("set-cmd-text -s :open", "set-cmd-text", ["-s", ":open"]),
        ("set-cmd-text :open {url:pretty}", "set-cmd-text",
         [":open {url:pretty}"]),
        ("set-cmd-text -s :open -t", "set-cmd-text", ["-s", ":open -t"]),
        ("set-cmd-text :open -t -r {url:pretty}", "set-cmd-text",
         [":open -t -r {url:pretty}"]),
        ("set-cmd-text -s :open -b", "set-cmd-text", ["-s", ":open -b"]),
        ("set-cmd-text :open -b -r {url:pretty}", "set-cmd-text",
         [":open -b -r {url:pretty}"]),
        ("set-cmd-text -s :open -w", "set-cmd-text",
         ["-s", ":open -w"]),
        ("set-cmd-text :open -w {url:pretty}", "set-cmd-text",
         [":open -w {url:pretty}"]),
        ("set-cmd-text /", "set-cmd-text", ["/"]),
        ("set-cmd-text ?", "set-cmd-text", ["?"]),
        ("set-cmd-text :", "set-cmd-text", [":"]),
    ])
    def test_parse_result(self, config_stub, command, name, args):
        p = parser.CommandParser()
        result = p.parse_all(command)[0]
        assert result.cmd.name == name
        assert result.args == args


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
        p = parser.CommandParser(partial_match=True)
        result = p.parse('on')
        assert result.cmd.name == 'one'

    def test_dont_use_best_match(self, config_stub):
        """Test multiple completion options with use_best_match set to false.

        Should raise NoSuchCommandError
        """
        config_stub.val.completion.use_best_match = False
        p = parser.CommandParser(partial_match=True)

        with pytest.raises(cmdexc.NoSuchCommandError):
            p.parse('tw')

    def test_use_best_match(self, config_stub):
        """Test multiple completion options with use_best_match set to true.

        The resulting command should be the best match
        """
        config_stub.val.completion.use_best_match = True
        p = parser.CommandParser(partial_match=True)

        result = p.parse('tw')
        assert result.cmd.name == 'two'
