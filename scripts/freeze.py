#!/usr/bin/python
# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""cx_Freeze script for qutebrowser.

Builds a standalone executable.
"""


import platform

from cx_Freeze import setup, Executable

from scripts.setupdata import setupdata


def get_egl_path():
    """Get the path for PyQt5's libEGL.dll."""
    bits = platform.architecture()[0]
    if bits == '32bit':
        return r'C:\Python33_x32\Lib\site-packages\PyQt5\libEGL.dll'
    elif bits == '64bit':
        return r'C:\Python33\Lib\site-packages\PyQt5\libEGL.dll'
    else:
        raise ValueError("Unknown architecture")


setup(
    executables = [Executable('qutebrowser/__main__.py', base='Win32GUI',
                              targetName='qutebrowser.exe')],
    options = {
        'build_exe': {
            'include_files': [
                (get_egl_path(), 'libEGL.dll'),
                ('qutebrowser/html', 'html'),
            ],
            'include_msvcr': True,
        }
    },
    **setupdata
)
