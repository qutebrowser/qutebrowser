#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Script to regenerate requirements files in misc/requirements."""

import re
import sys
import os.path
import glob
import json
import subprocess
import tempfile
import argparse
import shutil
import pathlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                                os.pardir))

from scripts import utils

REPO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        '..', '..')  # /scripts/dev -> /scripts -> /
REQ_DIR = os.path.join(REPO_DIR, 'misc', 'requirements')

CHANGELOG_URLS_PATH = pathlib.Path(__file__).parent / "changelog_urls.json"
CHANGELOG_URLS = json.loads(CHANGELOG_URLS_PATH.read_text())


def convert_line(line, comments):
    """Convert the given requirement line to place into the output."""
    for pattern, repl in comments['replace'].items():
        line = re.sub(pattern, repl, line)

    pkgname = line.split('=')[0]

    if pkgname in comments['ignore']:
        line = '# ' + line

    try:
        line += '  # ' + comments['comment'][pkgname]
    except KeyError:
        pass

    try:
        line += '  # rq.filter: {}'.format(comments['filter'][pkgname])
    except KeyError:
        pass

    try:
        line += ' ; {}'.format(comments['markers'][pkgname])
    except KeyError:
        pass

    return line


def read_comments(fobj):
    """Find special comments in the config.

    Args:
        fobj: A file object for the config.

    Return:
        A dict with the parsed comment data.
    """
    comments = {
        'filter': {},
        'markers': {},
        'comment': {},
        'ignore': [],
        'add': [],
        'replace': {},
        'pre': False,
        'pip_args': [],
    }
    for line in fobj:
        if line.startswith('#@'):
            if ':' in line:
                command, args = line[2:].split(':', maxsplit=1)
                command = command.strip()
                args = args.strip()
            else:
                command = line[2:].strip()
                args = None

            if command == 'filter':
                pkg, filt = args.split(' ', maxsplit=1)
                comments['filter'][pkg] = filt
            elif command == 'comment':
                pkg, comment = args.split(' ', maxsplit=1)
                comments['comment'][pkg] = comment
            elif command == 'ignore':
                comments['ignore'] += args.split(', ')
            elif command == 'replace':
                pattern, replacement = args.split(' ', maxsplit=1)
                comments['replace'][pattern] = replacement
            elif command == 'markers':
                pkg, markers = args.split(' ', maxsplit=1)
                comments['markers'][pkg] = markers
            elif command == 'add':
                comments['add'].append(args)
            elif command == 'pre':
                comments['pre'] = True
            elif command == 'pip_args':
                comments['pip_args'] += args.split()
    return comments


def get_all_names():
    """Get all requirement names based on filenames."""
    for filename in glob.glob(os.path.join(REQ_DIR, 'requirements-*.txt-raw')):
        basename = os.path.basename(filename)
        yield basename[len('requirements-'):-len('.txt-raw')]


def run_pip(venv_dir, *args, quiet=False, **kwargs):
    """Run pip inside the virtualenv."""
    args = list(args)
    if quiet:
        args.insert(1, '-q')

    arg_str = ' '.join(str(arg) for arg in args)
    utils.print_col('venv$ pip {}'.format(arg_str), 'blue')

    venv_python = get_venv_python(venv_dir)
    return subprocess.run([venv_python, '-m', 'pip'] + args, check=True, **kwargs)


def init_venv(host_python, venv_dir, requirements, pre=False, pip_args=None):
    """Initialize a new virtualenv and install the given packages."""
    with utils.gha_group('Creating virtualenv'):
        utils.print_col('$ python3 -m venv {}'.format(venv_dir), 'blue')
        subprocess.run([host_python, '-m', 'venv', venv_dir], check=True)

        run_pip(venv_dir, 'install', '-U', 'pip', quiet=not utils.ON_CI)
        run_pip(venv_dir, 'install', '-U', 'setuptools', 'wheel', quiet=not utils.ON_CI)

    install_command = ['install', '-r', requirements]
    if pre:
        install_command.append('--pre')
    if pip_args:
        install_command += pip_args

    with utils.gha_group('Installing requirements'):
        run_pip(venv_dir, *install_command)
        run_pip(venv_dir, 'check')


def parse_args():
    """Parse commandline arguments via argparse."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--force-test', help="Force running environment tests",
                        action='store_true')
    parser.add_argument('names', nargs='*')
    return parser.parse_args()


def git_diff(*args):
    """Run a git diff command."""
    command = (['git', '--no-pager', 'diff'] + list(args) + [
        '--', 'requirements.txt', 'misc/requirements/requirements-*.txt'])
    proc = subprocess.run(command,
                          stdout=subprocess.PIPE,
                          encoding='utf-8',
                          check=True)
    return proc.stdout.splitlines()


class Change:

    """A single requirements change from a git diff output."""

    def __init__(self, name: str, base_path: pathlib.Path) -> None:
        self.name = name
        self.old = None
        self.new = None
        self.base = extract_requirement_name(base_path)
        if CHANGELOG_URLS.get(name):
            self.url = CHANGELOG_URLS[name]
            self.link = '[{}]({})'.format(self.name, self.url)
        else:
            self.url = '(no changelog)'
            self.link = self.name

    def __str__(self):
        prefix = f"- [{self.base}] {self.name}"
        suffix = f"   {self.url}"
        if self.old is None:
            return f"{prefix} new: {self.new} {suffix}"
        elif self.new is None:
            return f"{prefix} removed: {self.old} {suffix}"
        else:
            return f"{prefix} {self.old} -> {self.new} {suffix}"

    def table_str(self):
        """Generate a markdown table."""
        if self.old is None:
            return f'| {self.base} | {self.link} | -- | {self.new} |'
        elif self.new is None:
            return f'| {self.base} | {self.link} | {self.old} | -- |'
        else:
            return f'| {self.base} | {self.link} | {self.old} | {self.new} |'


def _get_changed_files():
    """Get a list of changed files via git."""
    changed_files = set()
    filenames = git_diff('--name-only')
    for filename in filenames:
        requirement_name = extract_requirement_name(pathlib.Path(filename))
        changed_files.add(requirement_name)

    return sorted(changed_files)


def extract_requirement_name(path: pathlib.Path) -> str:
    prefix = "requirements-"
    assert path.suffix == ".txt", path
    assert path.stem.startswith(prefix), path
    return path.stem[len(prefix):]


def parse_versioned_line(line):
    """Parse a requirements.txt line into name/version."""
    if line[0] == '#':  # ignored dependency
        line = line[1:].strip()

    # Strip comments and pip environment markers
    line = line.rsplit('#', maxsplit=1)[0]
    line = line.split(';')[0].strip()

    ops = ["==", "~=", "!=", ">", "<", ">=", "<="]

    if any(op in line for op in ops):
        # strictly speaking, this version isn't necessarily correct, but it's
        # enough for the table.
        for op in ops:
            if op in line:
                name, version = line.split(op)
    elif line.startswith('-e'):
        rest, name = line.split('#egg=')
        version = rest.split('@')[1][:7]
    else:
        name = line
        version = '?'

    if name.startswith('#'):  # duplicate requirements
        name = name[1:].strip()

    return name, version


def _get_changes(diff):
    """Get a list of changed versions from git."""
    changes_dict = {}
    current_path = None

    for line in diff:
        if not line.startswith('-') and not line.startswith('+'):
            continue
        elif line.startswith('--- '):
            prefix = '--- a/'
            current_path = pathlib.Path(line[len(prefix):])
            continue
        elif line.startswith('+++ '):
            prefix = '+++ b/'
            new_path = pathlib.Path(line[len(prefix):])
            assert current_path == new_path, (current_path, new_path)
            continue
        elif not line.strip():
            # Could be newline changes on Windows
            continue
        elif line[1:].startswith('# This file is automatically'):
            # Could be newline changes on Windows
            continue

        name, version = parse_versioned_line(line[1:])

        if name not in changes_dict:
            changes_dict[name] = Change(name, base_path=current_path)

        if line.startswith('-'):
            changes_dict[name].old = version
        elif line.startswith('+'):
            changes_dict[name].new = version

    return [change for _name, change in sorted(changes_dict.items())]


def print_changed_files():
    """Output all changed files from this run."""
    diff = git_diff()
    if utils.ON_CI:
        with utils.gha_group('Raw diff'):
            print('\n'.join(diff))

    changed_files = _get_changed_files()
    files_text = '\n'.join('- ' + line for line in changed_files)

    changes = _get_changes(diff)
    changes_text = '\n'.join(str(change) for change in changes)

    utils.print_subtitle('Files')
    print(files_text)
    print()
    utils.print_subtitle('Changes')
    print(changes_text)

    if utils.ON_CI:
        print()
        print('::set-output name=changed::' +
              files_text.replace('\n', '%0A'))
        table_header = [
            '| File | Requirement | old | new |',
            '|------|-------------|-----|-----|',
        ]
        diff_table = '%0A'.join(table_header +
                                [change.table_str() for change in changes])
        print('::set-output name=diff::' + diff_table)


def get_host_python(name):
    """Get the Python to use for a given requirement name.

    pylint installs typed_ast on < 3.8 only
    """
    if name == 'pylint':
        return 'python3.7'
    else:
        return sys.executable


def get_venv_python(venv_dir):
    """Get the path to Python inside a virtualenv."""
    subdir = 'Scripts' if os.name == 'nt' else 'bin'
    return os.path.join(venv_dir, subdir, 'python')


def get_outfile(name):
    """Get the path to the output requirements.txt file."""
    if name == 'qutebrowser':
        return os.path.join(REPO_DIR, 'requirements.txt')
    return os.path.join(REQ_DIR, 'requirements-{}.txt'.format(name))


def build_requirements(name):
    """Build a requirements file."""
    utils.print_subtitle("Building")
    filename = os.path.join(REQ_DIR, 'requirements-{}.txt-raw'.format(name))
    host_python = get_host_python(name)

    with open(filename, 'r', encoding='utf-8') as f:
        comments = read_comments(f)

    with tempfile.TemporaryDirectory() as tmpdir:
        init_venv(host_python=host_python,
                  venv_dir=tmpdir,
                  requirements=filename,
                  pre=comments['pre'],
                  pip_args=comments['pip_args'])
        with utils.gha_group('Freezing requirements'):
            args = ['--all'] if name == 'tox' else []
            proc = run_pip(tmpdir, 'freeze', *args, stdout=subprocess.PIPE)
            reqs = proc.stdout.decode('utf-8')
            if utils.ON_CI:
                print(reqs.strip())

    outfile = get_outfile(name)

    with open(outfile, 'w', encoding='utf-8') as f:
        f.write("# This file is automatically generated by "
                "scripts/dev/recompile_requirements.py\n\n")
        for line in reqs.splitlines():
            if line.startswith('qutebrowser=='):
                continue
            f.write(convert_line(line, comments) + '\n')

        for line in comments['add']:
            f.write(line + '\n')

    return outfile


def test_tox():
    """Test requirements via tox."""
    host_python = get_host_python('tox')
    req_path = os.path.join(REQ_DIR, 'requirements-tox.txt')

    with tempfile.TemporaryDirectory() as tmpdir:
        venv_dir = os.path.join(tmpdir, 'venv')
        tox_workdir = os.path.join(tmpdir, 'tox-workdir')
        venv_python = get_venv_python(venv_dir)
        init_venv(host_python, venv_dir, req_path)
        list_proc = subprocess.run([venv_python, '-m', 'tox', '--listenvs'],
                                   check=True,
                                   stdout=subprocess.PIPE,
                                   universal_newlines=True)
        environments = list_proc.stdout.strip().split('\n')
        for env in environments:
            with utils.gha_group('tox for {}'.format(env)):
                utils.print_subtitle(env)
                utils.print_col('venv$ tox -e {} --notest'.format(env), 'blue')
                subprocess.run([venv_python, '-m', 'tox',
                                '--workdir', tox_workdir,
                                '-e', env,
                                '--notest'],
                               check=True)


def test_requirements(name, outfile, *, force=False):
    """Test a resulting requirements file."""
    print()
    utils.print_subtitle("Testing")

    if name not in _get_changed_files() and not force:
        print(f"Skipping test as there were no changes for {name}.")
        return

    in_file = os.path.join(REQ_DIR, 'requirements-{}.txt-raw'.format(name))
    with open(in_file, 'r', encoding='utf-8') as f:
        comments = read_comments(f)

    host_python = get_host_python(name)
    with tempfile.TemporaryDirectory() as tmpdir:
        init_venv(host_python, tmpdir, outfile, pip_args=comments['pip_args'])


def cleanup_pylint_build():
    """Clean up pylint_checkers build files."""
    path = pathlib.Path(__file__).parent / 'pylint_checkers' / 'build'
    utils.print_col(f'$ rm -r {path}', 'blue')
    shutil.rmtree(path)


def main():
    """Re-compile the given (or all) requirement files."""
    args = parse_args()
    if args.names:
        names = args.names
    else:
        names = sorted(get_all_names())

    utils.print_col('Rebuilding requirements: ' + ', '.join(names), 'green')
    for name in names:
        utils.print_title(name)
        outfile = build_requirements(name)
        test_requirements(name, outfile, force=args.force_test)
        if name == 'pylint':
            cleanup_pylint_build()

    utils.print_title('Testing via tox')
    if args.names and not args.force_test:
        # If we selected a subset, let's not go through the trouble of testing
        # via tox.
        print("Skipping: Selected a subset only")
    elif not _get_changed_files() and not args.force_test:
        print("Skipping: No changes")
    else:
        test_tox()

    utils.print_title('Changed')
    print_changed_files()


if __name__ == '__main__':
    main()
