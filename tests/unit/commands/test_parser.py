# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.commands.parser."""

import re

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
        with pytest.raises(cmdexc.EmptyCommandError):
            p.parse_all(command)

    @pytest.mark.parametrize('command, name, args', [
        ("cmd-set-text -s :open", "cmd-set-text", ["-s", ":open"]),
        ("cmd-set-text :open {url:pretty}", "cmd-set-text",
         [":open {url:pretty}"]),
        ("cmd-set-text -s :open -t", "cmd-set-text", ["-s", ":open -t"]),
        ("cmd-set-text :open -t -r {url:pretty}", "cmd-set-text",
         [":open -t -r {url:pretty}"]),
        ("cmd-set-text -s :open -b", "cmd-set-text", ["-s", ":open -b"]),
        ("cmd-set-text :open -b -r {url:pretty}", "cmd-set-text",
         [":open -b -r {url:pretty}"]),
        ("cmd-set-text -s :open -w", "cmd-set-text",
         ["-s", ":open -w"]),
        ("cmd-set-text :open -w {url:pretty}", "cmd-set-text",
         [":open -w {url:pretty}"]),
        ("cmd-set-text /", "cmd-set-text", ["/"]),
        ("cmd-set-text ?", "cmd-set-text", ["?"]),
        ("cmd-set-text :", "cmd-set-text", [":"]),
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


@pytest.mark.parametrize("find_similar, msg", [
    (True, "tabfocus: no such command (did you mean :tab-focus?)"),
    (False, "tabfocus: no such command"),
])
def test_find_similar(find_similar, msg):
    p = parser.CommandParser(find_similar=find_similar)
    with pytest.raises(cmdexc.NoSuchCommandError, match=re.escape(msg)):
        p.parse_all("tabfocus", aliases=False)
