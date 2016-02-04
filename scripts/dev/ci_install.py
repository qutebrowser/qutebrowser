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

"""Install needed prerequisites on the AppVeyor/Travis CI.

Note this file is written in python2 as this is more readily available on the
CI machines.
"""

from __future__ import print_function

import os
import re
import sys
import subprocess
import urllib
import contextlib

try:
    import _winreg as winreg
except ImportError:
    winreg = None

TESTENV = os.environ['TESTENV']
TRAVIS_OS = os.environ.get('TRAVIS_OS_NAME', None)
INSTALL_PYQT = TESTENV in ('py34', 'py35', 'py34-cov', 'py35-cov',
                           'unittests-nodisp', 'vulture', 'pylint')
XVFB = TRAVIS_OS == 'linux' and TESTENV == 'py34'
pip_packages = ['tox']
if TESTENV.endswith('-cov'):
    pip_packages.append('codecov')


@contextlib.contextmanager
def travis_fold(text):
    if 'TRAVIS' in os.environ:
        marker = re.compile(r'\W+').sub('-', text.lower()).strip('-')
        print("travis_fold:start:{}".format(marker))
        yield
        print("travis_fold:end:{}".format(marker))
    else:
        yield


def folded_cmd(argv):
    """Output a command with travis folding markers."""
    with travis_fold(''.join(argv)):
        print("  $ " + ' '.join(argv))
        subprocess.check_call(argv)


def fix_sources_list():
    """The mirror used by Travis has trouble a lot, so switch to another."""
    subprocess.check_call(['sudo', 'sed', '-i', r's/us-central1\.gce/us/',
                           '/etc/apt/sources.list'])


def apt_get(args):
    folded_cmd(['sudo', 'apt-get', '-y', '-q'] + args)


def brew(args):
    folded_cmd(['brew'] + args)


def check_setup(executable):
    if INSTALL_PYQT:
        print("Checking setup...")
        subprocess.check_call([executable, '-c', 'import PyQt5'])
        subprocess.check_call([executable, '-c', 'import sip'])
    subprocess.check_call([executable, '--version'])


if 'APPVEYOR' in os.environ:
    print("Getting PyQt5...")
    qt_version = '5.5.1'
    pyqt_version = '5.5.1'
    pyqt_url = ('http://www.qutebrowser.org/pyqt/'
                'PyQt5-{}-gpl-Py3.4-Qt{}-x32.exe'.format(
                    pyqt_version, qt_version))
    urllib.urlretrieve(pyqt_url, r'C:\install-PyQt5.exe')

    print("Fixing registry...")
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                        r'Software\Python\PythonCore\3.4', 0,
                        winreg.KEY_WRITE) as key:
        winreg.SetValue(key, 'InstallPath', winreg.REG_SZ, r'C:\Python34')

    print("Installing PyQt5...")
    subprocess.check_call([r'C:\install-PyQt5.exe', '/S'])

    folded_cmd([r'C:\Python34\Scripts\pip', 'install', '-U'] + pip_packages)

    print("Linking Python...")
    with open(r'C:\Windows\system32\python3.bat', 'w') as f:
        f.write(r'@C:\Python34\python %*')

    check_setup(r'C:\Python34\python')
elif TRAVIS_OS == 'linux':
    folded_cmd(['sudo', 'pip', 'install'] + pip_packages)

    pkgs = []

    if XVFB:
        pkgs.append('xvfb')
    if INSTALL_PYQT:
        pkgs += ['python3-pyqt5', 'python3-pyqt5.qtwebkit']
    if TESTENV == 'eslint':
        pkgs += ['npm', 'nodejs', 'nodejs-legacy']

    if pkgs:
        fix_sources_list()
        apt_get(['update'])
        apt_get(['install'] + pkgs)

    if TESTENV == 'flake8':
        fix_sources_list()
        apt_get(['update'])
        # We need an up-to-date Python because of:
        # https://github.com/google/yapf/issues/46
        apt_get(['install', '-t', 'trusty-updates', 'python3.4'])

    if TESTENV == 'eslint':
        folded_cmd(['sudo', 'npm', 'install', '-g', 'eslint'])
    else:
        check_setup('python3')
elif TRAVIS_OS == 'osx':
    print("Disabling App Nap...")
    subprocess.check_call(['defaults', 'write', 'NSGlobalDomain',
                           'NSAppSleepDisabled', '-bool', 'YES'])
    brew(['update'])

    pkgs = ['python3']
    if INSTALL_PYQT:
        pkgs.append('pyqt5')
    brew(['install', '--verbose'] + pkgs)

    folded_cmd(['sudo', 'pip3', 'install'] + pip_packages)

    check_setup('python3')
else:
    def env(key):
        return os.environ.get(key, None)
    print("Unknown environment! (CI {}, APPVEYOR {}, TRAVIS {}, "
          "TRAVIS_OS_NAME {})".format(env('CI'), env('APPVEYOR'),
                                      env('TRAVIS'), env('TRAVIS_OS_NAME')),
          file=sys.stderr)
    sys.exit(1)
