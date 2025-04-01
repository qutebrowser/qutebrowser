# SPDX-FileCopyrightText: Florian Bruhin (The-Compiler) <me@the-compiler.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for misc.notree library."""
import pytest

from qutebrowser.misc.notree import TreeError, Node, TraverseOrder


@pytest.fixture
def tree():
    """Return an example tree.

    n1
    ├─n2
    │ ├─n4
    │ └─n5
    └─n3
      ├─n6
      │ ├─n7
      │ ├─n8
      │ └─n9
      │   └─n10
      └─n11
    """
    # these are actually used because they appear in expected strings
    n1 = Node('n1')
    n2 = Node('n2', n1)
    n4 = Node('n4', n2)
    n5 = Node('n5', n2)
    n3 = Node('n3', n1)
    n6 = Node('n6', n3)
    n7 = Node('n7', n6)
    n8 = Node('n8', n6)
    n9 = Node('n9', n6)
    n10 = Node('n10', n9)
    n11 = Node('n11', n3)
    return n1, n2, n3, n4, n5, n6, n7, n8, n9, n10, n11


@pytest.fixture
def node(tree):
    return tree[0]


def test_creation():
    node = Node('foo')
    assert node.value == 'foo'

    child = Node('bar', node)
    assert child.parent == node
    assert node.children == (child, )


def test_attach_parent():
    n1 = Node('n1', None, [])
    print(n1.children)
    n2 = Node('n2', n1)
    n3 = Node('n3')

    n2.parent = n3
    assert n2.parent == n3
    assert n3.children == (n2, )
    assert n1.children == ()


def test_duplicate_child():
    p = Node('n1')
    try:
        c1 = Node('c1', p)
        c2 = Node('c2', p)
        p.children = [c1, c1, c2]
        raise AssertionError("Can add duplicate child")
    except TreeError:
        pass
    finally:
        if len(p.children) == 3:
            raise AssertionError("Can add duplicate child")


def test_replace_parent():
    p1 = Node('foo')
    p2 = Node('bar')
    _ = Node('_', p2)
    c = Node('baz', p1)
    c.parent = p2
    assert c.parent is p2
    assert c not in p1.children
    assert c in p2.children


def test_replace_children(tree):
    n2 = tree[1]
    n3 = tree[2]
    n6 = tree[5]
    n11 = tree[10]
    n3.children = [n11]
    n2.children = (n6, ) + n2.children
    assert n6.parent is n2
    assert n6 in n2.children
    assert n11.parent is n3
    assert n11 in n3.children
    assert n6 not in n3.children
    assert len(n3.children) == 1


def test_promote_to_first(tree):
    n1 = tree[0]
    n3 = tree[2]
    n6 = tree[5]
    assert n6.parent is n3
    assert n3.parent is n1
    n6.promote(to='first')
    assert n6.parent is n1
    assert n1.children[0] is n6


def test_promote_to_last(tree):
    n1 = tree[0]
    n3 = tree[2]
    n6 = tree[5]
    assert n6.parent is n3
    assert n3.parent is n1
    n6.promote(to='last')
    assert n6.parent is n1
    assert n1.children[-1] is n6


def test_promote_to_prev(tree):
    n1 = tree[0]
    n3 = tree[2]
    n6 = tree[5]
    assert n6.parent is n3
    assert n3.parent is n1
    assert n1.children[1] is n3
    n6.promote(to='prev')
    assert n6.parent is n1
    assert n1.children[1] is n6


def test_promote_to_next(tree):
    n1 = tree[0]
    n3 = tree[2]
    n6 = tree[5]
    assert n6.parent is n3
    assert n3.parent is n1
    assert n1.children[1] is n3
    n6.promote(to='next')
    assert n6.parent is n1
    assert n1.children[2] is n6


def test_demote_to_first(tree):
    n11 = tree[10]
    n6 = tree[5]
    assert n11.parent is n6.parent
    parent = n11.parent
    assert parent.children.index(n11) == parent.children.index(n6) + 1
    n11.demote(to='first')
    assert n11.parent is n6
    assert n6.children[0] is n11


def test_demote_to_last(tree):
    n11 = tree[10]
    n6 = tree[5]
    assert n11.parent is n6.parent
    parent = n11.parent
    assert parent.children.index(n11) == parent.children.index(n6) + 1
    n11.demote(to='last')
    assert n11.parent is n6
    assert n6.children[-1] is n11


def test_traverse(tree):
    n1, n2, n3, n4, n5, n6, n7, n8, n9, n10, n11 = tree
    actual = list(n1.traverse())
    rendered = n1.render()
    assert len(actual) == len(rendered)
    print("\n".join('\t'.join((str(t[0]), t[1][0] + str(t[1][1]))) for t in zip(actual, rendered)))
    assert actual == [n1, n2, n4, n5, n3, n6, n7, n8, n9, n10, n11]


def test_traverse_postorder(tree):
    n1, n2, n3, n4, n5, n6, n7, n8, n9, n10, n11 = tree
    actual = list(n1.traverse(TraverseOrder.POST))
    print('\n'.join([str(n) for n in actual]))
    assert actual == [n4, n5, n2, n7, n8, n10, n9, n6, n11, n3, n1]


def test_traverse_postorder_r(tree):
    n1, n2, n3, n4, n5, n6, n7, n8, n9, n10, n11 = tree
    actual = list(n1.traverse(TraverseOrder.POST_R))
    print('\n'.join([str(n) for n in actual]))
    assert actual == [n11, n10, n9, n8, n7, n6, n3, n5, n4, n2, n1]


def test_render_tree(node):
    expected = [
        'n1',
        '├─n2',
        '│ ├─n4',
        '│ └─n5',
        '└─n3',
        '  ├─n6',
        '  │ ├─n7',
        '  │ ├─n8',
        '  │ └─n9',
        '  │   └─n10',
        '  └─n11'
    ]
    result = [char + str(n) for char, n in node.render()]
    print('\n'.join(result))
    assert expected == result


def test_uid(node):
    uids = set()
    for n in node.traverse():
        assert n not in uids
        uids.add(n.uid)
    # pylint: disable=unused-variable
    n1 = Node('n1')
    n2 = Node('n2', n1)
    n4 = Node('n4', n2)  # noqa: F841
    n5 = Node('n5', n2)  # noqa: F841
    n3 = Node('n3', n1)
    n6 = Node('n6', n3)
    n7 = Node('n7', n6)  # noqa: F841
    n8 = Node('n8', n6)  # noqa: F841
    n9 = Node('n9', n6)
    n10 = Node('n10', n9)  # noqa: F841
    n11 = Node('n11', n3)
    # pylint: enable=unused-variable
    for n in n1.traverse():
        assert n not in uids
        uids.add(n.uid)

    n11_uid = n11.uid
    assert n1.get_descendent_by_uid(n11_uid) is n11
    assert node.get_descendent_by_uid(n11_uid) is None


def test_collapsed(node):
    pre_collapsed_traverse = list(node.traverse())
    to_collapse = node.children[1]

    # collapse
    to_collapse.collapsed = True
    assert to_collapse.collapsed is True
    for n in node.traverse(render_collapsed=False):
        assert to_collapse not in n.path[:-1]

    assert list(to_collapse.traverse(render_collapsed=False)) == [to_collapse]

    assert list(node.traverse()) == pre_collapsed_traverse

    expected = [
        'n1',
        '├─n2',
        '│ ├─n4',
        '│ └─n5',
        '└─n3'
    ]
    result = [char + str(n) for char, n in node.render()]
    print('\n'.join(result))
    assert expected == result

    # uncollapse
    to_collapse.collapsed = False

    assert any(n for n in node.traverse(render_collapsed=False) if to_collapse
               in n.path[:-1])


def test_memoization(node):
    assert node._Node__modified is True
    node.render()
    assert node._Node__modified is False

    node.children[0].parent = None
    assert node._Node__modified is True
    node.render()
    assert node._Node__modified is False

    n2 = Node('ntest', parent=node)
    assert node._Node__modified is True
    assert n2._Node__modified is True
    node.render()
    assert node._Node__modified is False

    node.children[0].children[1].parent = None
    assert node._Node__modified is True
    assert node.children[0]._Node__modified is True
    node.render()
    assert node._Node__modified is False
