# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later


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
