# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.commands.cmdexc."""

import re
import pytest

from qutebrowser.commands import cmdexc


def test_empty_command_error():
    with pytest.raises(cmdexc.NoSuchCommandError, match="No command given"):
        raise cmdexc.EmptyCommandError


@pytest.mark.parametrize("all_commands, msg", [
    ([], "testcmd: no such command"),
    (["fastcmd"], "testcmd: no such command (did you mean :fastcmd?)"),
    (["thisdoesnotmatch"], "testcmd: no such command"),
])
def test_no_such_command_error(all_commands, msg):
    with pytest.raises(cmdexc.NoSuchCommandError, match=re.escape(msg)):
        raise cmdexc.NoSuchCommandError.for_cmd("testcmd", all_commands=all_commands)
