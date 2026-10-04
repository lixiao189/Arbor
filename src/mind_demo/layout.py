"""Balanced mind-map layout (XMind's default "Mind Map" structure) and spatial navigation.

Pure Python so it can be tested without Qt: topic sizes come from a ``measure`` callback.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .model import Topic

ROOT_H_GAP = 56
H_GAP = 36
V_GAP = 14

Measure = Callable[[Topic], tuple[float, float]]


@dataclass
class Placement:
    x: float  # center
    y: float  # center
    w: float
    h: float
    side: int  # +1 right, -1 left, 0 for the root


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

    def place_stack(parent: Topic, kids: list[Topic], side: int, gap: float) -> None:
        p = out[parent]
        y = p.y - stack_height(kids) / 2
        for child in kids:
            cw, _ = size(child)
            sh = subtree_height(child)
            place(child, p.x + side * (p.w / 2 + gap + cw / 2), y + sh / 2, side)
            y += sh + V_GAP

    def place(t: Topic, x: float, y: float, side: int) -> None:
        w, h = size(t)
        out[t] = Placement(x, y, w, h, side)
        place_stack(t, visible_children(t), side, H_GAP)

    w, h = size(root)
    out[root] = Placement(0.0, 0.0, w, h, 0)
    kids = visible_children(root)
    n_right = split_sides(len(kids))
    place_stack(root, kids[:n_right], +1, ROOT_H_GAP)
    place_stack(root, kids[n_right:], -1, ROOT_H_GAP)
    return out


def neighbor(topic: Topic, direction: str, placements: dict[Topic, Placement]) -> Topic | None:
    """Topic reached by an arrow key, following XMind's conventions.

    Left/Right move toward/away from the centre: into the child nearest vertically,
    or back out to the parent. Up/Down move between siblings on the same side and
    fall back to the nearest visible topic at the same depth.
    """
    p = placements[topic]
    if direction in ("left", "right"):
        d = 1 if direction == "right" else -1
        if topic.parent is not None and p.side == -d:
            return topic.parent
        cands = [c for c in topic.children if c in placements and placements[c].side == d]
        return min(cands, key=lambda c: abs(placements[c].y - p.y), default=None)

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
    return min(cands, key=lambda q: abs(placements[q].y - p.y), default=None)
