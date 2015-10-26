#!/usr/bin/env python2
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

# pylint: skip-file

"""Install needed prerequisites on the AppVeyor/Travis CI.

Note this file is written in python2 as this is more readily available on the
CI machines.
"""

from __future__ import print_function

import os
import sys
import subprocess
import urllib

try:
    import _winreg as winreg
except ImportError:
    winreg = None

TESTENV = os.environ['TESTENV']
TRAVIS_OS = os.environ.get('TRAVIS_OS_NAME', None)
INSTALL_PYQT = TESTENV in ('py34', 'py35', 'unittests-nodisp', 'vulture',
                           'pylint')
XVFB = TRAVIS_OS == 'linux' and TESTENV == 'py34'
pip_packages = ['tox']
if TESTENV in ['py34', 'py35']:
    pip_packages.append('codecov')



def apt_get(args):
    subprocess.check_call(['sudo', 'apt-get', '-y', '-q'] + args)


def brew(args, silent=False):
    if silent:
        with open(os.devnull, 'w') as f:
            subprocess.check_call(['brew'] + args, stdout=f)
    else:
        subprocess.check_call(['brew'] + args + ['--verbose'])


def check_setup(executable):
    if INSTALL_PYQT:
        print("Checking setup...")
        subprocess.check_call([executable, '-c', 'import PyQt5'])
        subprocess.check_call([executable, '-c', 'import sip'])


if 'APPVEYOR' in os.environ:
    print("Getting PyQt5...")
    urllib.urlretrieve(
        'http://www.qutebrowser.org/pyqt/PyQt5-5.5-gpl-Py3.4-Qt5.5.0-x32.exe',
        r'C:\install-PyQt5.exe')

    print("Fixing registry...")
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                        r'Software\Python\PythonCore\3.4', 0,
                        winreg.KEY_WRITE) as key:
        winreg.SetValue(key, 'InstallPath', winreg.REG_SZ, r'C:\Python34')

    print("Installing PyQt5...")
    subprocess.check_call([r'C:\install-PyQt5.exe', '/S'])

    print("Installing tox...")
    subprocess.check_call([r'C:\Python34\Scripts\pip', 'install'] +
                          pip_packages)

    print("Linking Python...")
    with open(r'C:\Windows\system32\python3.bat', 'w') as f:
        f.write(r'@C:\Python34\python %*')

    check_setup(r'C:\Python34\python')
elif TRAVIS_OS == 'linux':
    print("travis_fold:start:ci_install")
    print("Installing via pip...")
    subprocess.check_call(['sudo', 'pip', 'install'] + pip_packages)

    print("Installing packages...")
    pkgs = []

    if XVFB:
        pkgs.append('xvfb')
    if INSTALL_PYQT:
        pkgs += ['python3-pyqt5', 'python3-pyqt5.qtwebkit']
    if TESTENV == 'eslint':
        pkgs += ['npm', 'nodejs', 'nodejs-legacy']

    if pkgs:
        print("apt-get update...")
        apt_get(['update'])
        print("apt-get install...")
        apt_get(['install'] + pkgs)

    if TESTENV == 'eslint':
        subprocess.check_call(['sudo', 'npm', 'install', '-g', 'eslint'])
    else:
        check_setup('python3')
    print("travis_fold:end:ci_install")
elif TRAVIS_OS == 'osx':
    print("brew update...")
    brew(['update'], silent=True)

    print("Installing packages...")
    pkgs = ['python3']
    if INSTALL_PYQT:
        pkgs.append('pyqt5')
    brew(['install'] + pkgs)

    print("Installing tox/codecov...")
    subprocess.check_call(['sudo', 'pip3', 'install'] + pip_packages)

    check_setup('python3')
else:
    def env(key):
        return os.environ.get(key, None)
    print("Unknown environment! (CI {}, APPVEYOR {}, TRAVIS {}, "
          "TRAVIS_OS_NAME {})".format(env('CI'), env('APPVEYOR'),
                                      env('TRAVIS'), env('TRAVIS_OS_NAME')),
          file=sys.stderr)
    sys.exit(1)
