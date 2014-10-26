#!/usr/bin/env python3
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

"""Update 3rd-party files (currently only ez_setup.py)."""

import sys
import os
import os.path
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

from scripts import utils

utils.change_cwd()
urllib.request.urlretrieve(
    'https://bitbucket.org/pypa/setuptools/raw/bootstrap/ez_setup.py',
    'scripts/ez_setup.py')
