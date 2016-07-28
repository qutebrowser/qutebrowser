#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Wrapper around pytest to ignore segfaults on exit."""

import os
import sys
import subprocess
import signal


if __name__ == '__main__':
    script_path = os.path.abspath(os.path.dirname(__file__))
    pytest_status_file = os.path.join(script_path, '..', '..', '.cache',
                                      'pytest_status')

    try:
        os.remove(pytest_status_file)
    except FileNotFoundError:
        pass

    try:
        subprocess.check_call([sys.executable, '-m', 'pytest'] + sys.argv[1:])
    except subprocess.CalledProcessError as exc:
        is_segfault = exc.returncode in [128 + signal.SIGSEGV, -signal.SIGSEGV]
        if is_segfault and os.path.exists(pytest_status_file):
            print("Ignoring segfault on exit!")
            with open(pytest_status_file, 'r', encoding='ascii') as f:
                exit_status = int(f.read())
        else:
            exit_status = exc.returncode
    else:
        exit_status = 0

    try:
        os.remove(pytest_status_file)
    except FileNotFoundError:
        pass

    sys.exit(exit_status)
