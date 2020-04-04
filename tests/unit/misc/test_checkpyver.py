# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

"""Tests for qutebrowser.misc.checkpyver."""

import re
import sys
import subprocess
import unittest.mock

import pytest

from qutebrowser.misc import checkpyver


TEXT = (r"At least Python 3.5.2 is required to run qutebrowser, but it's "
        r"running with \d+\.\d+\.\d+.\n")


@pytest.mark.not_frozen
def test_python2():
    """Run checkpyver with python 2."""
    try:
        proc = subprocess.run(
            ['python2', checkpyver.__file__, '--no-err-windows'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False)
    except FileNotFoundError:
        pytest.skip("python2 not found")
    assert not proc.stdout
    stderr = proc.stderr.decode('utf-8')
    assert re.fullmatch(TEXT, stderr), stderr
    assert proc.returncode == 1


def test_normal(capfd):
    checkpyver.check_python_version()
    out, err = capfd.readouterr()
    assert not out
    assert not err


def test_patched_no_errwindow(capfd, monkeypatch):
    """Test with a patched sys.hexversion and --no-err-windows."""
    monkeypatch.setattr(checkpyver.sys, 'argv',
                        [sys.argv[0], '--no-err-windows'])
    monkeypatch.setattr(checkpyver.sys, 'hexversion', 0x03040000)
    monkeypatch.setattr(checkpyver.sys, 'exit', lambda status: None)
    checkpyver.check_python_version()
    stdout, stderr = capfd.readouterr()
    assert not stdout
    assert re.fullmatch(TEXT, stderr), stderr


def test_patched_errwindow(capfd, mocker, monkeypatch):
    """Test with a patched sys.hexversion and a fake Tk."""
    monkeypatch.setattr(checkpyver.sys, 'hexversion', 0x03040000)
    monkeypatch.setattr(checkpyver.sys, 'exit', lambda status: None)

    try:
        import tkinter  # pylint: disable=unused-import
    except ImportError:
        tk_mock = mocker.patch('qutebrowser.misc.checkpyver.Tk',
                               spec=['withdraw'], new_callable=mocker.Mock)
        msgbox_mock = mocker.patch('qutebrowser.misc.checkpyver.messagebox',
                                   spec=['showerror'])
    else:
        tk_mock = mocker.patch('qutebrowser.misc.checkpyver.Tk', autospec=True)
        msgbox_mock = mocker.patch('qutebrowser.misc.checkpyver.messagebox',
                                   autospec=True)

    checkpyver.check_python_version()
    stdout, stderr = capfd.readouterr()
    assert not stdout
    assert not stderr
    tk_mock.assert_called_with()
    tk_mock().withdraw.assert_called_with()
    msgbox_mock.showerror.assert_called_with("qutebrowser: Fatal error!",
                                             unittest.mock.ANY)
