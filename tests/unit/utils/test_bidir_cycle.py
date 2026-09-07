# SPDX-FileCopyrightText: Vilhelm Engström <vilhelm.engstrom@tuta.io>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.utils.bidir_cycle."""

import pytest

from qutebrowser.utils.bidir_cycle import BidirectionalCycle


@pytest.mark.parametrize('seq', [['a', 'b', 'c', 'd'], list(range(33))])
def test_foward_iteration(seq: list[str] | list[int]) -> None:
    cycle = BidirectionalCycle[type(seq[0])](seq, backward=False)

    for item in seq:
        assert next(cycle) == item

    # Verify wrapping
    assert next(cycle) == seq[0]
    assert next(cycle) == seq[1]


@pytest.mark.parametrize('seq', [['a', 'b', 'c', 'd', 'E'], list(range(112))])
def test_backward_iteration(seq: list[str] | list[int]) -> None:
    cycle = BidirectionalCycle[type(seq[0])](seq, backward=True)

    for item in reversed(seq):
        assert next(cycle) == item

    # Verify wrapping
    assert next(cycle) == seq[-1]
    assert next(cycle) == seq[-2]


@pytest.mark.parametrize('seq', [['a', 'b', 'c', 'd', 'E'], list(range(23))])
def test_mixed_iteration(seq: list[str] | list[int]) -> None:
    cycle = BidirectionalCycle[type(seq[0])](seq, backward=False)

    assert next(cycle) == seq[0]
    assert next(cycle) == seq[1]

    cycle.backward = True
    assert next(cycle) == seq[0]
    assert next(cycle) == seq[-1]
    assert next(cycle) == seq[-2]

    cycle.backward = False
    assert next(cycle) == seq[-1]
    assert next(cycle) == seq[0]

    cycle.backward = True
    assert next(cycle) == seq[-1]

    cycle.backward = False
    assert next(cycle) == seq[0]
