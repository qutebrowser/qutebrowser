#!/usr/bin/python

# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""setuptools installer script for qutebrowser"""

import os
import os.path

from scripts.setupcommon import setupdata, write_git_file

from scripts.ez_setup import use_setuptools
use_setuptools()
from setuptools import setup, find_packages


try:
    BASEDIR = os.path.dirname(os.path.realpath(__file__))
except NameError:
    BASEDIR = None


try:
    write_git_file()
    setup(
        packages=find_packages(exclude=['qutebrowser.test']),
        include_package_data=True,
        package_data={'qutebrowser': ['html/*', 'git-commit-id']},
        entry_points={'gui_scripts':
                      ['qutebrowser = qutebrowser.qutebrowser:main']},
        test_suite='qutebrowser.test',
        zip_safe=True,
        extras_require={'nice-debugging': ['colorlog', 'colorama', 'ipdb']},
        **setupdata
    )
finally:
    if BASEDIR is not None:
        path = os.path.join(BASEDIR, 'qutebrowser', 'git-commit-id')
        if os.path.exists(path):
            os.remove(path)
