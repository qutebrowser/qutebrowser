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

"""
Tree library for tree-tabs.
The fundamental unit is the Node class.

Create a tree with with Node(value, parent):
root = Node('foo')
child = Node('bar', root)
child2 = Node('baz', root)
child3 = Node('lorem', child)

You can also assign parent after instantiation, or even reassign it:
child4 = Node('ipsum')
child4.parent = root

Assign children:
child.children = []
child2.children = [child4, child3]
child3.parent
> Node('foo/bar/baz')

Render a tree with render_tree(root_node):
render_tree(root)

> ('', 'foo')
> ('├─', 'bar')
> ('│ ├─', 'lorem')
> ('│ └─', 'ipsum')
> ('└─', 'baz')
"""
import enum

class TreeError(RuntimeError):
    """Exception used for tree-related errors"""
    pass

class Node():
    """Fundamental unit of notree library """
    sep = '/'

    def __init__(self, value, parent=None, childs=tuple()):
        self.value = value
        # set initial values so there's no need for AttributeError checks
        self.__parent = None
        self.__children = []

        if parent:
            self.parent = parent  # calls setter
        if childs:
            self.children = childs  # this too

        self.collapsed = False

    @property
    def parent(self):
        return self.__parent

    @parent.setter
    def parent(self, value):
        """Set parent property. Also adds self to value.children"""
        assert(value is None or isinstance(value, Node))
        if self.__parent:
            self.__parent.__disown(self)
            self.__parent = None
        if value is not None:
            value.__add_child(self)
            self.__parent = value

    @property
    def children(self):
        return tuple(self.__children)

    @children.setter
    def children(self, value):
        """
        Set children property, preserving order.
        Also sets n.parent = self for n in value. Does not allow duplicates.
        """
        seen = set(value)
        if len(seen) != len(value):
            raise TreeError("A duplicate item is present in in %r" % value)
        new_children = list(value)
        for child in new_children:
            if child.parent is not self:
                child.parent = self
        self.__children = new_children

    @property
    def path(self):
        """Get a list of all nodes from the root node to self"""
        if self.parent is None:
            return [self.value]
        else:
            return self.parent.path + [self.value]

    @property
    def siblings(self):
        """Get siblings. Can not be set."""
        if self.parent:
            return (i for i in self.parent.children if i is not self)

    def __add_child(self, node):
        if node not in self.__children:
            self.__children.append(node)

    def __disown(self, value):
        if value in self.__children:
            self.__children.remove(value)

    def __repr__(self):
        # return "<Node '%s'>" % self.value
        return "<Node '%s'>" % self.sep.join(self.path)

    def __str__(self):
        # return "<Node '%s'>" % self.value
        return self.value

corner = '└─'
intersection = '├─'
pipe = '│'

class TraverseOrder(enum.Enum):
    """
    To be used as argument to traverse().
    Implemented orders are pre-order and post-order.
    PRE yields nodes in the same order as they appear in the result of render_tree.
    POST yields them so the children of a node are always yield before their parent.
    """
    PRE = enum.auto()
    POST = enum.auto()

def traverse(node, order=TraverseOrder.PRE, render_collapsed=True):
    """Generator for all descendants of `node`"""
    if order == TraverseOrder.PRE:
        yield node
    for child in node.children:
        if render_collapsed or not child.collapsed:
            yield from traverse(child, order)
        else:
            yield child
    if order == TraverseOrder.POST:
        yield node


def render_tree(node, render_collapsed=True):
    """
    Render a tree with ascii symbols.
    Tabs always appear in the same order as in traverse() with TraverseOrder.PRE
    return: list of tuples where the first item is the symbol,
            and the second is the node it refers to
    """
    result = [('', node)]
    for child in node.children:
        if child.children:
            subtree = render_tree(child, render_collapsed)
            if child is not node.children[-1]:
                subtree = [(pipe + ' ' + c, n) for c, n in subtree]
                char = intersection
            else:
                subtree = [('  ' + c, n) for c, n in subtree]
                char = corner
            subtree[0] = (char, subtree[0][1])
            if child.collapsed and not render_collapsed:
                result += [subtree[0]]
            else:
                result += subtree
        else:
            if child is node.children[-1]:
                result.append((corner, child))
            else:
                result.append((intersection, child))
    # return '\n'.join(result)
    return result
