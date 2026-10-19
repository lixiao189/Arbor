"""Virtual nodes: a pure description of what each visible topic draws.

``render()`` describes the tree; the canvas compares each node with the one its item
last drew and patches only items whose node differs, like a virtual DOM diff. A node
holds everything an item, its edge and its fold badge draw except positions, which
come from the layout.
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtGui import QColor

from .model import Topic
from .style import FILLED_TEXT, Style, branch_color, style_for, theme

ROOT_EDGE_WIDTH, EDGE_WIDTH = 3.0, 1.8


@dataclass(frozen=True)
class TopicNode:
    uid: int  # the key matching a node to the item that drew it before
    text: str
    style: Style
    color: QColor  # the branch colour: body, edge and badge
    text_color: QColor
    edge_width: float | None  # the edge from the parent; None for the root
    hidden_count: int | None  # shown in the fold badge; None when not collapsed


def node_for(topic: Topic) -> TopicNode:
    style = style_for(topic)
    if topic.parent is None:
        edge_width = None
    else:
        edge_width = ROOT_EDGE_WIDTH if topic.parent.is_root else EDGE_WIDTH
    return TopicNode(
        uid=topic.uid,
        text=topic.text,
        style=style,
        color=branch_color(topic),
        text_color=FILLED_TEXT if style.filled else theme().sub_text,
        edge_width=edge_width,
        hidden_count=(
            topic.descendant_count() if topic.collapsed and topic.children else None
        ),
    )


def render(root: Topic) -> dict[Topic, TopicNode]:
    """Nodes for the visible topics, in document order."""
    return {topic: node_for(topic) for topic in root.walk_visible()}
