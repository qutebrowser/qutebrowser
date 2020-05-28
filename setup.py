#!/usr/bin/env python3

# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
        packages=setuptools.find_packages(exclude=['scripts', 'scripts.*']),
        include_package_data=True,
        entry_points={'gui_scripts':
                      ['qutebrowser = qutebrowser.qutebrowser:main']},
        zip_safe=True,
        install_requires=['pypeg2', 'jinja2', 'pygments', 'PyYAML', 'attrs'],
        python_requires='>=3.5',
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
            'Development Status :: 4 - Beta',
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
            'Programming Language :: Python :: 3.5',
            'Programming Language :: Python :: 3.6',
            'Programming Language :: Python :: 3.7',
            'Programming Language :: Python :: 3.8',
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
