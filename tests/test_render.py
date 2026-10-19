import pytest

from arbor import model, style
from arbor.model import Topic
from arbor.render import EDGE_WIDTH, ROOT_EDGE_WIDTH, render


pytestmark = pytest.mark.usefixtures("qapp")  # theme() reads the system scheme


def tree():
    root = Topic("root")
    a = root.add(Topic("a"))
    a.add(Topic("a1"))
    root.add(Topic("b"))
    return root


def test_unchanged_tree_renders_equal_nodes_even_after_a_snapshot():
    root = tree()
    again = Topic.from_dict(root.to_dict(keep_uids=True))
    assert list(render(again).values()) == list(render(root).values())


def test_nodes_describe_style_edges_and_badges():
    root = tree()
    a, b = root.children
    a.collapsed = True
    nodes = render(root)
    assert list(nodes) == [root, a, b]  # visible topics, in document order
    assert nodes[root].style is style.ROOT_STYLE and nodes[root].edge_width is None
    assert nodes[a].edge_width == ROOT_EDGE_WIDTH and nodes[a].hidden_count == 1
    assert nodes[b].hidden_count is None
    a.collapsed = False
    assert render(root)[a.children[0]].edge_width == EDGE_WIDTH


def test_moving_a_branch_changes_the_nodes_of_topics_that_were_not_touched():
    root = tree()
    a, b = root.children
    a1 = a.children[0]
    before = render(root)
    model.move(b, -1)
    after = render(root)
    assert after[root] == before[root] and after[a1].text == before[a1].text
    assert after[a1].color != before[a1].color  # a's branch colour follows its position
