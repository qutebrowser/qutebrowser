# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Hypothesis tests for qutebrowser.misc.split."""

import pytest
import hypothesis
from hypothesis import strategies

from qutebrowser.misc import split


@pytest.mark.parametrize('keep', [True, False])
@hypothesis.given(strategies.text())
def test_split(keep, s):
    split.split(s, keep=keep)


@pytest.mark.parametrize('keep', [True, False])
@pytest.mark.parametrize('maxsplit', [None, 0, 1])
@hypothesis.given(strategies.text())
def test_simple_split(keep, maxsplit, s):
    split.simple_split(s, keep=keep, maxsplit=maxsplit)
