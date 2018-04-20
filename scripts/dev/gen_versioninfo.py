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

import os
import os.path
import sys

from PyInstaller.utils.win32 import versioninfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                                os.pardir))

import qutebrowser


out_filename = 'file_version_info.txt'

FileVersion = qutebrowser.__version_info__ + (0,)
ProductVersion = qutebrowser.__version_info__ + (0,)

CommentText = "A keyboard-focused browser with a minimal GUI."
CopyrightText = "© 2014-2018 Florian Bruhin (The Compiler) \
<mail@qutebrowser.org>"
TrademarkText = "qutebrowser is free software under the GNU General Public \
License"

FixedFileInfo = versioninfo.FixedFileInfo(FileVersion, ProductVersion)

StringFileInfo = [versioninfo.StringFileInfo(             
    [versioninfo.StringTable('040904B0',
    [versioninfo.StringStruct('Comments',f'{CommentText}'),
    versioninfo.StringStruct('CompanyName',"qutebrowser.org"),
    versioninfo.StringStruct('FileDescription',"qutebrowser"),
    versioninfo.StringStruct('FileVersion',f'{qutebrowser.__version__}'),
    versioninfo.StringStruct('InternalName',"qutebrowser"),
    versioninfo.StringStruct('LegalCopyright',f'{CopyrightText}'),
    versioninfo.StringStruct('LegalTrademarks',f'{TrademarkText}'),
    versioninfo.StringStruct('OriginalFilename',"qutebrowser.exe"),
    versioninfo.StringStruct('ProductName',"qutebrowser"),
    versioninfo.StringStruct('ProductVersion',f'{qutebrowser.__version__}')])]),
    versioninfo.VarFileInfo([versioninfo.VarStruct('Translation',
                            [1033, 1200])])]

VSVersionInfo = versioninfo.VSVersionInfo(FixedFileInfo, StringFileInfo)

with open(out_filename, 'w', encoding='utf-8') as f:
    f.write(f'{VSVersionInfo}')

f.close()
