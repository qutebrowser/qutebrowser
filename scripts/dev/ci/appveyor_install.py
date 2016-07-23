#!/usr/bin/env python2
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

# pylint: skip-file

"""Install needed prerequisites on the AppVeyor.

Note this file is written in python2 as this is more readily available on the
CI machines.
"""

from __future__ import print_function

import subprocess
import urllib


def check_setup(executable):
    subprocess.check_call([executable, '-c', 'import PyQt5'])
    subprocess.check_call([executable, '-c', 'import sip'])
    subprocess.check_call([executable, '--version'])


def pip_install(pkg):
    subprocess.check_call([r'C:\Python34\python', '-m', 'pip', 'install', '-U',
                           pkg])


print("Getting PyQt5...")
qt_version = '5.5.1'
pyqt_version = '5.5.1'
pyqt_url = ('http://www.qutebrowser.org/pyqt/'
            'PyQt5-{}-gpl-Py3.4-Qt{}-x32.exe'.format(
                pyqt_version, qt_version))
urllib.urlretrieve(pyqt_url, r'C:\install-PyQt5.exe')

print("Installing PyQt5...")
subprocess.check_call([r'C:\install-PyQt5.exe', '/S'])

print("Installing pip/tox")
pip_install(r'-rmisc\requirements\requirements-pip.txt')
pip_install(r'-rmisc\requirements\requirements-tox.txt')

print("Linking Python...")
with open(r'C:\Windows\system32\python3.bat', 'w') as f:
    f.write(r'@C:\Python34\python %*')

check_setup(r'C:\Python34\python')
