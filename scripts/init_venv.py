#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Initialize a virtualenv suitable to be used for qutebrowser."""

import os
import sys
import glob
import os.path
import shutil
import argparse
import subprocess
import distutils.sysconfig

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))
from scripts import utils


g_path = None
g_args = None


def parse_args():
    """Parse the commandline arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', help="Force creating a new virtualenv.",
                        action='store_true')
    parser.add_argument('--dev', help="Set up an environment suitable for "
                                      "developing qutebrowser.",
                        action='store_true')
    parser.add_argument('path', help="Path to the virtualenv folder",
                        default='.venv', nargs='?')
    return parser.parse_args()


def check_exists():
    """Check if the virtualenv already exists."""
    if os.path.exists(g_path):
        if g_args.force:
            print("Deleting old virtualenv at {}".format(g_path))
            shutil.rmtree(g_path)
        else:
            print("virtualenv at {} does already exist!".format(g_path),
                  file=sys.stderr)
            sys.exit(1)


def install_dev_packages():
    """Install the packages needed for development."""
    packages = ['colorlog', 'flake8', 'pylint==1.3.1', 'pep257']
    if os.name == 'nt':
        packages += ['colorama']
    for pkg in packages:
        utils.print_subtitle("Installing {}".format(pkg))
        venv_python('-m', 'pip', 'install', pkg)


def venv_python(*args, output=False):
    """Call the virtualenv's python with the given arguments."""
    executable = os.path.join(g_path, 'bin', os.path.basename(sys.executable))
    if output:
        return subprocess.check_output([executable] + list(args),
                                       universal_newlines=True)
    else:
        subprocess.check_call([executable] + list(args))


def test_toolchain():
    """Test if imports work properly."""
    utils.print_title("Checking toolchain")
    packages = ['sip', 'PyQt5.QtCore', 'PyQt5.QtWebKit', 'qutebrowser.app']
    if g_args.dev:
        packages.append('pylint')
    for pkg in packages:
        print("Importing {}".format(pkg))
        venv_python('-c', 'import {}'.format(pkg))


def link_pyqt():
    """Symlink the systemwide PyQt/sip into the virtualenv."""
    utils.print_title("Softlinking PyQt5")
    sys_path = distutils.sysconfig.get_python_lib()
    venv_path = venv_python(
        '-c', 'from distutils.sysconfig import get_python_lib\n'
              'print(get_python_lib())', output=True).rstrip()
    globbed_sip = glob.glob(os.path.join(sys_path, 'sip*.so'))
    if not globbed_sip:
        print("Did not find sip in {}!".format(sys_path), file=sys.stderr)
        sys.exit(1)
    elif len(globbed_sip) != 1:
        print("Found multiple sip installations: {}!".format(globbed_sip),
              file=sys.stderr)
        sys.exit(1)
    files = (
        'PyQt5',
        os.path.basename(globbed_sip[0]),
    )
    for fn in files:
        source = os.path.join(sys_path, fn)
        link_name = os.path.join(venv_path, fn)
        if not os.path.exists(source):
            raise FileNotFoundError(source)
        print('{} -> {}'.format(source, link_name))
        os.symlink(source, link_name)


def main():
    """Main entry point."""
    global g_path, g_args
    g_args = parse_args()
    if not g_args.path:
        print("Refusing to run with empty path!", file=sys.stderr)
        sys.exit(1)
    g_path = os.path.abspath(g_args.path)
    check_exists()
    utils.print_title("Creating virtualenv")
    subprocess.check_call(['virtualenv', '-p', sys.executable, g_path])
    utils.print_title("Calling setup.py")
    venv_python('setup.py', 'develop')
    if g_args.dev:
        utils.print_title("Installing developer packages")
        install_dev_packages()
    link_pyqt()
    test_toolchain()


if __name__ == '__main__':
    main()
