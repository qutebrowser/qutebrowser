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

"""Tests for qutebrowser.misc.crashdialog."""

import os
import pytest
from qutebrowser.misc import crashdialog


VALID_CRASH_TEXT = """
Fatal Python error: Segmentation fault
_
Current thread 0x00007f09b538d700 (most recent call first):
  File "", line 1 in testfunc
  File "filename", line 88 in func
"""

VALID_CRASH_TEXT_EMPTY = """
Fatal Python error: Aborted
_
Current thread 0x00007f09b538d700 (most recent call first):
  File "", line 1 in_
  File "filename", line 88 in func
"""

VALID_CRASH_TEXT_THREAD = """
Fatal Python error: Segmentation fault
_
Thread 0x00007fa135ac7700 (most recent call first):
  File "", line 1 in testfunc
"""

WINDOWS_CRASH_TEXT = r"""
Windows fatal exception: access violation
_
Current thread 0x000014bc (most recent call first):
  File "qutebrowser\mainwindow\tabbedbrowser.py", line 468 in tabopen
  File "qutebrowser\browser\shared.py", line 247 in get_tab
"""

INVALID_CRASH_TEXT = """
Hello world!
"""


@pytest.mark.parametrize('text, typ, func', [
    (VALID_CRASH_TEXT, 'Segmentation fault', 'testfunc'),
    (VALID_CRASH_TEXT_THREAD, 'Segmentation fault', 'testfunc'),
    (VALID_CRASH_TEXT_EMPTY, 'Aborted', ''),
    (WINDOWS_CRASH_TEXT, 'Windows access violation', 'tabopen'),
    (INVALID_CRASH_TEXT, '', ''),
])
def test_parse_fatal_stacktrace(text, typ, func):
    text = text.strip().replace('_', ' ')
    assert crashdialog.parse_fatal_stacktrace(text) == (typ, func)


@pytest.mark.parametrize('env, expected', [
    ({'FOO': 'bar'}, ""),
    ({'FOO': 'bar', 'LC_ALL': 'baz'}, "LC_ALL = baz"),
    ({'LC_ALL': 'baz', 'PYTHONFOO': 'fish'}, "LC_ALL = baz\nPYTHONFOO = fish"),
    (
        {'DE': 'KDE', 'DESKTOP_SESSION': 'plasma'},
        "DE = KDE\nDESKTOP_SESSION = plasma"
    ),
    (
        {'QT5_IM_MODULE': 'fcitx', 'QT_IM_MODULE': 'fcitx'},
        "QT_IM_MODULE = fcitx"
    ),
    ({'LANGUAGE': 'foo', 'LANG': 'en_US.UTF-8'}, "LANG = en_US.UTF-8"),
    ({'FOO': 'bar', 'QUTE_BLAH': '1'}, "QUTE_BLAH = 1"),
])
def test_get_environment_vars(monkeypatch, env, expected):
    """Test for crashdialog._get_environment_vars."""
    for key in os.environ.copy():
        monkeypatch.delenv(key)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert crashdialog._get_environment_vars() == expected
