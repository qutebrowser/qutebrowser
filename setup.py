#!/usr/bin/env python3

# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""setuptools installer script for qutebrowser."""

import re
import ast
import os
import os.path
import sys

# Add repo root to path so we can import scripts. Prior to PEP517 support this
# was the default behavior for setuptools.
# https://github.com/pypa/setuptools/issues/3939#issuecomment-1573619382
# > If users want to import local modules they are recommended to explicitly add the current directory to sys.path at the top of setup.py.
sys.path.append(".")

from scripts import setupcommon as common

import setuptools

# Dynamic stuff in setup.py:
# * common.write_git_file (and then cleaning it up)
#   * should be shipped with qutebrowser
#   * read in version, used in pyinstaller
#   * couldn't find any good options for this. There are plugins like
#   setuptools-scm and hatch-vcs that can include git data in the version. But
#   we want a clean version but to include git info about the build at
#   runtime. This really seems like it needs a build hook, which for
#   setuptools I think is setup.py (there are entry points you can set, but
#   they say something about the application needing to be installed before
#   they can run, not sure if that means they aren't usable or what). I think
#   hatch has build hooks you can specify in pyproject.toml
# * long_description=read_file('README.asciidoc')
#   * dynamic `readme` key in setuptools
#   * but docs say to just put the file name anyhow? https://packaging.python.org/en/latest/guides/writing-pyproject-toml/#readme
# * version=_get_constant('version'),
#   * dynamic in setuptools
# * description=_get_constant('description'),
#   * dynamic option in setuptools
# * author=_get_constant('author'),
# * author_email=_get_constant('email'),
#   * both not dynamic and don't change much, duplicate or move
# * license=_get_constant('license'),
#   * not dynamic, it's also not used anywhere else and doesn't change often
#   * just duplicate it and leave a comment or move it completely
#

# Args to setup()
# https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html#setuptools-specific-configuration
# * packages=setuptools.find_namespace_packages(include=['qutebrowser', 'qutebrowser.*']),
#    * [tool.setuptools.packages.find]
# * include_package_data=True,
#    * true by default when using pyproject.toml
# * entry_points={'gui_scripts': ['qutebrowser = qutebrowser.qutebrowser:main']},
#    * https://setuptools.pypa.io/en/latest/userguide/entry_point.html#gui-scripts
# * zip_safe=True,
#    * obsolete


try:
    BASEDIR = os.path.dirname(os.path.realpath(__file__))
except NameError:
    BASEDIR = None


def read_file(name):
    """Get the string contained in the file named name."""
    with common.open_file(name, 'r', encoding='utf-8') as f:
        return f.read()


def _get_constant(name):
    """Read a __magic__ constant from qutebrowser/__init__.py.

    We don't import qutebrowser here because it can go wrong for multiple
    reasons. Instead we use re/ast to get the value directly from the source
    file.

    Args:
        name: The name of the argument to get.

    Return:
        The value of the argument.
    """
    field_re = re.compile(r'__{}__\s+=\s+(.*)'.format(re.escape(name)))
    path = os.path.join(BASEDIR, 'qutebrowser', '__init__.py')
    line = field_re.search(read_file(path)).group(1)
    value = ast.literal_eval(line)
    return value


try:
    common.write_git_file()
    setuptools.setup(
        #packages=setuptools.find_namespace_packages(include=['qutebrowser',
        #                                                     'qutebrowser.*']),
        #include_package_data=True,
        #entry_points={'gui_scripts':
        #              ['qutebrowser = qutebrowser.qutebrowser:main']},
        #zip_safe=True,

        #install_requires=['jinja2', 'PyYAML'],
        #python_requires='>=3.9',
        #name='qutebrowser',
        #version=_get_constant('version'),
        #description=_get_constant('description'),
        #long_description=read_file('README.asciidoc'),
        #long_description_content_type='text/plain',
        #url='https://www.qutebrowser.org/',
        #author=_get_constant('author'),
        #author_email=_get_constant('email'),
        #license=_get_constant('license'),
        #classifiers=[
        #    'Development Status :: 5 - Production/Stable',
        #    'Environment :: X11 Applications :: Qt',
        #    'Intended Audience :: End Users/Desktop',
        #    'Natural Language :: English',
        #    'Operating System :: Microsoft :: Windows',
        #    'Operating System :: POSIX :: Linux',
        #    'Operating System :: MacOS',
        #    'Operating System :: POSIX :: BSD',
        #    'Programming Language :: Python :: 3',
        #    'Programming Language :: Python :: 3.9',
        #    'Programming Language :: Python :: 3.10',
        #    'Programming Language :: Python :: 3.11',
        #    'Programming Language :: Python :: 3.12',
        #    'Programming Language :: Python :: 3.13',
        #    'Topic :: Internet',
        #    'Topic :: Internet :: WWW/HTTP',
        #    'Topic :: Internet :: WWW/HTTP :: Browsers',
        #],
        #keywords='pyqt browser web qt webkit qtwebkit qtwebengine',
    )
finally:
    if BASEDIR is not None:
        path = os.path.join(BASEDIR, 'qutebrowser', 'git-commit-id')
        if os.path.exists(path):
            os.remove(path)
