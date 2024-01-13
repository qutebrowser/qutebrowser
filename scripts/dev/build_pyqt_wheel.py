#!/usr/bin/env python3

# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Build updated PyQt wheels."""

import os
import subprocess
import argparse
import sys
import pathlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                                os.pardir))
from scripts import utils


def find_pyqt_bundle():
    """Try to find the pyqt-bundle executable next to the current Python.

    We do this instead of using $PATH so that the script can be used via
    .venv/bin/python.
    """
    bin_path = pathlib.Path(sys.executable).parent
    path = bin_path / 'pyqt-bundle'

    if not path.exists():
        raise FileNotFoundError("Can't find pyqt-bundle at {}".format(path))

    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('qt_location', help='Qt compiler directory')
    parser.add_argument('--wheels-dir', help='Directory to use for wheels',
                        default='wheels')
    args = parser.parse_args()

    old_cwd = pathlib.Path.cwd()

    try:
        pyqt_bundle = find_pyqt_bundle()
    except FileNotFoundError as e:
        utils.print_error(str(e))
        sys.exit(1)

    qt_dir = pathlib.Path(args.qt_location)
    bin_dir = qt_dir / 'bin'
    if not bin_dir.exists():
        utils.print_error("Can't find {}".format(bin_dir))
        sys.exit(1)

    wheels_dir = pathlib.Path(args.wheels_dir).resolve()
    wheels_dir.mkdir(exist_ok=True)

    if list(wheels_dir.glob('*')):
        utils.print_col("Wheels directory is not empty, "
                        "unexpected behavior might occur!", 'yellow')

    os.chdir(wheels_dir)

    utils.print_title("Downloading wheels")
    subprocess.run([sys.executable, '-m', 'pip', 'download',
                    '--no-deps', '--only-binary', 'PyQt5,PyQtWebEngine',
                    'PyQt5', 'PyQtWebEngine'], check=True)

    utils.print_title("Patching wheels")
    input_files = wheels_dir.glob('*.whl')
    for wheel in input_files:
        utils.print_subtitle(wheel.stem.split('-')[0])
        subprocess.run([str(pyqt_bundle),
                        '--qt-dir', args.qt_location,
                        '--ignore-missing',
                        str(wheel)],
                       check=True)
        wheel.unlink()

    print("Done, output files:")
    for wheel in wheels_dir.glob('*.whl'):
        print(wheel.relative_to(old_cwd))


if __name__ == '__main__':
    main()
