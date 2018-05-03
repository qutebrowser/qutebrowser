#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Generate file_version_info.txt for Pyinstaller use with Windows builds."""

import os.path
import sys

from PyInstaller.utils.win32 import versioninfo as vs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                                os.pardir))

import qutebrowser

out_filename = 'misc/file_version_info.txt'

filevers = qutebrowser.__version_info__ + (0,)
prodvers = qutebrowser.__version_info__ + (0,)
str_filevers = qutebrowser.__version__
str_prodvers = qutebrowser.__version__

comment_text = """\
A keyboard-focused browser with a minimal GUI.\
"""
copyright_text = """\
© 2014-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>\
"""
trademark_text = """\
qutebrowser is free software under the GNU General Public License\
"""

ffi = vs.FixedFileInfo(filevers, prodvers)

kids = [vs.StringFileInfo(
    [vs.StringTable('040904B0',
                    [vs.StringStruct('Comments', f'{comment_text}'),
                     vs.StringStruct('CompanyName', "qutebrowser.org"),
                     vs.StringStruct('FileDescription', "qutebrowser"),
                     vs.StringStruct('FileVersion', f'{str_filevers}'),
                     vs.StringStruct('InternalName', "qutebrowser"),
                     vs.StringStruct('LegalCopyright', f'{copyright_text}'),
                     vs.StringStruct('LegalTrademarks', f'{trademark_text}'),
                     vs.StringStruct('OriginalFilename', "qutebrowser.exe"),
                     vs.StringStruct('ProductName', "qutebrowser"),
                     vs.StringStruct('ProductVersion', f'{str_prodvers}')])]),
    vs.VarFileInfo([vs.VarStruct('Translation', [1033, 1200])])]

file_version_info = vs.VSVersionInfo(ffi, kids)

with open(out_filename, 'w', encoding='utf-8') as f:
    f.write(f'{file_version_info}')

f.close()
