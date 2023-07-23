#!/usr/bin/env python3

# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""setuptools installer script for qutebrowser."""

import re
import ast
import os
import os.path

from scripts import setupcommon as common

import setuptools


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
        packages=setuptools.find_namespace_packages(include=['qutebrowser',
                                                             'qutebrowser.*']),
        include_package_data=True,
        entry_points={'gui_scripts':
                      ['qutebrowser = qutebrowser.qutebrowser:main']},
        zip_safe=True,
        install_requires=['jinja2', 'PyYAML',
                          'importlib_resources>=1.1.0; python_version < "3.9"'],
        python_requires='>=3.8',
        name='qutebrowser',
        version=_get_constant('version'),
        description=_get_constant('description'),
        long_description=read_file('README.asciidoc'),
        long_description_content_type='text/plain',
        url='https://www.qutebrowser.org/',
        author=_get_constant('author'),
        author_email=_get_constant('email'),
        license=_get_constant('license'),
        classifiers=[
            'Development Status :: 5 - Production/Stable',
            'Environment :: X11 Applications :: Qt',
            'Intended Audience :: End Users/Desktop',
            'License :: OSI Approved :: GNU General Public License v3 or later '
                '(GPLv3+)',
            'Natural Language :: English',
            'Operating System :: Microsoft :: Windows',
            'Operating System :: POSIX :: Linux',
            'Operating System :: MacOS',
            'Operating System :: POSIX :: BSD',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.8',
            'Programming Language :: Python :: 3.9',
            'Programming Language :: Python :: 3.10',
            'Programming Language :: Python :: 3.11',
            'Topic :: Internet',
            'Topic :: Internet :: WWW/HTTP',
            'Topic :: Internet :: WWW/HTTP :: Browsers',
        ],
        keywords='pyqt browser web qt webkit qtwebkit qtwebengine',
    )
finally:
    if BASEDIR is not None:
        path = os.path.join(BASEDIR, 'qutebrowser', 'git-commit-id')
        if os.path.exists(path):
            os.remove(path)
