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

"""Misc. utility commands exposed to the user."""

import types
import functools


from PyQt5.QtCore import QCoreApplication

from qutebrowser.utils import log, objreg
from qutebrowser.commands import cmdutils
from qutebrowser.config import style


@cmdutils.register(debug=True)
def debug_crash(typ: ('exception', 'segfault')='exception'):
    """Crash for debugging purposes.

    Args:
        typ: either 'exception' or 'segfault'.

    Raises:
        raises Exception when typ is not segfault.
        segfaults when typ is (you don't say...)
    """
    if typ == 'segfault':
        # From python's Lib/test/crashers/bogus_code_obj.py
        co = types.CodeType(0, 0, 0, 0, 0, b'\x04\x71\x00\x00', (), (), (),
                            '', '', 1, b'')
        exec(co)  # pylint: disable=exec-used
        raise Exception("Segfault failed (wat.)")
    else:
        raise Exception("Forced crash")


@cmdutils.register(debug=True)
def debug_all_objects():
    """Print a list of  all objects to the debug log."""
    s = QCoreApplication.instance().get_all_objects()
    log.misc.debug(s)


@cmdutils.register(debug=True)
def debug_cache_stats():
    """Print LRU cache stats."""
    config_info = objreg.get('config').get.cache_info()
    style_info = style.get_stylesheet.cache_info()
    log.misc.debug('config: {}'.format(config_info))
    log.misc.debug('style: {}'.format(style_info))


@cmdutils.register(debug=True)
def debug_console():
    """Show the debugging console."""
    objreg.get('debug-console').show()
