#!/usr/bin/env python3

# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later


"""Symlink PyQt into a given virtualenv."""

import os
import os.path
import argparse
import shutil
import sys
import subprocess
import tempfile
import filecmp
import json


class Error(Exception):

    """Exception raised when linking fails."""


def run_py(executable, *code):
    """Run the given python code with the given executable."""
    if os.name == 'nt' and len(code) > 1:
        # Windows can't do newlines in arguments...
        oshandle, filename = tempfile.mkstemp()
        with os.fdopen(oshandle, 'w') as f:
            f.write('\n'.join(code))
        cmd = [executable, filename]
        try:
            ret = subprocess.run(cmd, text=True, check=True,
                                 stdout=subprocess.PIPE).stdout
        finally:
            os.remove(filename)
    else:
        cmd = [executable, '-c', '\n'.join(code)]
        ret = subprocess.run(cmd, text=True, check=True,
                             stdout=subprocess.PIPE).stdout
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
            wrapper = os.environ["QUTE_QT_WRAPPER"]
            raise Error(
                f"Could not import {name} with {executable}: {data} "
                f"(QUTE_QT_WRAPPER: {wrapper})"
            )
        return None
    else:
        raise ValueError("Unexpected output: {!r}".format(output))


def link_pyqt(executable, venv_path, *, version):
    """Symlink the systemwide PyQt/sip into the venv.

    Args:
        executable: The python executable where the source files are present.
        venv_path: The path to the virtualenv site-packages.
        version: The PyQt version to use.
    """
    if version not in ["5", "6"]:
        raise ValueError(f"Invalid version {version}")

    pyqt_dir = os.path.dirname(get_lib_path(executable, f'PyQt{version}.QtCore'))

    try:
        get_lib_path(executable, f'PyQt{version}.sip')
    except Error:
        # There is no PyQt*.sip, so we need to copy the toplevel sip.
        sip_file = get_lib_path(executable, 'sip')
    else:
        # There is a PyQt*.sip, it'll get copied with the PyQt* dir.
        sip_file = None

    sipconfig_file = get_lib_path(executable, 'sipconfig', required=False)

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
                  'from sysconfig import get_path',
                  'print(get_path("platlib"))')


def get_tox_syspython(tox_path):
    """Get the system python based on a virtualenv created by tox."""
    path = os.path.join(tox_path, '.tox-config1')
    if os.path.exists(path):  # tox3
        with open(path, encoding='ascii') as f:
            line = f.readline()
        _md5, sys_python = line.rstrip().split(' ', 1)
    else:  # tox4
        path = os.path.join(tox_path, '.tox-info.json')
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
            sys_python = data["Python"]["executable"]
    # Follow symlinks to get the system-wide interpreter if we have a tox isolated
    # build.
    return os.path.realpath(sys_python)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('path', help="Base path to the venv.")
    parser.add_argument('--tox', help="Add when called via tox.",
                        action='store_true')
    args = parser.parse_args()

    executable = get_tox_syspython(args.path) if args.tox else sys.executable

    venv_path = get_venv_lib_path(args.path)
    wrapper = os.environ["QUTE_QT_WRAPPER"]
    link_pyqt(executable, venv_path, version=wrapper[-1])


if __name__ == '__main__':
    try:
        main()
    except Error as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
