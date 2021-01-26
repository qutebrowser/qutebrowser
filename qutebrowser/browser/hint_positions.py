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
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Arranging hints so they don't overlap."""

import collections
import math
import time
from typing import Dict, Iterable, List, Set, Tuple

from PyQt5.QtCore import QPoint, QRect
from PyQt5.QtWidgets import QLabel

from qutebrowser.config import config
from qutebrowser.utils import log

MAX_OVERLAP_FACTOR = 1 / 5  # 1/5 works well with defaults
NUM_ITERATIONS = 15  # with hints.mode = word 10 isn't enough sometimes
PUSH_SIZE_FACTOR = 1 / 6.5
TIMEOUT_SECS = 10  # prevent poor worst-case performance


def _overlap(r1: QRect, r2: QRect) -> bool:
    hor_overlap = max(0,
        (min(r1.right(), r2.right()) - max(r1.left(), r2.left()))
    )
    vert_overlap = max(0,
        (min(r1.bottom(), r2.bottom()) - max(r1.top(), r2.top()))
    )
    return hor_overlap > 0 or vert_overlap > 0


def _min_overlap(r1: QRect, r2: QRect) -> int:
    hor_overlap = max(0,
        (min(r1.right(), r2.right()) - max(r1.left(), r2.left()))
    )
    vert_overlap = max(0,
        (min(r1.bottom(), r2.bottom()) - max(r1.top(), r2.top()))
    )
    return min(hor_overlap, vert_overlap)


def _length(p: QPoint) -> float:
    return math.sqrt(QPoint.dotProduct(p, p))


def _to_viewport(rect: QRect, push: QPoint, bounds: QRect) -> QPoint:
    push.setX(max(push.x(), bounds.left() - rect.left()))
    push.setX(min(push.x(), bounds.right() - rect.right()))
    push.setY(max(push.y(), bounds.top() - rect.top()))
    push.setY(min(push.y(), bounds.bottom() - rect.bottom()))
    return push


def _corners(label: QLabel) -> List[QPoint]:
    return [
        label.geometry().topLeft(), label.geometry().topRight(),
        label.geometry().bottomLeft(), label.geometry().bottomRight(),
    ]


class OverlapLookup:
    """Hold a collection of labels and compute overlaps.

    Suppose we tile the viewport with cells of shape max_width x max_height.
    Then `self._lookup` maps (i,j) to set of labels that intersect cell (i, j).

    alternatives: R-tree, quadtree

    This could be modified slightly due to the fact that we only care about
    overlaps of at least a certain amount.
    """

    def __init__(
        self,
        labels: Iterable[QLabel],
        max_width: int,
        max_height: int,
    ):
        self._lookup: Dict[
            Tuple[int, int], Set[QLabel]
        ] = collections.defaultdict(set)
        self._max_width = max_width
        self._max_height = max_height
        for label in labels:
            self.register(label)

    def _cell_index(self, p: QPoint) -> Tuple[int, int]:
        return (
            math.floor(p.x() / self._max_width),
            math.floor(p.y() / self._max_height),
        )

    def register(self, label: QLabel) -> None:
        """Add a label."""
        for corner in _corners(label):
            self._lookup[self._cell_index(corner)].add(label)

    def deregister(self, label: QLabel) -> None:
        """Remove a label."""
        for corner in _corners(label):
            self._lookup[self._cell_index(corner)].difference_update([label])

    def overlappings(self, label: QLabel) -> Iterable[QLabel]:
        """Get labels that overlap with `label`."""
        cands = set()
        for corner in _corners(label):
            cands.update(self._lookup[self._cell_index(corner)])
        cands.difference_update([label])
        return [
            cand for cand in cands
            if _overlap(cand.geometry(), label.geometry())
        ]


def adjust_positions(labels: Tuple[QLabel, ...]) -> None:
    """TODO.

    put the whole thing behind a boolean setting?
    make MAX_OVERLAP_FACTOR a setting unless there's a way to compute what it
        should be given hint font size, border, and padding
    draw lines to where the element is if the label ends up far away?
    delint, refactor, tests (automatic and manual)
    """
    max_width = max(label.width() for label in labels)
    max_height = max(label.height() for label in labels)

    # arrange labels at the same position in a diagonal
    xy2labels = collections.defaultdict(list)
    for label in labels:
        xy2labels[(label.pos().x(), label.pos().y())].append(label)
    for labels_here in xy2labels.values():
        for i, label_here in enumerate(labels_here):
            push = i * (1 - MAX_OVERLAP_FACTOR) * max_height * QPoint(1, 1)
            push = _to_viewport(
                label_here.geometry(), push, label_here.parent().geometry())
            label_here.move(label_here.pos() + push)

    # push labels away from each other if they're overlapping
    overlap_lookup = OverlapLookup(labels, max_width, max_height)
    push_size = max_height * PUSH_SIZE_FACTOR
    max_overlap = max_height * MAX_OVERLAP_FACTOR
    start_time = time.time()
    for _ in range(NUM_ITERATIONS):
        something_pushed = False
        for label in labels:
            agg_push = QPoint(0, 0)
            for overlapping in overlap_lookup.overlappings(label):
                disp = label.pos() - overlapping.pos()
                if not _length(disp):
                    disp = QPoint(1, 1)
                overlap = _min_overlap(label.geometry(), overlapping.geometry())
                if overlap > max_overlap:
                    agg_push += disp * (push_size / _length(disp))
            agg_push = _to_viewport(
                label.geometry(), agg_push, label.parent().geometry())
            if _length(agg_push):
                something_pushed = True
                overlap_lookup.deregister(label)
                label.move(label.pos() + agg_push)
                overlap_lookup.register(label)
            if time.time() - start_time > TIMEOUT_SECS:
                return
        if not something_pushed: return
