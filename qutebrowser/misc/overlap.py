# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Work with overlapping widgets."""

import collections
import math
from typing import Dict, Iterable, List, Sequence, Set, Tuple

from PyQt5.QtCore import QPoint, QRect
from PyQt5.QtWidgets import QWidget


def _overlap(r1: QRect, r2: QRect) -> bool:
    hor_overlap = max(0,
        (min(r1.right(), r2.right()) - max(r1.left(), r2.left()))
    )
    vert_overlap = max(0,
        (min(r1.bottom(), r2.bottom()) - max(r1.top(), r2.top()))
    )
    return hor_overlap > 0 and vert_overlap > 0


def _corners(widget: QWidget) -> List[QPoint]:
    return [
        widget.geometry().topLeft(), widget.geometry().topRight(),
        widget.geometry().bottomLeft(), widget.geometry().bottomRight(),
    ]


class OverlapLookup:
    """Hold a collection of widgets and compute overlaps.

    Suppose we tile the viewport with cells of shape max_width x max_height.
    If a widget intersects a cell, at least one of its corners are in the cell.
    Then `self._lookup` maps (i,j) to set of widgets that intersect cell (i,j).
    If widget1 intersects widget2 then widget2 must intersect at least one
    cell that widget1 intersects; this allows us to avoid checking every pair
    of widgets to see if they intersect.

    alternatives: R-tree, quadtree
    """

    def __init__(self, widgets: Iterable[QWidget]):
        self._lookup: Dict[
            Tuple[int, int], Set[QWidget]
        ] = collections.defaultdict(set)
        self._max_width = max(widget.width() for widget in widgets)
        self._max_height = max(widget.height() for widget in widgets)
        for widget in widgets:
            self.register(widget)

    def _cell_index(self, p: QPoint) -> Tuple[int, int]:
        return (
            math.floor(p.x() / self._max_width),
            math.floor(p.y() / self._max_height),
        )

    def register(self, widget: QWidget) -> None:
        """Add a widget."""
        for corner in _corners(widget):
            self._lookup[self._cell_index(corner)].add(widget)

    def deregister(self, widget: QWidget) -> None:
        """Remove a widget."""
        for corner in _corners(widget):
            self._lookup[self._cell_index(corner)].difference_update([widget])

    def overlappings(self, widget: QWidget) -> Iterable[QWidget]:
        """Get widgets that overlap with `widget`."""
        cands = set()
        for corner in _corners(widget):
            cands.update(self._lookup[self._cell_index(corner)])
        cands.difference_update([widget])
        return [
            cand for cand in cands
            if _overlap(cand.geometry(), widget.geometry())
        ]


def cycle(widgets: Sequence[QWidget], reverse: bool = False) -> None:
    """Rotate the order of overlapping widgets.

    Args:
        widgets: List of widgets to consider. Must be siblings.
        reverse: Cycle in reverse direction.
    """
    if not widgets:
        return

    children = widgets[0].parent().children()
    widget_set = {widget for widget in widgets if widget.isVisible()}
    overlap_lookup = OverlapLookup(widget_set)
    # widget1 is above widget2 iff widget1 comes later in parent().children()
    widgets_in_order = [child for child in children if child in widget_set]
    if reverse:
        widgets_in_order = list(reversed(widgets_in_order))

    to_move: Set[QWidget] = set()
    excluded: Set[QWidget] = set()
    for widget in widgets_in_order:
        if widget in excluded:
            continue
        assert isinstance(widget, QWidget)
        overlappings = overlap_lookup.overlappings(widget)
        if overlappings:
            to_move.add(widget)
            excluded.update(overlappings)

    if reverse:
        lowest = next(
            child for child in children
            if child in widget_set and child not in to_move
        )
        assert isinstance(lowest, QWidget)
        for widget in to_move:
            widget.stackUnder(lowest)
    else:
        for widget in to_move:
            widget.raise_()
