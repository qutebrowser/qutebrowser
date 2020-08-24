#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Script to regenerate requirements files in misc/requirements."""

import re
import sys
import os.path
import glob
import subprocess
import tempfile
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                                os.pardir))

from scripts import utils

REPO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        '..', '..')  # /scripts/dev -> /scripts -> /
REQ_DIR = os.path.join(REPO_DIR, 'misc', 'requirements')

CHANGELOG_URLS = {
    'pyparsing': 'https://github.com/pyparsing/pyparsing/blob/master/CHANGES',
    'cherrypy': 'https://github.com/cherrypy/cherrypy/blob/master/CHANGES.rst',
    'pylint': 'http://pylint.pycqa.org/en/latest/whatsnew/changelog.html',
    'setuptools': 'https://github.com/pypa/setuptools/blob/master/CHANGES.rst',
    'pytest-cov': 'https://github.com/pytest-dev/pytest-cov/blob/master/CHANGELOG.rst',
    'requests': 'https://github.com/psf/requests/blob/master/HISTORY.md',
    'requests-file': 'https://github.com/dashea/requests-file/blob/master/CHANGES.rst',
    'werkzeug': 'https://github.com/pallets/werkzeug/blob/master/CHANGES.rst',
    'hypothesis': 'https://hypothesis.readthedocs.io/en/latest/changes.html',
    'mypy': 'https://mypy-lang.blogspot.com/',
    'pytest': 'https://docs.pytest.org/en/latest/changelog.html',
    'iniconfig': 'https://github.com/RonnyPfannschmidt/iniconfig/blob/master/CHANGELOG',
    'tox': 'https://tox.readthedocs.io/en/latest/changelog.html',
    'pyyaml': 'https://github.com/yaml/pyyaml/blob/master/CHANGES',
    'pytest-bdd': 'https://github.com/pytest-dev/pytest-bdd/blob/master/CHANGES.rst',
    'snowballstemmer': 'https://github.com/snowballstem/snowball/blob/master/NEWS',
    'virtualenv': 'https://virtualenv.pypa.io/en/latest/changelog.html',
    'pip': 'https://pip.pypa.io/en/stable/news/',
    'packaging': 'https://pypi.org/project/packaging/',
    'flake8-docstrings': 'https://pypi.org/project/flake8-docstrings/',
    'attrs': 'http://www.attrs.org/en/stable/changelog.html',
    'jinja2': 'https://github.com/pallets/jinja/blob/master/CHANGES.rst',
    'flake8': 'https://gitlab.com/pycqa/flake8/tree/master/docs/source/release-notes',
    'cffi': 'https://cffi.readthedocs.io/en/latest/whatsnew.html',
    'flake8-debugger': 'https://github.com/JBKahn/flake8-debugger/',
    'astroid': 'https://github.com/PyCQA/astroid/blob/2.4/ChangeLog',
    'pytest-instafail': 'https://github.com/pytest-dev/pytest-instafail/blob/master/CHANGES.rst',
    'coverage': 'https://github.com/nedbat/coveragepy/blob/master/CHANGES.rst',
    'colorama': 'https://github.com/tartley/colorama/blob/master/CHANGELOG.rst',
    'hunter': 'https://github.com/ionelmc/python-hunter/blob/master/CHANGELOG.rst',
    'uritemplate': 'https://pypi.org/project/uritemplate/',
    'flake8-builtins': 'https://github.com/gforcada/flake8-builtins/blob/master/CHANGES.rst',
    'flake8-bugbear': 'https://github.com/PyCQA/flake8-bugbear',
    'flake8-tidy-imports': 'https://github.com/adamchainz/flake8-tidy-imports/blob/master/HISTORY.rst',
    'flake8-tuple': 'https://github.com/ar4s/flake8_tuple/blob/master/HISTORY.rst',
    'more-itertools': 'https://github.com/erikrose/more-itertools/blob/master/docs/versions.rst',
    'pydocstyle': 'http://www.pydocstyle.org/en/latest/release_notes.html',
    'sphinx': 'https://www.sphinx-doc.org/en/master/changes.html',
    'jaraco.functools': 'https://github.com/jaraco/jaraco.functools/blob/master/CHANGES.rst',
    'parse': 'https://github.com/r1chardj0n3s/parse#potential-gotchas',
    'py': 'https://py.readthedocs.io/en/latest/changelog.html#changelog',
    'pytest-mock': 'https://github.com/pytest-dev/pytest-mock/blob/master/CHANGELOG.rst',
    'pytest-qt': 'https://github.com/pytest-dev/pytest-qt/blob/master/CHANGELOG.rst',
    'wcwidth': 'https://github.com/jquast/wcwidth#history',
    'pyinstaller': 'https://pyinstaller.readthedocs.io/en/stable/CHANGES.html',
    'pyinstaller-hooks-contrib': 'https://github.com/pyinstaller/pyinstaller-hooks-contrib/blob/master/CHANGELOG.rst',
    'pytest-benchmark': 'https://pytest-benchmark.readthedocs.io/en/stable/changelog.html',
    'typed-ast': 'https://github.com/python/typed_ast/commits/master',
    'docutils': 'https://docutils.sourceforge.io/RELEASE-NOTES.html',
    'bump2version': 'https://github.com/c4urself/bump2version/blob/master/CHANGELOG.md',
    'six': 'https://github.com/benjaminp/six/blob/master/CHANGES',
    'flake8-comprehensions': 'https://github.com/adamchainz/flake8-comprehensions/blob/master/HISTORY.rst',
    'altgraph': 'https://github.com/ronaldoussoren/altgraph/blob/master/doc/changelog.rst',
    'urllib3': 'https://github.com/urllib3/urllib3/blob/master/CHANGES.rst',
    'wheel': 'https://github.com/pypa/wheel/blob/master/docs/news.rst',
    'mako': 'https://docs.makotemplates.org/en/latest/changelog.html',
    'lxml': 'https://lxml.de/4.5/changes-4.5.0.html',
    'jwcrypto': 'https://github.com/latchset/jwcrypto/commits/master',
    'tox-pip-version': 'https://github.com/pglass/tox-pip-version/commits/master',
    'wrapt': 'https://github.com/GrahamDumpleton/wrapt/blob/develop/docs/changes.rst',
    'pep517': 'https://github.com/pypa/pep517/commits/master',
    'cryptography': 'https://cryptography.io/en/latest/changelog/',
    'toml': 'https://github.com/uiri/toml/releases',
    'pyqt': 'https://www.riverbankcomputing.com/',
    'vulture': 'https://github.com/jendrikseipp/vulture/blob/master/CHANGELOG.md',
    'distlib': 'https://bitbucket.org/pypa/distlib/src/master/CHANGES.rst',
    'py-cpuinfo': 'https://github.com/workhorsy/py-cpuinfo/blob/master/ChangeLog',
    'cheroot': 'https://cheroot.cherrypy.org/en/latest/history.html',
    'certifi': 'https://ccadb-public.secure.force.com/mozilla/IncludedCACertificateReport',
    'chardet': 'https://github.com/chardet/chardet/releases',
    'idna': 'https://github.com/kjd/idna/blob/master/HISTORY.rst',
    'tldextract': 'https://github.com/john-kurkowski/tldextract/blob/master/CHANGELOG.md',
    'typing_extensions': 'https://github.com/python/typing/commits/master/typing_extensions',
}

# PyQt versions which need SIP v4
OLD_PYQT = {'pyqt-5.7', 'pyqt-5.9', 'pyqt-5.10', 'pyqt-5.11'}


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
    return comments


def get_all_names():
    """Get all requirement names based on filenames."""
    for filename in glob.glob(os.path.join(REQ_DIR, 'requirements-*.txt-raw')):
        basename = os.path.basename(filename)
        yield basename[len('requirements-'):-len('.txt-raw')]


def filter_names(names, old_pyqt=False):
    """Filter requirement names."""
    if old_pyqt:
        return sorted(names)
    else:
        return sorted(set(names) - OLD_PYQT)


def run_pip(venv_dir, *args, **kwargs):
    """Run pip inside the virtualenv."""
    arg_str = ' '.join(str(arg) for arg in args)
    utils.print_col('venv$ pip {}'.format(arg_str), 'blue')
    venv_python = os.path.join(venv_dir, 'bin', 'python')
    return subprocess.run([venv_python, '-m', 'pip'] + list(args),
                          check=True, **kwargs)


def init_venv(host_python, venv_dir, requirements, pre=False):
    """Initialize a new virtualenv and install the given packages."""
    with utils.gha_group('Creating virtualenv'):
        utils.print_col('$ python3 -m venv {}'.format(venv_dir), 'blue')
        subprocess.run([host_python, '-m', 'venv', venv_dir], check=True)

        run_pip(venv_dir, 'install', '-U', 'pip')
        run_pip(venv_dir, 'install', '-U', 'setuptools', 'wheel')

    install_command = ['install', '-r', requirements]
    if pre:
        install_command.append('--pre')

    with utils.gha_group('Installing requirements'):
        run_pip(venv_dir, *install_command)
        run_pip(venv_dir, 'check')


def parse_args():
    """Parse commandline arguments via argparse."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--old-pyqt',
                        action='store_true',
                        help='Also include old PyQt requirements.')
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

    def __init__(self, name):
        self.name = name
        self.old = None
        self.new = None
        if name.lower() in CHANGELOG_URLS:
            self.url = CHANGELOG_URLS[name.lower()]
            self.link = '[{}]({})'.format(self.name, self.url)
        else:
            self.url = '(no changelog)'
            self.link = self.name

    def __str__(self):
        if self.old is None:
            return '- {} new: {}    {}'.format(self.name, self.new, self.url)
        elif self.new is None:
            return '- {} removed: {}    {}'.format(self.name, self.old,
                                                   self.url)
        else:
            return '- {} {} -> {}    {}'.format(self.name, self.old, self.new,
                                                self.url)

    def table_str(self):
        """Generate a markdown table."""
        if self.old is None:
            return '| {} | -- | {} |'.format(self.link, self.new)
        elif self.new is None:
            return '| {} | {} | -- |'.format(self.link, self.old)
        else:
            return '| {} | {} | {} |'.format(self.link, self.old, self.new)


def print_changed_files():
    """Output all changed files from this run."""
    changed_files = set()
    filenames = git_diff('--name-only')
    for filename in filenames:
        filename = filename.strip()
        filename = filename.replace('misc/requirements/requirements-', '')
        filename = filename.replace('.txt', '')
        changed_files.add(filename)
    files_text = '\n'.join('- ' + line for line in sorted(changed_files))

    changes_dict = {}
    diff = git_diff()
    for line in diff:
        if not line.startswith('-') and not line.startswith('+'):
            continue
        if line.startswith('+++ ') or line.startswith('--- '):
            continue

        if '==' in line:
            name, version = line[1:].split('==')
        else:
            name = line[1:]
            version = '?'

        if name not in changes_dict:
            changes_dict[name] = Change(name)

        if line.startswith('-'):
            changes_dict[name].old = version
        elif line.startswith('+'):
            changes_dict[name].new = version

    changes = [change for _name, change in sorted(changes_dict.items())]
    diff_text = '\n'.join(str(change) for change in changes)

    utils.print_title('Changed')
    utils.print_subtitle('Files')
    print(files_text)
    print()
    utils.print_subtitle('Diff')
    print(diff_text)

    if 'CI' in os.environ:
        print()
        print('::set-output name=changed::' +
              files_text.replace('\n', '%0A'))
        table_header = [
            '| Requirement | old | new |',
            '|-------------|-----|-----|',
        ]
        diff_table = '%0A'.join(table_header +
                                [change.table_str() for change in changes])
        print('::set-output name=diff::' + diff_table)


def get_host_python(name):
    """Get the Python to use for a given requirement name.

    Old PyQt versions need sip v4 which doesn't work on Python 3.8
    ylint installs typed_ast on < 3.8 only
    """
    if name in OLD_PYQT or name == 'pylint':
        return 'python3.7'
    else:
        return sys.executable


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
                  pre=comments['pre'])
        with utils.gha_group('Freezing requirements'):
            proc = run_pip(tmpdir, 'freeze', stdout=subprocess.PIPE)
            reqs = proc.stdout.decode('utf-8')
            if utils.ON_CI:
                print(reqs.strip())

    if name == 'qutebrowser':
        outfile = os.path.join(REPO_DIR, 'requirements.txt')
    else:
        outfile = os.path.join(REQ_DIR, 'requirements-{}.txt'.format(name))

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
    utils.print_title('Testing via tox')
    host_python = get_host_python('tox')
    req_path = os.path.join(REQ_DIR, 'requirements-tox.txt')

    with tempfile.TemporaryDirectory() as tmpdir:
        venv_dir = os.path.join(tmpdir, 'venv')
        tox_workdir = os.path.join(tmpdir, 'tox-workdir')
        venv_python = os.path.join(venv_dir, 'bin', 'python')
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


def test_requirements(name, outfile):
    """Test a resulting requirements file."""
    print()
    utils.print_subtitle("Testing")

    host_python = get_host_python(name)
    with tempfile.TemporaryDirectory() as tmpdir:
        init_venv(host_python, tmpdir, outfile)


def main():
    """Re-compile the given (or all) requirement files."""
    args = parse_args()
    if args.names:
        names = args.names
    else:
        names = filter_names(get_all_names(), old_pyqt=args.old_pyqt)

    utils.print_col('Rebuilding requirements: ' + ', '.join(names), 'green')
    for name in names:
        utils.print_title(name)
        outfile = build_requirements(name)
        test_requirements(name, outfile)

    if not args.names:
        # If we selected a subset, let's not go through the trouble of testing
        # via tox.
        test_tox()

    print_changed_files()


if __name__ == '__main__':
    main()
