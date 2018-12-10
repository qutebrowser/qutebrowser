# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Loader for qutebrowser extensions."""

import pkgutil

from qutebrowser import components
from qutebrowser.utils import log


def load_components() -> None:
    """Load everything from qutebrowser.components."""
    for info in pkgutil.walk_packages(components.__path__):
        if info.ispkg:
            continue
        log.extensions.debug("Importing {}".format(info.name))
        loader = info.module_finder.find_module(info.name)
        loader.load_module(info.name)
