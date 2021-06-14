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
    'pylint': 'https://pylint.pycqa.org/en/latest/whatsnew/changelog.html',
    'isort': 'https://pycqa.github.io/isort/CHANGELOG/',
    'lazy-object-proxy': 'https://github.com/ionelmc/python-lazy-object-proxy/blob/master/CHANGELOG.rst',
    'mccabe': 'https://github.com/PyCQA/mccabe#changes',
    'pytest-cov': 'https://github.com/pytest-dev/pytest-cov/blob/master/CHANGELOG.rst',
    'pytest-xdist': 'https://github.com/pytest-dev/pytest-xdist/blob/master/CHANGELOG.rst',
    'pytest-forked': 'https://github.com/pytest-dev/pytest-forked/blob/master/CHANGELOG',
    'pytest-xvfb': 'https://github.com/The-Compiler/pytest-xvfb/blob/master/CHANGELOG.rst',
    'EasyProcess': 'https://github.com/ponty/EasyProcess/commits/master',
    'PyVirtualDisplay': 'https://github.com/ponty/PyVirtualDisplay/commits/master',
    'execnet': 'https://execnet.readthedocs.io/en/latest/changelog.html',
    'pytest-rerunfailures': 'https://github.com/pytest-dev/pytest-rerunfailures/blob/master/CHANGES.rst',
    'pytest-repeat': 'https://github.com/pytest-dev/pytest-repeat/blob/master/CHANGES.rst',
    'requests': 'https://github.com/psf/requests/blob/master/HISTORY.md',
    'requests-file': 'https://github.com/dashea/requests-file/blob/master/CHANGES.rst',
    'Werkzeug': 'https://werkzeug.palletsprojects.com/en/latest/changes/',
    'click': 'https://click.palletsprojects.com/en/latest/changes/',
    'itsdangerous': 'https://itsdangerous.palletsprojects.com/en/latest/changes/',
    'parse-type': 'https://github.com/jenisys/parse_type/blob/master/CHANGES.txt',
    'sortedcontainers': 'https://github.com/grantjenks/python-sortedcontainers/blob/master/HISTORY.rst',
    'soupsieve': 'https://facelessuser.github.io/soupsieve/about/changelog/',
    'Flask': 'https://flask.palletsprojects.com/en/latest/changes/',
    'Mako': 'https://docs.makotemplates.org/en/latest/changelog.html',
    'glob2': 'https://github.com/miracle2k/python-glob2/blob/master/CHANGES',
    'hypothesis': 'https://hypothesis.readthedocs.io/en/latest/changes.html',
    'mypy': 'https://mypy-lang.blogspot.com/',
    'pytest': 'https://docs.pytest.org/en/latest/changelog.html',
    'iniconfig': 'https://github.com/RonnyPfannschmidt/iniconfig/blob/master/CHANGELOG',
    'tox': 'https://tox.readthedocs.io/en/latest/changelog.html',
    'PyYAML': 'https://github.com/yaml/pyyaml/blob/master/CHANGES',
    'pytest-bdd': 'https://github.com/pytest-dev/pytest-bdd/blob/master/CHANGES.rst',
    'snowballstemmer': 'https://github.com/snowballstem/snowball/blob/master/NEWS',
    'virtualenv': 'https://virtualenv.pypa.io/en/latest/changelog.html',
    'packaging': 'https://packaging.pypa.io/en/latest/changelog.html',
    'build': 'https://github.com/pypa/build/blob/main/CHANGELOG.rst',
    'attrs': 'https://www.attrs.org/en/stable/changelog.html',
    'Jinja2': 'https://jinja.palletsprojects.com/en/latest/changes/',
    'MarkupSafe': 'https://markupsafe.palletsprojects.com/en/latest/changes/',
    'flake8': 'https://gitlab.com/pycqa/flake8/tree/master/docs/source/release-notes',
    'flake8-docstrings': 'https://pypi.org/project/flake8-docstrings/',
    'flake8-debugger': 'https://github.com/JBKahn/flake8-debugger/',
    'flake8-builtins': 'https://github.com/gforcada/flake8-builtins/blob/master/CHANGES.rst',
    'flake8-bugbear': 'https://github.com/PyCQA/flake8-bugbear#change-log',
    'flake8-tidy-imports': 'https://github.com/adamchainz/flake8-tidy-imports/blob/master/HISTORY.rst',
    'flake8-tuple': 'https://github.com/ar4s/flake8_tuple/blob/master/HISTORY.rst',
    'flake8-comprehensions': 'https://github.com/adamchainz/flake8-comprehensions/blob/master/HISTORY.rst',
    'flake8-copyright': 'https://github.com/savoirfairelinux/flake8-copyright/blob/master/CHANGELOG.rst',
    'flake8-deprecated': 'https://github.com/gforcada/flake8-deprecated/blob/master/CHANGES.rst',
    'flake8-future-import': 'https://github.com/xZise/flake8-future-import#changes',
    'flake8-mock': 'https://github.com/aleGpereira/flake8-mock#changes',
    'flake8-polyfill': 'https://gitlab.com/pycqa/flake8-polyfill/-/blob/master/CHANGELOG.rst',
    'flake8-string-format': 'https://github.com/xZise/flake8-string-format#changes',
    'pep8-naming': 'https://github.com/PyCQA/pep8-naming/blob/master/CHANGELOG.rst',
    'pycodestyle': 'https://github.com/PyCQA/pycodestyle/blob/master/CHANGES.txt',
    'pyflakes': 'https://github.com/PyCQA/pyflakes/blob/master/NEWS.rst',
    'cffi': 'https://github.com/python-cffi/release-doc/blob/master/doc/source/whatsnew.rst',
    'astroid': 'https://github.com/PyCQA/astroid/blob/2.4/ChangeLog',
    'pytest-instafail': 'https://github.com/pytest-dev/pytest-instafail/blob/master/CHANGES.rst',
    'coverage': 'https://github.com/nedbat/coveragepy/blob/master/CHANGES.rst',
    'colorama': 'https://github.com/tartley/colorama/blob/master/CHANGELOG.rst',
    'hunter': 'https://github.com/ionelmc/python-hunter/blob/master/CHANGELOG.rst',
    'uritemplate': 'https://github.com/python-hyper/uritemplate/blob/master/HISTORY.rst',
    'more-itertools': 'https://github.com/erikrose/more-itertools/blob/master/docs/versions.rst',
    'pydocstyle': 'https://www.pydocstyle.org/en/latest/release_notes.html',
    'Sphinx': 'https://www.sphinx-doc.org/en/master/changes.html',
    'Babel': 'https://github.com/python-babel/babel/blob/master/CHANGES',
    'alabaster': 'https://alabaster.readthedocs.io/en/latest/changelog.html',
    'imagesize': 'https://github.com/shibukawa/imagesize_py/commits/master',
    'pytz': 'https://mm.icann.org/pipermail/tz-announce/',
    'sphinxcontrib-applehelp': 'https://www.sphinx-doc.org/en/master/changes.html',
    'sphinxcontrib-devhelp': 'https://www.sphinx-doc.org/en/master/changes.html',
    'sphinxcontrib-htmlhelp': 'https://www.sphinx-doc.org/en/master/changes.html',
    'sphinxcontrib-jsmath': 'https://www.sphinx-doc.org/en/master/changes.html',
    'sphinxcontrib-qthelp': 'https://www.sphinx-doc.org/en/master/changes.html',
    'sphinxcontrib-serializinghtml': 'https://www.sphinx-doc.org/en/master/changes.html',
    'jaraco.functools': 'https://github.com/jaraco/jaraco.functools/blob/master/CHANGES.rst',
    'parse': 'https://github.com/r1chardj0n3s/parse#potential-gotchas',
    'py': 'https://py.readthedocs.io/en/latest/changelog.html#changelog',
    'Pympler': 'https://github.com/pympler/pympler/blob/master/CHANGELOG.md',
    'pytest-mock': 'https://github.com/pytest-dev/pytest-mock/blob/master/CHANGELOG.rst',
    'pytest-qt': 'https://github.com/pytest-dev/pytest-qt/blob/master/CHANGELOG.rst',
    'pyinstaller': 'https://pyinstaller.readthedocs.io/en/stable/CHANGES.html',
    'pyinstaller-hooks-contrib': 'https://github.com/pyinstaller/pyinstaller-hooks-contrib/blob/master/CHANGELOG.rst',
    'pytest-benchmark': 'https://pytest-benchmark.readthedocs.io/en/stable/changelog.html',
    'typed-ast': 'https://github.com/python/typed_ast/commits/master',
    'docutils': 'https://docutils.sourceforge.io/RELEASE-NOTES.html',
    'bump2version': 'https://github.com/c4urself/bump2version/blob/master/CHANGELOG.md',
    'six': 'https://github.com/benjaminp/six/blob/master/CHANGES',
    'altgraph': 'https://github.com/ronaldoussoren/altgraph/blob/master/doc/changelog.rst',
    'urllib3': 'https://github.com/urllib3/urllib3/blob/master/CHANGES.rst',
    'lxml': 'https://lxml.de/index.html#old-versions',
    'jwcrypto': 'https://github.com/latchset/jwcrypto/commits/master',
    'wrapt': 'https://github.com/GrahamDumpleton/wrapt/blob/develop/docs/changes.rst',
    'pep517': 'https://github.com/pypa/pep517/blob/master/doc/changelog.rst',
    'cryptography': 'https://cryptography.io/en/latest/changelog.html',
    'toml': 'https://github.com/uiri/toml/releases',
    'PyQt5': 'https://www.riverbankcomputing.com/news',
    'PyQt5-Qt': 'https://www.riverbankcomputing.com/news',
    'PyQt5-Qt5': 'https://www.riverbankcomputing.com/news',
    'PyQtWebEngine': 'https://www.riverbankcomputing.com/news',
    'PyQtWebEngine-Qt': 'https://www.riverbankcomputing.com/news',
    'PyQtWebEngine-Qt5': 'https://www.riverbankcomputing.com/news',
    'PyQt-builder': 'https://www.riverbankcomputing.com/news',
    'PyQt5-sip': 'https://www.riverbankcomputing.com/news',
    'PyQt5-stubs': 'https://github.com/stlehmann/PyQt5-stubs/blob/master/CHANGELOG.md',
    'sip': 'https://www.riverbankcomputing.com/news',
    'Pygments': 'https://pygments.org/docs/changelog/',
    'vulture': 'https://github.com/jendrikseipp/vulture/blob/master/CHANGELOG.md',
    'distlib': 'https://bitbucket.org/pypa/distlib/src/master/CHANGES.rst',
    'py-cpuinfo': 'https://github.com/workhorsy/py-cpuinfo/blob/master/ChangeLog',
    'cheroot': 'https://cheroot.cherrypy.org/en/latest/history.html',
    'certifi': 'https://ccadb-public.secure.force.com/mozilla/IncludedCACertificateReport',
    'chardet': 'https://github.com/chardet/chardet/releases',
    'idna': 'https://github.com/kjd/idna/blob/master/HISTORY.rst',
    'tldextract': 'https://github.com/john-kurkowski/tldextract/blob/master/CHANGELOG.md',
    'typing-extensions': 'https://github.com/python/typing/commits/master/typing_extensions',
    'diff-cover': 'https://github.com/Bachmann1234/diff_cover/blob/master/CHANGELOG',
    'pytest-icdiff': 'https://github.com/hjwp/pytest-icdiff/blob/master/HISTORY.rst',
    'icdiff': 'https://github.com/jeffkaufman/icdiff/blob/master/ChangeLog',
    'pprintpp': 'https://github.com/wolever/pprintpp/blob/master/CHANGELOG.txt',
    'beautifulsoup4': 'https://bazaar.launchpad.net/~leonardr/beautifulsoup/bs4/view/head:/CHANGELOG',
    'check-manifest': 'https://github.com/mgedmin/check-manifest/blob/master/CHANGES.rst',
    'yamllint': 'https://github.com/adrienverge/yamllint/blob/master/CHANGELOG.rst',
    'pathspec': 'https://github.com/cpburnz/python-path-specification/blob/master/CHANGES.rst',
    'filelock': 'https://github.com/benediktschmitt/py-filelock/commits/master',
    'github3.py': 'https://github3py.readthedocs.io/en/master/release-notes/index.html',
    'manhole': 'https://github.com/ionelmc/python-manhole/blob/master/CHANGELOG.rst',
    'pycparser': 'https://github.com/eliben/pycparser/blob/master/CHANGES',
    'python-dateutil': 'https://dateutil.readthedocs.io/en/stable/changelog.html',
    'appdirs': 'https://github.com/ActiveState/appdirs/blob/master/CHANGES.rst',
    'pluggy': 'https://github.com/pytest-dev/pluggy/blob/master/CHANGELOG.rst',
    'inflect': 'https://github.com/jazzband/inflect/blob/master/CHANGES.rst',
    'jinja2-pluralize': 'https://github.com/audreyfeldroy/jinja2_pluralize/blob/master/HISTORY.rst',
    'mypy-extensions': 'https://github.com/python/mypy_extensions/commits/master',
    'pyroma': 'https://github.com/regebro/pyroma/blob/master/HISTORY.txt',
    'adblock': 'https://github.com/ArniDagur/python-adblock/blob/master/CHANGELOG.md',
    'importlib-resources': 'https://importlib-resources.readthedocs.io/en/latest/history.html',
    'importlib-metadata': 'https://github.com/python/importlib_metadata/blob/main/CHANGES.rst',
    'zipp': 'https://github.com/jaraco/zipp/blob/main/CHANGES.rst',
    'dataclasses': 'https://github.com/ericvsmith/dataclasses#release-history',
    'pip': 'https://pip.pypa.io/en/stable/news/',
    'wheel': 'https://wheel.readthedocs.io/en/stable/news.html',
    'setuptools': 'https://setuptools.readthedocs.io/en/latest/history.html',
    'future': 'https://python-future.org/whatsnew.html',
    'pefile': 'https://github.com/erocarrera/pefile/commits/master',
    'Deprecated': 'https://github.com/tantale/deprecated/blob/master/CHANGELOG.rst',
}


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


def run_pip(venv_dir, *args, quiet=False, **kwargs):
    """Run pip inside the virtualenv."""
    args = list(args)
    if quiet:
        args.insert(1, '-q')

    arg_str = ' '.join(str(arg) for arg in args)
    utils.print_col('venv$ pip {}'.format(arg_str), 'blue')

    venv_python = get_venv_python(venv_dir)
    return subprocess.run([venv_python, '-m', 'pip'] + args, check=True, **kwargs)


def init_venv(host_python, venv_dir, requirements, pre=False):
    """Initialize a new virtualenv and install the given packages."""
    with utils.gha_group('Creating virtualenv'):
        utils.print_col('$ python3 -m venv {}'.format(venv_dir), 'blue')
        subprocess.run([host_python, '-m', 'venv', venv_dir], check=True)

        run_pip(venv_dir, 'install', '-U', 'pip', quiet=not utils.ON_CI)
        run_pip(venv_dir, 'install', '-U', 'setuptools', 'wheel', quiet=not utils.ON_CI)

    install_command = ['install', '-r', requirements]
    if pre:
        install_command.append('--pre')

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

    def __init__(self, name):
        self.name = name
        self.old = None
        self.new = None
        if CHANGELOG_URLS.get(name):
            self.url = CHANGELOG_URLS[name]
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


def _get_changed_files():
    """Get a list of changed files via git."""
    changed_files = set()
    filenames = git_diff('--name-only')
    for filename in filenames:
        filename = filename.strip()
        filename = filename.replace('misc/requirements/requirements-', '')
        filename = filename.replace('.txt', '')
        changed_files.add(filename)

    return sorted(changed_files)


def parse_versioned_line(line):
    """Parse a requirements.txt line into name/version."""
    if '==' in line:
        if line[0] == '#':  # ignored dependency
            line = line[1:].strip()

        # Strip comments and pip environment markers
        line = line.rsplit('#', maxsplit=1)[0]
        line = line.split(';')[0].strip()

        name, version = line.split('==')
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
    for line in diff:
        if not line.startswith('-') and not line.startswith('+'):
            continue
        elif line.startswith('+++ ') or line.startswith('--- '):
            continue
        elif not line.strip():
            # Could be newline changes on Windows
            continue
        elif line[1:].startswith('# This file is automatically'):
            # Could be newline changes on Windows
            continue

        name, version = parse_versioned_line(line[1:])

        if name not in changes_dict:
            changes_dict[name] = Change(name)

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
            '| Requirement | old | new |',
            '|-------------|-----|-----|',
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
                  pre=comments['pre'])
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

    host_python = get_host_python(name)
    with tempfile.TemporaryDirectory() as tmpdir:
        init_venv(host_python, tmpdir, outfile)


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
