# SPDX-FileCopyrightText: Vilhelm Engström <vilhelm.engstrom@tuta.io>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Bidirectional itertools.cycle-like adapter."""

from collections.abc import Sequence
from typing import Generic, TypeVar

_T = TypeVar("_T")


class BidirectionalCycle(Generic[_T]):

    """Simple adapter inspired by itertools.cycle allowing bidirectional iteration.

    Calling :func:`next` on an instance yields the next item in the cycle. The
    direction is determined by :attr:`backward`.

    .. code-block:: python

        cycle = BidrectionalCycle[str](['a', 'b', 'c', 'd'], backward=False)

        next(cycle)  # a
        next(cycle)  # b

        cycle.backward = True
        next(cycle)  # a
        next(cycle)  # d
        next(cycle)  # c
        next(cycle)  # b
        next(cycle)  # a
        next(cycle)  # d

        cycle.backward = False
        next(cycle)  # a
        # etc.
    """

    def __init__(self, items: Sequence[_T], *, backward: bool = False) -> None:
        self._items = items
        self._idx = 0 if backward else len(self._items) - 1
        self._backward = backward

    @property
    def backward(self) -> bool:
        """Check whether the current direction is backwards."""
        return self._backward

    @backward.setter
    def backward(self, backward: bool) -> None:
        """Set iteration direction.

        :param backward: `True` to enabled backward iteration, `False` to disable
        :type backward: bool
        """
        assert isinstance(backward, bool)
        self._backward = backward

    def _next_forward(self) -> _T:
        """Get the next item and advance adapter index."""
        self._idx = (self._idx + 1) % len(self._items)
        return self._items[self._idx]

    def _next_backward(self) -> _T:
        """Revert adapter index and get the last item."""
        self._idx -= 1
        if self._idx < 0:
            self._idx = len(self._items) - 1

        return self._items[self._idx]

    def __next__(self) -> _T:
        """Get then next item."""
        if self._backward:
            return self._next_backward()

        return self._next_forward()
