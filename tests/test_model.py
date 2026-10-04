from mind_demo import model
from mind_demo.model import Topic


def tree():
    root = Topic("root")
    a = root.add(Topic("a"))
    a.add(Topic("a1"))
    root.add(Topic("b"))
    return root


def test_roundtrip():
    root = tree()
    root.children[0].collapsed = True
    data = model.document_to_json(root)
    again = model.document_from_json(data)
    assert again.to_dict() == root.to_dict()
    assert again.children[0].children[0].parent is again.children[0]


def test_add_child_and_sibling_names():
    root = tree()
    assert model.add_child(root).text == "Main Topic 3"
    a = root.children[0]
    new = model.add_sibling(a, before=True)
    assert root.children[0] is new and root.children[1] is a
    assert model.add_child(a).text == "Subtopic 2"


def test_sibling_of_root_adds_child():
    root = tree()
    new = model.add_sibling(root)
    assert new.parent is root


def test_insert_parent():
    root = tree()
    a = root.children[0]
    p = model.insert_parent(a)
    assert root.children[0] is p and p.children == [a] and a.parent is p
    assert model.insert_parent(root) is None


def test_remove_selects_neighbour():
    root = tree()
    a, b = root.children
    assert model.remove(a) is b
    assert model.remove(b) is root
    assert model.remove(root) is None


def test_move():
    root = tree()
    a, b = root.children
    assert model.move(a, 1) is a and root.children == [b, a]
    assert model.move(a, 1) is None


def test_paths():
    root = tree()
    a1 = root.children[0].children[0]
    assert a1.path() == [0, 0] and root.at([0, 0]) is a1 and a1.depth == 2


def test_outline_roundtrip():
    root = tree()
    [parsed] = model.parse_outline(model.outline_text(root))
    assert parsed.to_dict() == root.to_dict()
