# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

import re

import pytest

from scripts.dev.ci import problemmatchers


@pytest.mark.parametrize('matcher_name', list(problemmatchers.MATCHERS))
def test_patterns(matcher_name):
    """Make sure all regexps are valid.

    They aren't actually Python syntax, but hopefully close enough to it to compile with
    Python's re anyways.
    """
    for matcher in problemmatchers.MATCHERS[matcher_name]:
        for pattern in matcher['pattern']:
            regexp = pattern['regexp']
            print(regexp)
            re.compile(regexp)
