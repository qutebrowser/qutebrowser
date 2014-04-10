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

"""Fixer to set QT_HARFBUZZ variable.

In its own file so it doesn't include any Qt stuff, because if it did, it
wouldn't work.
"""

import os
import sys


def fix():
    """Fix harfbuzz issues.

    This switches to an older (but more stable) harfbuzz font rendering engine
    instead of using the system wide one.

    This fixes crashes on various sites.
    See https://bugreports.qt-project.org/browse/QTBUG-36099
    """
    if sys.platform.startswith('linux'):
        # Switch to old but stable font rendering engine
        os.environ['QT_HARFBUZZ'] = 'old'
