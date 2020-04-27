#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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


"""Create a local virtualenv with a PyQt install."""

import argparse
import pathlib
import sys
import os
import os.path
import typing
import shutil
import venv
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))
from scripts import utils, link_pyqt


REPO_ROOT = pathlib.Path(__file__).parent.parent


def parse_args() -> argparse.Namespace:
    """Parse commandline arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--keep',
                        action='store_true',
                        help="Reuse an existing virtualenv.")
    parser.add_argument('--venv-dir',
                        default='.venv',
                        help="Where to place the virtualenv.")
    parser.add_argument('--pyqt-version',
                        choices=pyqt_versions(),
                        default='auto',
                        help="PyQt version to install.")
    parser.add_argument('--pyqt-type',
                        choices=['binary', 'source', 'link', 'wheels', 'skip'],
                        default='binary',
                        help="How to install PyQt/Qt.")
    parser.add_argument('--pyqt-wheels-dir',
                        default='wheels',
                        help="Directory to get PyQt wheels from.")
    parser.add_argument('--virtualenv',
                        action='store_true',
                        help="Use virtualenv instead of venv.")
    parser.add_argument('--asciidoc', help="Full path to python and "
                        "asciidoc.py. If not given, it's searched in PATH.",
                        nargs=2, required=False,
                        metavar=('PYTHON', 'ASCIIDOC'))
    parser.add_argument('--dev',
                        action='store_true',
                        help="Also install dev/test dependencies.")
    parser.add_argument('--skip-docs',
                        action='store_true',
                        help="Skip doc generation.")
    parser.add_argument('--tox-error',
                        action='store_true',
                        help=argparse.SUPPRESS)
    return parser.parse_args()


def pyqt_versions() -> typing.List[str]:
    """Get a list of all available PyQt versions.

    The list is based on the filenames of misc/requirements/ files.
    """
    version_set = set()

    requirements_dir = REPO_ROOT / 'misc' / 'requirements'
    for req in requirements_dir.glob('requirements-pyqt-*.txt'):
        version_set.add(req.stem.split('-')[-1])

    versions = sorted(version_set,
                      key=lambda v: [int(c) for c in v.split('.')])
    return versions + ['auto']


def run_venv(venv_dir: pathlib.Path, executable, *args: str) -> None:
    """Run the given command inside the virtualenv."""
    subdir = 'Scripts' if os.name == 'nt' else 'bin'

    try:
        subprocess.run([str(venv_dir / subdir / executable)] +
                       [str(arg) for arg in args], check=True)
    except subprocess.CalledProcessError as e:
        utils.print_error("Subprocess failed, exiting")
        sys.exit(e.returncode)


def pip_install(venv_dir: pathlib.Path, *args: str) -> None:
    """Run a pip install command inside the virtualenv."""
    arg_str = ' '.join(str(arg) for arg in args)
    utils.print_col('venv$ pip install {}'.format(arg_str), 'blue')
    run_venv(venv_dir, 'python', '-m', 'pip', 'install', *args)


def delete_old_venv(venv_dir: pathlib.Path) -> None:
    """Remove an existing virtualenv directory."""
    if not venv_dir.exists():
        return

    markers = [
        venv_dir / '.tox-config1',  # tox
        venv_dir / 'pyvenv.cfg',  # venv
        venv_dir / 'Scripts',  # Windows
        venv_dir / 'bin',  # Linux
    ]

    if not any(m.exists() for m in markers):
        utils.print_error('{} does not look like a virtualenv, '
                          'cowardly refusing to remove it.'.format(venv_dir))
        sys.exit(1)

    utils.print_col('$ rm -r {}'.format(venv_dir), 'blue')
    shutil.rmtree(str(venv_dir))


def create_venv(venv_dir: pathlib.Path, use_virtualenv: bool = False) -> None:
    """Create a new virtualenv."""
    if use_virtualenv:
        utils.print_col('$ python3 -m virtualenv {}'.format(venv_dir), 'blue')
        try:
            subprocess.run([sys.executable, '-m', 'virtualenv', venv_dir],
                           check=True)
        except subprocess.CalledProcessError as e:
            utils.print_error("virtualenv failed, exiting")
            sys.exit(e.returncode)
    else:
        utils.print_col('$ python3 -m venv {}'.format(venv_dir), 'blue')
        venv.create(str(venv_dir), with_pip=True)


def upgrade_seed_pkgs(venv_dir: pathlib.Path) -> None:
    """Upgrade initial seed packages inside a virtualenv.

    This also makes sure that wheel is installed, which causes pip to use its
    wheel cache for rebuilds.
    """
    utils.print_title("Upgrading initial packages")
    pip_install(venv_dir, '-U', 'pip')
    pip_install(venv_dir, '-U', 'setuptools', 'wheel')


def requirements_file(name: str) -> pathlib.Path:
    """Get the filename of a requirements file."""
    return (REPO_ROOT / 'misc' / 'requirements' /
            'requirements-{}.txt'.format(name))


def pyqt_requirements_file(version: str) -> pathlib.Path:
    """Get the filename of the requirements file for the given PyQt version."""
    name = 'pyqt' if version == 'auto' else 'pyqt-{}'.format(version)
    return requirements_file(name)


def install_pyqt_binary(venv_dir: pathlib.Path, version: str) -> None:
    """Install PyQt from a binary wheel."""
    utils.print_title("Installing PyQt from binary")
    utils.print_col("No proprietary codec support will be available in "
                    "qutebrowser.", 'bold')
    pip_install(venv_dir, '-r', pyqt_requirements_file(version),
                '--only-binary', 'PyQt5,PyQtWebEngine')


def install_pyqt_source(venv_dir: pathlib.Path, version: str) -> None:
    """Install PyQt from the source tarball."""
    utils.print_title("Installing PyQt from sources")
    pip_install(venv_dir, '-r', pyqt_requirements_file(version),
                '--verbose', '--no-binary', 'PyQt5,PyQtWebEngine')


def install_pyqt_link(venv_dir: pathlib.Path) -> None:
    """Install PyQt by linking a system-wide install."""
    utils.print_title("Linking system-wide PyQt")
    lib_path = link_pyqt.get_venv_lib_path(str(venv_dir))
    link_pyqt.link_pyqt(sys.executable, lib_path)


def install_pyqt_wheels(venv_dir: pathlib.Path,
                        wheels_dir: pathlib.Path) -> None:
    """Install PyQt from the wheels/ directory."""
    utils.print_title("Installing PyQt wheels")
    wheels = [str(wheel) for wheel in wheels_dir.glob('*.whl')]
    pip_install(venv_dir, *wheels)


def install_requirements(venv_dir: pathlib.Path) -> None:
    """Install qutebrowser's requirement.txt."""
    utils.print_title("Installing other qutebrowser dependencies")
    requirements = REPO_ROOT / 'requirements.txt'
    pip_install(venv_dir, '-r', str(requirements))


def install_dev_requirements(venv_dir: pathlib.Path) -> None:
    """Install development dependencies."""
    utils.print_title("Installing dev dependencies")
    pip_install(venv_dir,
                '-r', str(requirements_file('dev')),
                '-r', requirements_file('tests'))


def install_qutebrowser(venv_dir: pathlib.Path) -> None:
    """Install qutebrowser itself as an editable install."""
    utils.print_title("Installing qutebrowser")
    pip_install(venv_dir, '-e', str(REPO_ROOT))


def regenerate_docs(venv_dir: pathlib.Path,
                    asciidoc: typing.Optional[typing.Tuple[str, str]]):
    """Regenerate docs using asciidoc."""
    utils.print_title("Generating documentation")
    if asciidoc is not None:
        a2h_args = ['--asciidoc'] + asciidoc
    else:
        a2h_args = []
    script_path = pathlib.Path(__file__).parent / 'asciidoc2html.py'

    utils.print_col('venv$ python3 scripts/asciidoc2html.py {}'
                    .format(' '.join(a2h_args)), 'blue')
    run_venv(venv_dir, 'python', str(script_path), *a2h_args)


def main() -> None:
    """Install qutebrowser in a virtualenv.."""
    args = parse_args()
    venv_dir = pathlib.Path(args.venv_dir)
    wheels_dir = pathlib.Path(args.pyqt_wheels_dir)
    utils.change_cwd()

    if (args.pyqt_version != 'auto' and
            args.pyqt_type not in ['binary', 'source']):
        utils.print_error('The --pyqt-version option is only available when '
                          'installing PyQt from binary or source')
        sys.exit(1)
    elif args.pyqt_wheels_dir != 'wheels' and args.pyqt_type != 'wheels':
        utils.print_error('The --pyqt-wheels-dir option is only available '
                          'when installing PyQt from wheels')
        sys.exit(1)

    if not args.keep:
        utils.print_title("Creating virtual environment")
        delete_old_venv(venv_dir)
        create_venv(venv_dir, use_virtualenv=args.virtualenv)

    upgrade_seed_pkgs(venv_dir)

    if args.pyqt_type == 'binary':
        install_pyqt_binary(venv_dir, args.pyqt_version)
    elif args.pyqt_type == 'source':
        install_pyqt_source(venv_dir, args.pyqt_version)
    elif args.pyqt_type == 'link':
        install_pyqt_link(venv_dir)
    elif args.pyqt_type == 'wheels':
        install_pyqt_wheels(venv_dir, wheels_dir)
    elif args.pyqt_type == 'skip':
        pass
    else:
        raise AssertionError

    install_requirements(venv_dir)
    install_qutebrowser(venv_dir)
    if args.dev:
        install_dev_requirements(venv_dir)

    if not args.skip_docs:
        regenerate_docs(venv_dir, args.asciidoc)


if __name__ == '__main__':
    main()
