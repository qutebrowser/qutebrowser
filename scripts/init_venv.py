#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Initialize a venv suitable to be used for qutebrowser."""

import os
import re
import sys
import glob
import os.path
import shutil
import argparse
import subprocess
import distutils.sysconfig  # pylint: disable=import-error
# see https://bitbucket.org/logilab/pylint/issue/73/
import venv
import urllib.request
import tempfile

from PyQt5.QtCore import QStandardPaths

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))
from scripts import utils


try:
    import ensurepip  # pylint: disable=import-error
except ImportError:
    # Debian-like systems don't have ensurepip...
    ensurepip = None


g_path = None
g_args = None


def parse_args():
    """Parse the commandline arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--clear', help="Clear venv in case it already "
                        "exists.", action='store_true')
    parser.add_argument('--upgrade', help="Upgrade venv to use this version "
                        "of Python, assuming Python has been upgraded "
                        "in-place.", action='store_true')
    parser.add_argument('--force', help=argparse.SUPPRESS,
                        action='store_true')
    parser.add_argument('--dev', help="Set up an environment suitable for "
                        "developing qutebrowser.",
                        action='store_true')
    parser.add_argument('--cache', help="Cache the clean virtualenv and "
                        "copy it when a new one is requested.",
                        default=False, nargs='?', const='', metavar='NAME')
    parser.add_argument('path', help="Path to the venv folder",
                        default='.venv', nargs='?')
    return parser.parse_args()


def get_dev_packages(short=False):
    """Get a list of packages to install.

    Args:
        short: Remove the version specification.
    """
    packages = ['colorlog', 'flake8', 'astroid', 'pylint', 'pep257',
                'colorama', 'beautifulsoup4']
    if short:
        packages = [re.split(r'[<>=]', p)[0] for p in packages]
    return packages


def install_dev_packages():
    """Install the packages needed for development."""
    for pkg in get_dev_packages():
        utils.print_subtitle("Installing {}".format(pkg))
        venv_python('-m', 'pip', 'install', '--upgrade', pkg)


def venv_python(*args, output=False):
    """Call the venv's python with the given arguments."""
    subdir = 'Scripts' if os.name == 'nt' else 'bin'
    executable = os.path.join(g_path, subdir, 'python')
    env = dict(os.environ)
    if sys.platform == 'darwin' and '__PYVENV_LAUNCHER__' in env:
        # WORKAROUND for https://github.com/pypa/pip/issues/2031
        del env['__PYVENV_LAUNCHER__']
    if output:
        return subprocess.check_output([executable] + list(args),
                                       universal_newlines=True, env=env)
    else:
        subprocess.check_call([executable] + list(args), env=env)


def test_toolchain():
    """Test if imports work properly."""
    utils.print_title("Checking toolchain")

    packages = ['sip', 'PyQt5.QtCore', 'PyQt5.QtWebKit', 'qutebrowser.app']
    if g_args.dev:
        packages += get_dev_packages(short=True)
    for pkg in packages:
        if pkg == 'beautifulsoup4':
            pkg = 'bs4'
        print("Importing {}".format(pkg))
        venv_python('-c', 'import {}'.format(pkg))


def verbose_copy(src, dst, *, follow_symlinks=True):
    """Copy function for shutil.copytree which prints copied files."""
    print('{} -> {}'.format(src, dst))
    shutil.copy(src, dst, follow_symlinks=follow_symlinks)


def get_ignored_files(directory, files):
    """Get the files which should be ignored for link_pyqt() on Windows."""
    needed_exts = ('.py', '.dll', '.pyd', '.so')
    filtered = []
    for f in files:
        ext = os.path.splitext(f)[1]
        full_path = os.path.join(directory, f)
        if (ext not in needed_exts) and os.path.isfile(full_path):
            filtered.append(f)
    return filtered


def link_pyqt():
    """Symlink the systemwide PyQt/sip into the venv."""
    action = "Copying" if os.name == 'nt' else "Softlinking"
    utils.print_title("{} PyQt5".format(action))
    sys_path = distutils.sysconfig.get_python_lib()
    venv_path = venv_python(
        '-c', 'from distutils.sysconfig import get_python_lib\n'
              'print(get_python_lib())', output=True).rstrip()

    globbed_sip = (glob.glob(os.path.join(sys_path, 'sip*.so')) +
                   glob.glob(os.path.join(sys_path, 'sip*.pyd')))
    if not globbed_sip:
        print("Did not find sip in {}!".format(sys_path), file=sys.stderr)
        sys.exit(1)

    files = [
        'PyQt5',
    ]
    files += [os.path.basename(e) for e in globbed_sip]
    for fn in files:
        source = os.path.join(sys_path, fn)
        dest = os.path.join(venv_path, fn)
        if not os.path.exists(source):
            raise FileNotFoundError(source)
        if os.path.exists(dest):
            if os.path.isdir(dest) and not os.path.islink(dest):
                shutil.rmtree(dest)
            else:
                os.unlink(dest)
        if os.name == 'nt':
            if os.path.isdir(source):
                shutil.copytree(source, dest, ignore=get_ignored_files,
                                copy_function=verbose_copy)
            else:
                print('{} -> {}'.format(source, dest))
                shutil.copy(source, dest)
        else:
            print('{} -> {}'.format(source, dest))
            os.symlink(source, dest)


def install_pip():
    """Install pip on Debian-like systems which don't have ensurepip.

    WORKAROUND for https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=772730 and
    https://bugs.launchpad.net/ubuntu/+source/python3.4/+bug/1290847
    """
    utils.print_title("Installing pip/setuptools")
    f = urllib.request.urlopen('https://bootstrap.pypa.io/get-pip.py')
    with tempfile.NamedTemporaryFile() as tmp:
        tmp.write(f.read())
        venv_python(tmp.name)


def create_venv():
    """Create a new venv."""
    utils.print_title("Creating venv")
    if os.name == 'nt':
        symlinks = False
    else:
        symlinks = True
    clear = g_args.clear or g_args.force
    upgrade = g_args.upgrade or g_args.cache is not None
    builder = venv.EnvBuilder(system_site_packages=False,
                              clear=clear, upgrade=upgrade,
                              symlinks=symlinks, with_pip=ensurepip)
    builder.create(g_path)
    # If we don't have ensurepip, we have to do it by hand...
    if not ensurepip:
        install_pip()


def restore_cache(cache_path):
    """Restore a cache if one is present and --cache is given."""
    if g_args.cache is not None:
        utils.print_title("Restoring cache")
        print("Restoring {} to {}...".format(cache_path, g_args.path))
        try:
            shutil.rmtree(g_args.path)
        except FileNotFoundError:
            pass
        try:
            shutil.copytree(cache_path, g_args.path, symlinks=True)
        except FileNotFoundError:
            print("No cache present!")
        else:
            return True
    return False


def save_cache(cache_path):
    """Save the cache if --cache is given."""
    if g_args.cache is not None:
        utils.print_title("Saving cache")
        print("Saving {} to {}...".format(g_args.path, cache_path))
        try:
            shutil.rmtree(cache_path)
        except FileNotFoundError:
            pass
        shutil.copytree(g_args.path, cache_path, symlinks=True)


def main():
    """Main entry point."""
    global g_path, g_args
    g_args = parse_args()
    if not g_args.path:
        print("Refusing to run with empty path!", file=sys.stderr)
        sys.exit(1)
    g_path = os.path.abspath(g_args.path)

    if os.path.exists(g_args.path) and not (g_args.force or g_args.clear or
                                            g_args.upgrade):
        print("{} does already exist! Use --clear or "
              "--upgrade.".format(g_path), file=sys.stderr)
        sys.exit(1)

    os_cache_dir = QStandardPaths.writableLocation(
        QStandardPaths.CacheLocation)
    file_name = 'qutebrowser-venv'
    if g_args.cache:
        file_name += '-' + g_args.cache
    cache_path = os.path.join(os_cache_dir, file_name)

    restored = restore_cache(cache_path)
    if not restored:
        create_venv()

    utils.print_title("Calling: setup.py develop")
    venv_python('setup.py', 'develop')

    if g_args.dev:
        utils.print_title("Installing developer packages")
        install_dev_packages()
    link_pyqt()
    test_toolchain()
    save_cache(cache_path)


if __name__ == '__main__':
    main()
