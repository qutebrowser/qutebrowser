#!/usr/bin/env python3
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

"""cx_Freeze script to freeze qutebrowser and its tests."""


import os
import os.path
import sys
import contextlib

import cx_Freeze as cx  # pylint: disable=import-error,useless-suppression
# cx_Freeze is hard to install (needs C extensions) so we don't check for it.
import pytest

import httpbin

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                                os.pardir))
from scripts import setupcommon
from scripts.dev import freeze


@contextlib.contextmanager
def temp_git_commit_file():
    """Context manager to temporarily create a fake git-commit-id file."""
    basedir = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                           os.path.pardir, os.pardir)
    path = os.path.join(basedir, 'qutebrowser', 'git-commit-id')
    with open(path, 'wb') as f:
        f.write(b'fake-frozen-git-commit')
    yield
    os.remove(path)


def get_build_exe_options():
    """Get build_exe options with additional includes."""
    opts = freeze.get_build_exe_options(skip_html=True)
    opts['includes'] += pytest.freeze_includes()  # pylint: disable=no-member
    opts['includes'] += ['unittest.mock', 'PyQt5.QtTest', 'hypothesis', 'bs4',
                         'httpbin', 'jinja2.ext', 'cherrypy.wsgiserver',
                         'pstats']

    httpbin_dir = os.path.dirname(httpbin.__file__)
    opts['include_files'] += [
        ('tests/end2end/data', 'end2end/data'),
        (os.path.join(httpbin_dir, 'templates'), 'end2end/templates'),
    ]

    opts['packages'].append('qutebrowser')
    return opts


def main():
    base = 'Win32GUI' if sys.platform.startswith('win') else None
    with temp_git_commit_file():
        cx.setup(
            executables=[
                cx.Executable('scripts/dev/run_frozen_tests.py',
                              targetName='run-frozen-tests'),
                cx.Executable('tests/end2end/fixtures/webserver_sub.py',
                              targetName='webserver_sub'),
                freeze.get_exe(base, target_name='qutebrowser')
            ],
            options={'build_exe': get_build_exe_options()},
            **setupcommon.setupdata
        )


if __name__ == '__main__':
    main()
