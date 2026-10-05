"""Balanced mind-map layout (XMind's default "Mind Map" structure) and spatial navigation.

Pure Python so it can be tested without Qt: topic sizes come from a ``measure`` callback.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import IntEnum
from typing import Literal

from .model import Topic

ROOT_H_GAP = 56
H_GAP = 36
V_GAP = 14

Measure = Callable[[Topic], tuple[float, float]]


class Side(IntEnum):
    """Which side of the root a topic sits on; the value is the x direction away from the root."""

    LEFT = -1
    CENTER = 0  # the root
    RIGHT = 1

    @property
    def outward(self) -> Side:
        """Direction to draw things beside the topic; the root uses the right."""
        return Side.RIGHT if self is Side.CENTER else self


@dataclass
class Placement:
    x: float  # center
    y: float  # center
    w: float
    h: float
    side: Side


def split_sides(count: int) -> int:
    """Number of main topics placed on the right; the rest go left."""
    return (count + 1) // 2


def layout(root: Topic, measure: Measure) -> dict[Topic, Placement]:
    sizes: dict[Topic, tuple[float, float]] = {}
    heights: dict[Topic, float] = {}

    def size(t: Topic) -> tuple[float, float]:
        if t not in sizes:
            sizes[t] = measure(t)
        return sizes[t]

    def visible_children(t: Topic) -> list[Topic]:
        return [] if t.collapsed else t.children

    def stack_height(topics: list[Topic]) -> float:
        if not topics:
            return 0.0
        return sum(subtree_height(c) for c in topics) + V_GAP * (len(topics) - 1)

    def subtree_height(t: Topic) -> float:
        if t not in heights:
            heights[t] = max(size(t)[1], stack_height(visible_children(t)))
        return heights[t]

    out: dict[Topic, Placement] = {}

    def place_stack(parent: Topic, kids: list[Topic], side: Side, gap: float) -> None:
        p = out[parent]
        y = p.y - stack_height(kids) / 2
        for child in kids:
            cw, _ = size(child)
            sh = subtree_height(child)
            place(child, p.x + side * (p.w / 2 + gap + cw / 2), y + sh / 2, side)
            y += sh + V_GAP

    def place(t: Topic, x: float, y: float, side: Side) -> None:
        w, h = size(t)
        out[t] = Placement(x, y, w, h, side)
        place_stack(t, visible_children(t), side, H_GAP)

    w, h = size(root)
    out[root] = Placement(0.0, 0.0, w, h, Side.CENTER)
    kids = visible_children(root)
    n_right = split_sides(len(kids))
    place_stack(root, kids[:n_right], Side.RIGHT, ROOT_H_GAP)
    place_stack(root, kids[n_right:], Side.LEFT, ROOT_H_GAP)
    return out


def neighbor(topic: Topic, direction: str, placements: dict[Topic, Placement]) -> Topic | None:
    """Topic reached by an arrow key, following XMind's conventions.

    Left/Right move toward/away from the centre: into the child nearest vertically,
    or back out to the parent. Up/Down move between siblings on the same side and
    fall back to the nearest visible topic at the same depth.
    """
    p = placements[topic]
    if direction in ("left", "right"):
        d = Side.RIGHT if direction == "right" else Side.LEFT
        if topic.parent is not None and p.side == -d:
            return topic.parent
        cands = [c for c in topic.children if c in placements and placements[c].side == d]
        return min(cands, key=lambda c: abs(placements[c].y - p.y)) if cands else None

    if direction not in ("up", "down"):
        raise ValueError(direction)
    if topic.parent is None:
        return None
    d = 1 if direction == "down" else -1
    sibs = [s for s in topic.parent.children if s in placements and placements[s].side == p.side]
    j = sibs.index(topic) + d
    if 0 <= j < len(sibs):
        return sibs[j]
    depth = topic.depth
    cands = [
        q
        for q, qp in placements.items()
        if q is not topic and qp.side == p.side and q.depth == depth and (qp.y - p.y) * d > 0
    ]
    return min(cands, key=lambda q: abs(placements[q].y - p.y)) if cands else None


DROP_EDGE = 0.3  # top/bottom fraction of a topic that means "insert beside" rather than "make child"
DROP_SLOP = 6


@dataclass
class DropTarget:
    parent: Topic
    index: int
    anchor: Topic  # the topic under the cursor
    kind: Literal["child", "before", "after"]


def drop_target(
    dragged: Topic | Sequence[Topic], x: float, y: float, placements: dict[Topic, Placement]
) -> DropTarget | None:
    """Where ``dragged`` (one topic or several) would land if dropped at scene point (x, y)."""
    group = [dragged] if isinstance(dragged, Topic) else dragged
    for t, p in placements.items():
        if any(t is d or d.is_ancestor_of(t) for d in group):
            continue
        if abs(x - p.x) > p.w / 2 + DROP_SLOP or abs(y - p.y) > p.h / 2 + DROP_SLOP:
            continue
        if t.parent is not None:
            rel = (y - (p.y - p.h / 2)) / p.h
            if rel < DROP_EDGE:
                return DropTarget(t.parent, t.index, t, "before")
            if rel > 1 - DROP_EDGE:
                return DropTarget(t.parent, t.index + 1, t, "after")
        return DropTarget(t, len(t.children), t, "child")
    return None
