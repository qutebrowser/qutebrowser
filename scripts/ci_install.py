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

PYQT_VERSION = '5.4.2'


def apt_get(args):
    subprocess.check_call(['sudo', 'apt-get', '-y', '-q'] + args)


def brew(args, silent=False):
    if silent:
        with open(os.devnull, 'w') as f:
            subprocess.check_call(['brew'] + args, stdout=f)
    else:
        subprocess.check_call(['brew'] + args)


if 'APPVEYOR' in os.environ:
    print("Getting PyQt5...")
    urllib.urlretrieve(
        ('http://sourceforge.net/projects/pyqt/files/PyQt5/PyQt-{v}/'
         'PyQt5-{v}-gpl-Py3.4-Qt{v}-x32.exe'.format(v=PYQT_VERSION)),
        r'C:\install-PyQt5.exe')

    print("Installing PyQt5...")
    subprocess.check_call([r'C:\install-PyQt5.exe', '/S'])

    print("Installing tox...")
    subprocess.check_call([r'C:\Python34\Scripts\pip', 'install', 'tox'])

    print("Linking Python...")
    with open(r'C:\Windows\system32\python3.bat', 'w') as f:
        f.write(r'@C:\Python34\python %*')
elif os.environ.get('TRAVIS_OS_NAME', None) == 'linux':
    print("apt-get update...")
    apt_get(['update'])

    print("Installing packages...")
    pkgs = 'python3-pyqt5 python3-pyqt5.qtwebkit python-tox python3-dev xvfb'
    apt_get(['install'] + pkgs.split())
elif os.environ.get('TRAVIS_OS_NAME', None) == 'osx':
    print("brew update...")
    brew(['update'], silent=True)

    print("Installing packages...")
    brew(['install', 'python3', 'pyqt5'])

    print("Installing tox...")
    subprocess.check_call(['sudo', 'pip3.4', 'install', 'tox'])

    os.system('ls -l /usr/local/bin/xvfb-run')
    print("Creating xvfb-run stub...")
    with open('/usr/local/bin/xvfb-run', 'w') as f:
        # This will break when xvfb-run is called differently in .travis.yml,
        # but I can't be bothered to do it in a nicer way.
        f.write('#!/bin/bash\n')
        f.write('shift 2\n')
        f.write('exec "$@"\n')
    os.system('sudo chmod 755 /usr/local/bin/xvfb-run')
    os.system('ls -l /usr/local/bin/xvfb-run')
else:
    def env(key):
        return os.environ.get(key, None)
    print("Unknown environment! (CI {}, APPVEYOR {}, TRAVIS {}, "
          "TRAVIS_OS_NAME {})".format(env('CI'), env('APPVEYOR'),
                                      env('TRAVIS'), env('TRAVIS_OS_NAME')),
          file=sys.stderr)
    sys.exit(1)
