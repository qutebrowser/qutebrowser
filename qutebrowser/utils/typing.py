# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Wrapper for Python 3.5's typing module.

This wrapper is needed as both Python 3.5 and typing for PyPI isn't commonly
packaged yet. As we don't actually need anything from the typing module at
runtime, we instead mock the typing classes (using objects to make things
easier) so the typing module isn't a hard dependency.
"""

try:
    from typing import Union
except ImportError:

    class TypingFake:

        def __getitem__(self, _item):
            pass

    Union = TypingFake()
