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

"""A keyboard-driven, vim-like browser based on PyQt5."""

import os.path

__author__ = "Florian Bruhin"
__copyright__ = "Copyright 2014-2020 Florian Bruhin (The Compiler)"
__license__ = "GPL"
__maintainer__ = __author__
__email__ = "mail@qutebrowser.org"
__version__ = "1.12.0"
__version_info__ = tuple(int(part) for part in __version__.split('.'))
__description__ = "A keyboard-driven, vim-like browser based on PyQt5."

basedir = os.path.dirname(os.path.realpath(__file__))
