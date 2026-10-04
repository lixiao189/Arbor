"""Mind map data model: a tree of topics plus the editing operations on it."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

FILE_VERSION = 1


@dataclass(eq=False)
class Topic:
    """A node in the mind map. Equality and hashing are by identity."""

    text: str = ""
    children: list[Topic] = field(default_factory=list)
    parent: Topic | None = field(default=None, repr=False)
    collapsed: bool = False

    @property
    def is_root(self) -> bool:
        return self.parent is None

    @property
    def index(self) -> int:
        return self.parent.children.index(self) if self.parent else 0

    @property
    def depth(self) -> int:
        depth, node = 0, self
        while node.parent is not None:
            depth, node = depth + 1, node.parent
        return depth

    def root(self) -> Topic:
        node = self
        while node.parent is not None:
            node = node.parent
        return node

    def add(self, child: Topic, index: int | None = None) -> Topic:
        child.parent = self
        if index is None:
            self.children.append(child)
        else:
            self.children.insert(index, child)
        return child

    def detach(self) -> None:
        if self.parent is not None:
            self.parent.children.remove(self)
            self.parent = None

    def path(self) -> list[int]:
        """Child indices from the root down to this topic."""
        path, node = [], self
        while node.parent is not None:
            path.append(node.index)
            node = node.parent
        return path[::-1]

    def at(self, path: list[int]) -> Topic:
        node = self
        for i in path:
            node = node.children[i]
        return node

    def walk(self) -> Iterator[Topic]:
        yield self
        for child in self.children:
            yield from child.walk()

    def walk_visible(self) -> Iterator[Topic]:
        yield self
        if not self.collapsed:
            for child in self.children:
                yield from child.walk_visible()

    def descendant_count(self) -> int:
        return sum(1 + c.descendant_count() for c in self.children)

    def is_ancestor_of(self, other: Topic) -> bool:
        node = other.parent
        while node is not None:
            if node is self:
                return True
            node = node.parent
        return False

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"text": self.text}
        if self.collapsed:
            data["collapsed"] = True
        if self.children:
            data["children"] = [c.to_dict() for c in self.children]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Topic:
        topic = cls(text=str(data.get("text", "")), collapsed=bool(data.get("collapsed", False)))
        for child in data.get("children", []):
            topic.add(cls.from_dict(child))
        return topic

    def clone(self) -> Topic:
        return Topic.from_dict(self.to_dict())


def new_document() -> Topic:
    root = Topic("Central Topic")
    for i in range(1, 5):
        root.add(Topic(f"Main Topic {i}"))
    return root


def document_to_json(root: Topic) -> dict[str, Any]:
    return {"version": FILE_VERSION, "root": root.to_dict()}


def document_from_json(data: dict[str, Any]) -> Topic:
    if "root" not in data:
        raise ValueError("Not a mind map file: missing 'root'")
    return Topic.from_dict(data["root"])


def default_text(parent: Topic) -> str:
    """XMind names new topics by level: 'Main Topic N' under the root, else 'Subtopic N'."""
    label = "Main Topic" if parent.is_root else "Subtopic"
    return f"{label} {len(parent.children) + 1}"


# --- Editing operations. Each returns the topic that should be selected afterwards,
# or None when the operation does not apply.


def add_child(topic: Topic) -> Topic:
    topic.collapsed = False
    return topic.add(Topic(default_text(topic)))


def add_sibling(topic: Topic, before: bool = False) -> Topic:
    if topic.parent is None:
        return add_child(topic)
    parent = topic.parent
    return parent.add(Topic(default_text(parent)), topic.index + (0 if before else 1))


def insert_parent(topic: Topic) -> Topic | None:
    parent = topic.parent
    if parent is None:
        return None
    index = topic.index
    topic.detach()
    new = parent.add(Topic("Topic" if not parent.is_root else default_text(parent)), index)
    new.add(topic)
    return new


def remove(topic: Topic) -> Topic | None:
    """Delete a topic and its subtree; returns the neighbour to select next."""
    parent = topic.parent
    if parent is None:
        return None
    siblings, index = parent.children, topic.index
    if index + 1 < len(siblings):
        nxt = siblings[index + 1]
    elif index > 0:
        nxt = siblings[index - 1]
    else:
        nxt = parent
    topic.detach()
    return nxt


def move(topic: Topic, delta: int) -> Topic | None:
    parent = topic.parent
    if parent is None:
        return None
    index = topic.index
    target = index + delta
    if not 0 <= target < len(parent.children):
        return None
    parent.children.insert(target, parent.children.pop(index))
    return topic


def paste(target: Topic, subtree: Topic) -> Topic:
    target.collapsed = False
    return target.add(subtree)


def outline_text(topic: Topic, indent: int = 0) -> str:
    """Plain-text outline (tab-indented), used for the clipboard."""
    lines = ["\t" * indent + topic.text]
    lines += [outline_text(c, indent + 1) for c in topic.children]
    return "\n".join(lines)


def parse_outline(text: str) -> list[Topic]:
    """Parse a tab/space-indented outline into a forest of topics."""
    roots: list[Topic] = []
    stack: list[tuple[int, Topic]] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        expanded = raw.expandtabs(4)
        level = len(expanded) - len(expanded.lstrip())
        topic = Topic(raw.strip())
        while stack and stack[-1][0] >= level:
            stack.pop()
        if stack:
            stack[-1][1].add(topic)
        else:
            roots.append(topic)
        stack.append((level, topic))
    return roots
