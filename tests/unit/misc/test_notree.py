# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2018 Alexander Cogneau (acogneau) <alexander.cogneau@gmail.com>
# Copyright 2015-2018 Florian Bruhin (The-Compiler) <me@the-compiler.org>
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

"""Tests for misc.notree"""

from qutebrowser.misc import notree

from notree import TreeError
from notree import Node
from notree import traverse, render_tree
import pytest

@pytest.fixture
def tree():
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
    return n1,n2,n3,n4,n5,n6,n7,n8,n9,n10,n11

@pytest.fixture
def node(tree):
    return tree[0]

def test_creation():
    node = Node('foo')
    assert node.name == 'foo'

    child = Node('bar', node)
    assert child.parent == node
    assert node.children == (child,)

def test_attach_parent():
    n1 = Node('n1', None, [])
    print(n1.children)
    n2 = Node('n2', n1)
    n3 = Node('n3')

    n2.parent = n3
    assert n2.parent == n3
    assert n3.children == (n2,)
    assert n1.children == tuple()

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
    n2.children = (n6,) + n2.children
    print('\n'.join(render_tree(tree[0])))
    assert n6.parent is n2
    assert n6 in n2.children
    assert n11.parent is n3
    assert n11 in n3.children
    assert n6 not in n3.children
    assert len(n3.children) == 1

def test_traverse(node):
    len_traverse = len(list(traverse(node)))
    len_render = len(render_tree(node))
    assert len_traverse == len_render

def test_render_tree(node):
    expected = ['n1',
                '├─n2',
                '│ ├─n4',
                '│ └─n5',
                '└─n3',
                '  ├─n6',
                '  │ ├─n7',
                '  │ ├─n8',
                '  │ └─n9',
                '  │   └─n10',
                '  └─n11']
    result = render_tree(node)
    assert expected == result

def test_siblings():
    n1 = Node('n1')
    n2 = Node('n2', n1)
    n4 = Node('n4', n2)
    n5 = Node('n5', n2)
    n52 = Node('n52', n2)
    n53 = Node('n53', n2)
    n3 = Node('n3', n1)
    n6 = Node('n6', n3)
    n7 = Node('n7', n6)
    n8 = Node('n8', n6)
    n9 = Node('n9', n6)
    n10 = Node('n10', n9)
    assert list(n2.siblings) == [n3]
    assert list(n52.siblings) == [n4, n5, n53]

