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
"""

class TreeError(RuntimeError):
    pass

class Node():
    sep = '/'

    def __init__(self, name, parent=None, childs=tuple()):
        self.name = name
        # set initial values so there's no need for AttributeError checks
        self.__parent = None
        self.__children = []

        if parent:
            self.parent = parent
        if childs:
            self.children = childs

    @property
    def parent(self):
        return self.__parent

    @parent.setter
    def parent(self, value):
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
        seen = set(value)
        if len(seen) != len(value):
            raise TreeError("A duplicate item is present in in %r" % value)
        new_children = list(value)
        for child in new_children:
            if child.parent is not self:
                child.parent = self

    @property
    def path(self):
        if self.parent is None:
            return [self.name]
        else:
            return self.parent.path + [self.name]

    @property
    def siblings(self):
        if self.parent:
            return (i for i in self.parent.children if i is not self)

    def __add_child(self, node):
        if node not in self.__children:
            self.__children.append(node)

    def __disown(self, value):
        if value in self.__children:
            self.__children.remove(value)

    def __repr__(self):
        # return "<Node '%s'>" % self.name
        return "<Node '%s'>" % self.sep.join(self.path)

    def __str__(self):
        # return "<Node '%s'>" % self.name
        return self.name

corner = '└─'
intersection = '├─'
pipe = '│'

def traverse(node):
    """
    Generator for all descendants of `node`, yield pre-order depth-first.
    In particular, the order of elements yield here will be the same as their order
    (line-wise, ignoring markup) when calling render_tree.
    """
    yield node
    for child in node.children:
        yield from traverse(child)


def render_tree(node):
    result = [('', node)]
    for child in node.children:
        if child.children:
            subtree = render_tree(child)
            if child is not node.children[-1]:
                subtree = [(pipe + ' ' + c, n) for c, n in subtree]
                char = intersection
            else:
                subtree = [('  ' + c, n) for c, n in subtree]
                char = corner
            subtree[0] = (char, subtree[0][1])
            result += subtree
        else:
            if child is node.children[-1]:
                result.append((corner, child))
            else:
                result.append((intersection, child))
    # return '\n'.join(result)
    return result
