import collections
import math
from typing import Dict, Iterable, List, Set, Tuple

from PyQt5.QtCore import QPoint, QRect
from PyQt5.QtWidgets import QLabel

from qutebrowser.utils import log


NUM_ITERATIONS = 10

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
    '''
    Suppose we tile the viewport with cells of shape max_width x max_height.
    Then `self._lookup` maps (i,j) to set of labels that intersect cell (i, j).

    alternatives: R-tree, quadtree

    This could be modified slightly due to the fact that we only care about
    overlaps of at least a certain amount.
    '''

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
        for corner in _corners(label):
            self._lookup[self._cell_index(corner)].add(label)
    def deregister(self, label: QLabel) -> None:
        for corner in _corners(label):
            self._lookup[self._cell_index(corner)].difference_update([label])
    def overlappings(self, label: QLabel) -> Iterable[QLabel]:
        cands = set()
        for corner in _corners(label):
            cands.update(self._lookup[self._cell_index(corner)])
        cands.difference_update([label])
        return [
            cand for cand in cands
            if _overlap(cand.geometry(), label.geometry())
        ]

def adjust_positions(labels: List[QLabel]) -> None:
    '''
    TODO:
    draw lines to where the element is if the label ends up far away?
    timeout?
    compute max allowed overlap using padding information?
    delint, refactor, tests (automatic and manual)
    '''
    max_width = max(label.width() for label in labels)
    max_height = max(label.height() for label in labels)

    # arrange labels at the same position in a diagonal
    xy2labels = collections.defaultdict(list)
    for label in labels:
        xy2labels[(label.pos().x(), label.pos().y())].append(label)
    for labels_here in xy2labels.values():
        for i, label_here in enumerate(labels_here):
            push = i * 4/5 * max_height * QPoint(1, 1)
            push = _to_viewport(
                label_here.geometry(), push, label_here.parent().geometry())
            label_here.move(label_here.pos() + push)

    # push labels away from each other if they're overlapping
    overlap_lookup = OverlapLookup(labels, max_width, max_height)
    push_size = max_height/6.5
    max_overlap = max_height/5
    for _ in range(NUM_ITERATIONS):
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
                overlap_lookup.deregister(label)
                label.move(label.pos() + agg_push)
                overlap_lookup.register(label)
