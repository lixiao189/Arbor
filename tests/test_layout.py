from mind_demo.layout import layout, neighbor
from mind_demo.model import Topic


def measure(t):
    return (100, 30)


def make(n):
    root = Topic("r")
    for i in range(n):
        m = root.add(Topic(f"m{i}"))
        for j in range(2):
            m.add(Topic(f"m{i}s{j}"))
    return root


def test_balanced_sides():
    root = make(5)
    p = layout(root, measure)
    sides = [p[c].side for c in root.children]
    assert sides == [1, 1, 1, -1, -1]
    assert all(p[c].x > 0 for c in root.children[:3])
    assert all(p[c].x < 0 for c in root.children[3:])
    # grandchildren continue outward
    assert p[root.children[0].children[0]].x > p[root.children[0]].x
    assert p[root.children[4].children[0]].x < p[root.children[4]].x


def test_no_vertical_overlap_on_a_side():
    root = make(6)
    p = layout(root, measure)
    for side in (1, -1):
        leaves = sorted((p[t].y for t in p if p[t].side == side and not t.children))
        assert all(b - a >= 30 for a, b in zip(leaves, leaves[1:]))


def test_collapsed_children_hidden():
    root = make(2)
    root.children[0].collapsed = True
    p = layout(root, measure)
    assert root.children[0].children[0] not in p


def test_navigation():
    root = make(4)
    p = layout(root, measure)
    r0, r1, l0, l1 = root.children
    assert neighbor(root, "right", p) in (r0, r1)
    assert neighbor(root, "left", p) in (l0, l1)
    assert neighbor(r0, "down", p) is r1
    assert neighbor(r0, "left", p) is root
    assert neighbor(r0, "right", p) in r0.children
    assert neighbor(l0, "right", p) is root
    assert neighbor(l0, "left", p) in l0.children
    # crossing between cousins at the same depth
    assert neighbor(r0.children[1], "down", p) is r1.children[0]
    assert neighbor(root, "up", p) is None


def test_drop_target_zones():
    from mind_demo.layout import drop_target

    root = make(4)
    p = layout(root, measure)
    r0, r1, l0, _ = root.children
    pr1 = p[r1]
    mid = drop_target(r0, pr1.x, pr1.y, p)
    assert (mid.parent, mid.index, mid.kind) == (r1, 2, "child")
    top = drop_target(r0, pr1.x, pr1.y - 12, p)
    assert (top.parent, top.index, top.kind) == (root, 1, "before")
    bottom = drop_target(r0, pr1.x, pr1.y + 12, p)
    assert (bottom.parent, bottom.index, bottom.kind) == (root, 2, "after")
    on_root = drop_target(l0, 0, 0, p)
    assert (on_root.parent, on_root.kind) == (root, "child")
    # never onto itself or its own subtree, and nothing on empty canvas
    assert drop_target(r0, p[r0].x, p[r0].y, p) is None
    assert drop_target(r0, p[r0.children[0]].x, p[r0.children[0]].y, p) is None
    assert drop_target(r0, 5000, 5000, p) is None
