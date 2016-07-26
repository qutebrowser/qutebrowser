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

"""Test which simply runs qutebrowser to check if it starts properly."""

import sys
import os.path
import subprocess
import signal

import pytest

@pytest.mark.parametrize('cmd', [':quit', ':later 500 quit'])
def test_smoke(cmd, capfd):
    if hasattr(sys, 'frozen'):
        argv = [os.path.join(os.path.dirname(sys.executable), 'qutebrowser')]
    else:
        argv = [sys.executable, '-m', 'qutebrowser']
    argv += ['--debug', '--no-err-windows', '--temp-basedir', 'about:blank',
             cmd]
    try:
        subprocess.check_call(argv)
    except subprocess.CalledProcessError as e:
        if e.returncode == -signal.SIGSEGV:
            _out, err = capfd.readouterr()
            assert 'Uncaught exception' not in err
            # pylint: disable=no-member
            # https://github.com/The-Compiler/qutebrowser/issues/1387
            pytest.xfail("Ignoring segfault on exit...")
        else:
            raise


def test_smoke_quteproc(quteproc):
    pass
