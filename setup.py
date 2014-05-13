#!/usr/bin/python
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


from scripts.setupdata import setupdata

from scripts.ez_setup import use_setuptools
use_setuptools()
from setuptools import setup, find_packages


setup(
    packages=find_packages(exclude=['qutebrowser.test']),
    include_package_data=True,
    package_data={'qutebrowser': ['html/*']},
    entry_points={'gui_scripts': ['qutebrowser = qutebrowser.__main__:main']},
    test_suite='qutebrowser.test',
    zip_safe=True,
    **setupdata
)
