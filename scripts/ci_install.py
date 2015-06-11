#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Install needed prerequisites on the AppVeyor CI."""

import subprocess
import urllib.request

PYQT_VERSION = '5.4.1'

print("Getting PyQt5...")
urllib.request.urlretrieve(
    ('http://sourceforge.net/projects/pyqt/files/PyQt5/PyQt-{v}/'
     'PyQt5-{v}-gpl-Py3.4-Qt{v}-x32.exe'.format(v=PYQT_VERSION)),
    r'C:\install-PyQt5.exe')

print("Installing PyQt5...")
subprocess.check_call([r'C:\install-PyQt5.exe', '/S'])

print("Installing tox...")
subprocess.check_call([r'C:\Python34\Scripts\pip', 'install', 'tox'])

print("Linking Python...")
with open(r'C:\Windows\system32\python3.bat', 'w', encoding='ascii') as f:
    f.write(r'@C:\Python34\python %*')
