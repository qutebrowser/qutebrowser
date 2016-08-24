#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Symlink PyQt into a given virtualenv."""

import os
import argparse
import shutil
import os.path
import sys
import subprocess
import tempfile
import filecmp


class Error(Exception):

    """Exception raised when linking fails."""

    pass


def run_py(executable, *code):
    """Run the given python code with the given executable."""
    if os.name == 'nt' and len(code) > 1:
        # Windows can't do newlines in arguments...
        oshandle, filename = tempfile.mkstemp()
        with os.fdopen(oshandle, 'w') as f:
            f.write('\n'.join(code))
        cmd = [executable, filename]
        try:
            ret = subprocess.check_output(cmd, universal_newlines=True)
        finally:
            os.remove(filename)
    else:
        cmd = [executable, '-c', '\n'.join(code)]
        ret = subprocess.check_output(cmd, universal_newlines=True)
    return ret.rstrip()


def verbose_copy(src, dst, *, follow_symlinks=True):
    """Copy function for shutil.copytree which prints copied files."""
    if '-v' in sys.argv:
        print('{} -> {}'.format(src, dst))
    shutil.copy(src, dst, follow_symlinks=follow_symlinks)


def get_ignored_files(directory, files):
    """Get the files which should be ignored for link_pyqt() on Windows."""
    needed_exts = ('.py', '.dll', '.pyd', '.so')
    ignored_dirs = ('examples', 'qml', 'uic', 'doc')
    filtered = []
    for f in files:
        ext = os.path.splitext(f)[1]
        full_path = os.path.join(directory, f)
        if os.path.isdir(full_path) and f in ignored_dirs:
            filtered.append(f)
        elif (ext not in needed_exts) and os.path.isfile(full_path):
            filtered.append(f)
    return filtered


def needs_update(source, dest):
    """Check if a file to be linked/copied needs to be updated."""
    if os.path.islink(dest):
        # No need to delete a link and relink -> skip this
        return False
    elif os.path.isdir(dest):
        diffs = filecmp.dircmp(source, dest)
        ignored = get_ignored_files(source, diffs.left_only)
        has_new_files = set(ignored) != set(diffs.left_only)
        return (has_new_files or diffs.right_only or diffs.common_funny or
                diffs.diff_files or diffs.funny_files)
    else:
        return not filecmp.cmp(source, dest)


def get_lib_path(executable, name, required=True):
    """Get the path of a python library.

    Args:
        executable: The Python executable to use.
        name: The name of the library to get the path for.
        required: Whether Error should be raised if the lib was not found.
    """
    code = [
        'try:',
        '    import {}'.format(name),
        'except ImportError as e:',
        '    print("ImportError: " + str(e))',
        'else:',
        '    print("path: " + {}.__file__)'.format(name)
    ]
    output = run_py(executable, *code)

    try:
        prefix, data = output.split(': ')
    except ValueError:
        raise ValueError("Unexpected output: {!r}".format(output))

    if prefix == 'path':
        return data
    elif prefix == 'ImportError':
        if required:
            raise Error("Could not import {} with {}: {}!".format(
                name, executable, data))
        else:
            return None
    else:
        raise ValueError("Unexpected output: {!r}".format(output))


def link_pyqt(executable, venv_path):
    """Symlink the systemwide PyQt/sip into the venv.

    Args:
        executable: The python executable where the source files are present.
        venv_path: The path to the virtualenv site-packages.
    """
    sip_file = get_lib_path(executable, 'sip')
    sipconfig_file = get_lib_path(executable, 'sipconfig', required=False)
    pyqt_dir = os.path.dirname(get_lib_path(executable, 'PyQt5.QtCore'))

    for path in [sip_file, sipconfig_file, pyqt_dir]:
        if path is None:
            continue

        fn = os.path.basename(path)
        dest = os.path.join(venv_path, fn)

        if os.path.exists(dest):
            if needs_update(path, dest):
                remove(dest)
            else:
                continue

        copy_or_link(path, dest)


def copy_or_link(source, dest):
    """Copy or symlink source to dest."""
    if os.name == 'nt':
        if os.path.isdir(source):
            print('{} -> {}'.format(source, dest))
            shutil.copytree(source, dest, ignore=get_ignored_files,
                            copy_function=verbose_copy)
        else:
            print('{} -> {}'.format(source, dest))
            shutil.copy(source, dest)
    else:
        print('{} -> {}'.format(source, dest))
        os.symlink(source, dest)


def remove(filename):
    """Remove a given filename, regardless of whether it's a file or dir."""
    if os.path.isdir(filename):
        shutil.rmtree(filename)
    else:
        os.unlink(filename)


def get_venv_lib_path(path):
    """Get the library path of a virtualenv."""
    subdir = 'Scripts' if os.name == 'nt' else 'bin'
    executable = os.path.join(path, subdir, 'python')
    return run_py(executable,
                  'from distutils.sysconfig import get_python_lib',
                  'print(get_python_lib())')


def get_tox_syspython(tox_path):
    """Get the system python based on a virtualenv created by tox."""
    path = os.path.join(tox_path, '.tox-config1')
    with open(path, encoding='ascii') as f:
        line = f.readline()
    _md5, sys_python = line.rstrip().split(' ', 1)
    return sys_python


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('path', help="Base path to the venv.")
    parser.add_argument('--tox', help="Add when called via tox.",
                        action='store_true')
    args = parser.parse_args()

    if args.tox:
        executable = get_tox_syspython(args.path)
    else:
        executable = sys.executable

    venv_path = get_venv_lib_path(args.path)
    link_pyqt(executable, venv_path)


if __name__ == '__main__':
    try:
        main()
    except Error as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
