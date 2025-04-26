# SPDX-FileCopyrightText: Giuseppe Stelluto (pinusc) <giuseppe@gstelluto.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tree library for tree-tabs.

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
from typing import Optional, TypeVar, Generic
from collections.abc import Iterable, Sequence
import itertools

from qutebrowser.utils import log

# For Node.render
CORNER = '└─'
INTERSECTION = '├─'
PIPE = '│'


class TreeError(RuntimeError):
    """Exception used for tree-related errors."""


class TraverseOrder(enum.Enum):
    """Tree traversal order for Node.traverse().

    All traversals are depth first.
    See https://en.wikipedia.org/wiki/Depth-first_search#Vertex_orderings

    Attributes:
        PRE: pre-order: parent then children, leftmost nodes first. Same as in Node.render().
        POST: post-order: children then parent, leftmost nodes first, then parent.
        POST_R: post-order-reverse: like POST but rightmost nodes first.
    """

    PRE = 'pre-order'  # pylint: disable=invalid-name
    POST = 'post-order'  # pylint: disable=invalid-name
    POST_R = 'post-order-reverse'  # pylint: disable=invalid-name


uid_gen = itertools.count(0)

# generic type of value held by Node
T = TypeVar('T')


class Node(Generic[T]):
    """Fundamental unit of notree library.

    Attributes:
        value: The element (usually a tab) the node represents
        parent: Node's parent.
        children: Node's children elements.
        siblings: Children of parent node that are not self.
        path: List of nodes from root of tree to self value, parent, and
            children can all be set by user. Everything else will be updated
            accordingly, so that if `node.parent = root_node`, then `node in
            root_node.children` will be True.
    """

    sep: str = '/'
    __parent: Optional['Node[T]'] = None
    # this is a global 'static' class attribute

    def __init__(self,
                 value: T,
                 parent: Optional['Node[T]'] = None,
                 childs: Sequence['Node[T]'] = (),
                 uid: Optional[int] = None) -> None:
        if uid is not None:
            self.__uid = uid
        else:
            self.__uid = next(uid_gen)

        self.value = value
        # set initial values so there's no need for AttributeError checks
        self.__parent: Optional['Node[T]'] = None
        self.__children: list['Node[T]'] = []

        # For render memoization
        self.__modified = False
        self.__set_modified()  # not the same as line above
        self.__rendered: Optional[list[tuple[str, 'Node[T]']]] = None

        if parent:
            self.parent = parent  # calls setter
        if childs:
            self.children = childs  # this too

        self.__collapsed = False

    @property
    def uid(self) -> int:
        return self.__uid

    @property
    def parent(self) -> Optional['Node[T]']:
        return self.__parent

    @parent.setter
    def parent(self, value: 'Node[T]') -> None:
        """Set parent property. Also adds self to value.children."""
        # pylint: disable=protected-access
        assert (value is None or isinstance(value, Node))
        if self.__parent:
            self.__parent.__disown(self)
            self.__parent = None
        if value is not None:
            assert self not in value.path
            value.__add_child(self)
            self.__parent = value
        self.__set_modified()

    @property
    def children(self) -> Sequence['Node[T]']:
        return tuple(self.__children)

    @children.setter
    def children(self, value: Sequence['Node[T]']) -> None:
        """Set children property, preserving order.

        Also sets n.parent = self for n in value. Does not allow duplicates.
        """
        seen = set(value)
        if len(seen) != len(value):
            raise TreeError("A duplicate item is present in %r" % value)
        new_children = list(value)
        for child in new_children:
            assert child not in self.path
            if child.parent is not self:
                child.parent = self
        self.__children = new_children
        self.__set_modified()

    def insert_child(
        self,
        node: 'Node[T]',
        idx: Optional[int] = None,
        before: Optional['Node[T]'] = None,
        after: Optional['Node[T]'] = None,
    ) -> None:
        """Insert `node` under `self` as a child.

        The `idx`, `before` and `after` parameters are mutually exclusive, one
        of them is required. They can be used to insert `node` at either a
        fixed index or beside another node.
        """
        assert sum(1 for a in [idx, before, after] if a is not None) == 1, f"{idx=} {before=} {after=}"
        node.parent = None
        children = list(self.children)
        if idx is not None:
            assert 0 <= idx <= len(children)
            children.insert(idx, node)
        else:
            rel_idx = children.index(before or after)
            if after:
                rel_idx += 1
            children.insert(rel_idx, node)
        self.children = children

    @property
    def path(self) -> list['Node[T]']:
        """Get a list of all nodes from the root node to self."""
        if self.parent is None:
            return [self]
        else:
            return self.parent.path + [self]

    @property
    def depth(self) -> int:
        """Get the number of nodes between self and the root node."""
        return len(self.path) - 1

    @property
    def index(self) -> int:
        """Get self's position among its siblings (self.parent.children)."""
        if self.parent is not None:
            return self.parent.children.index(self)
        else:
            raise TreeError('Node has no parent.')

    @property
    def collapsed(self) -> bool:
        return self.__collapsed

    @collapsed.setter
    def collapsed(self, val: bool) -> None:
        self.__collapsed = val
        self.__set_modified()

    def __set_modified(self) -> None:
        """If self is modified, every ancestor is modified as well."""
        for node in self.path:
            node.__modified = True  # pylint: disable=protected-access,unused-private-member

    def render(self) -> list[tuple[str, 'Node[T]']]:
        """Render a tree with ascii symbols.

        Tabs appear in the same order as in traverse() with TraverseOrder.PRE
        Args:
            node; the root of the tree to render

        Return: list of tuples where the first item is the symbol,
                and the second is the node it refers to
        """
        if not self.__modified and self.__rendered is not None:
            return self.__rendered

        result = [('', self)]
        for child in self.children:
            if child.children:
                subtree = child.render()
                if child is not self.children[-1]:
                    subtree = [(PIPE + ' ' + c, n) for c, n in subtree]
                    char = INTERSECTION
                else:
                    subtree = [('  ' + c, n) for c, n in subtree]
                    char = CORNER
                subtree[0] = (char, subtree[0][1])
                if child.collapsed:
                    result += [subtree[0]]
                else:
                    result += subtree
            elif child is self.children[-1]:
                result.append((CORNER, child))
            else:
                result.append((INTERSECTION, child))
        self.__modified = False
        self.__rendered = list(result)
        return list(result)

    def traverse(self, order: TraverseOrder = TraverseOrder.PRE,
                 render_collapsed: bool = True) -> Iterable['Node']:
        """Generator for `self` and all descendants.

        Args:
            order: a TraverseOrder object. See TraverseOrder documentation.
            render_collapsed: whether to yield children of collapsed nodes
        """
        if order == TraverseOrder.PRE:
            yield self

        if self.collapsed and not render_collapsed:
            if order != TraverseOrder.PRE:
                yield self
            return

        f = reversed if order is TraverseOrder.POST_R else lambda x: x
        for child in f(self.children):
            if render_collapsed or not child.collapsed:
                yield from child.traverse(order, render_collapsed)
            else:
                yield child
        if order in [TraverseOrder.POST, TraverseOrder.POST_R]:
            yield self

    def __add_child(  # pylint: disable=unused-private-member
        self,
        node: 'Node[T]',
    ) -> None:
        if node not in self.__children:
            self.__children.append(node)

    def __disown(  # pylint: disable=unused-private-member
        self,
        value: 'Node[T]',
    ) -> None:
        self.__set_modified()
        if value in self.__children:
            self.__children.remove(value)

    def get_descendent_by_uid(self, uid: int) -> Optional['Node[T]']:
        """Return descendent identified by the provided uid.

        Returns None if there is no such descendent.

        Args:
            uid: The uid of the node to return
        """
        for descendent in self.traverse():
            if descendent.uid == uid:
                return descendent
        return None

    def promote(self, times: int = 1, to: str = 'first') -> None:
        """Makes self a child of its grandparent, i.e. sibling of its parent.

        Args:
            times: How many levels to promote the tab to.
            to: One of 'next', 'prev', 'first', 'last'. Determines the position among siblings
              after being promoted. 'next' and 'prev' are relative to the current
              parent.

        """
        if to not in ['first', 'last', 'next', 'prev']:
            raise ValueError("Invalid value supplied for 'to': " + to)
        position = {'first': 0, 'last': -1}.get(to, None)
        diff = {'next': 1, 'prev': 0}.get(to, 1)
        count = times
        while count > 0:
            if self.parent is None or self.parent.parent is None:
                raise TreeError("Tab has no parent!")
            grandparent = self.parent.parent
            if position is not None:
                idx = position
            else:  # diff is necessarily not none
                idx = self.parent.index + diff
            self.parent = None

            siblings = list(grandparent.children)
            if idx != -1:
                siblings.insert(idx, self)
            else:
                siblings.append(self)
            grandparent.children = siblings
            count -= 1

    def demote(self, to: str = 'last') -> None:
        """Demote a tab making it a child of its previous adjacent sibling."""
        if self.parent is None or self.parent.children is None:
            raise TreeError("Tab has no siblings!")
        siblings = list(self.parent.children)

        # we want previous node in the same subtree as current node
        rel_idx = siblings.index(self) - 1

        if rel_idx >= 0:
            parent = siblings[rel_idx]
            new_siblings = list(parent.children)
            position = {'first': 0, 'last': -1}.get(to, -1)
            if position == 0:
                new_siblings.insert(0, self)
            else:
                new_siblings.append(self)
            parent.children = new_siblings
        else:
            raise TreeError("Tab has no previous sibling!")

    def __repr__(self) -> str:
        try:
            value = str(self.value.url().url())  # type: ignore
        except Exception:
            value = str(self.value)
        return "<Node -%d- '%s'>" % (self.__uid, value)

    def __str__(self) -> str:
        # return "<Node '%s'>" % self.value
        return str(self.value)

    def check_can_move(self, to: "Node") -> None:
        """Raise a TreeError if our moving logic doesn't support the requested operation."""
        if self in to.path:
            raise TreeError("Can't move tab to a descendent of itself")

    def move_recursive(self, to: "Node") -> None:
        """Move this tab and its children to the position of `to`."""
        # The logic below doesn't currently handle these cases.
        self.check_can_move(to)

        nodes = list(self.path[0].traverse(render_collapsed=False))[1:]
        from_idx = nodes.index(self)
        if nodes.index(to) > from_idx:
            to.parent.insert_child(self, after=to)
        else:
            to.parent.insert_child(self, before=to)

    def drag(self, direction: str) -> None:
        """Move this tab a single place in the list of nodes."""
        # move() implementation that only supports moving a single step at a
        # time. Could probably be generalized into a non-recursive move()
        # implementation.

        # Give nodes direction independent names so we can re-use logic
        # below. Names reflect where we need to put the nodes, eg if
        # moving down the moved node will be the bottom of the two.
        nodes = list(self.path[0].traverse(render_collapsed=False))[1:]
        from_idx = nodes.index(self)
        if direction == "+":
            moving_down = True
            top_node = nodes[from_idx + 1]
            bottom_node = self
        elif direction == "-":
            moving_down = False
            top_node = self
            bottom_node = nodes[from_idx - 1]
        else:
            raise TreeError('direction argument must be one of: "-" or "+"')

        # TODO:
        # * check with dragging onto collapsed nodes, they should have
        #   the same behaviour as no-children nodes: https://github.com/brimdata/react-arborist/issues/181
        # * move this logic into notree? At least so it's easier to unit test?
        # * review comments (and logic) below to make sure it's clear,
        #   concise and accurate
        # * look for opportunities to consolidate between branches

        # The general strategy here is to go with the positioning that
        # QTabBar uses and try to make that work. QTabBar shows all the nodes
        # in order and will always swap the moved node with the displaced one.
        # So we adjust parents and children to make the tab bar's view of
        # things reality.

        if bottom_node == top_node.parent:
            log.notree.info("moving along a branch")
            # Nodes are parent and child, swap them around. First move the
            # top node up to be a sibling of the bottom node.
            bottom_node.parent.insert_child(top_node, before=bottom_node)
            # Then swap children to keep them in the same place.
            top_node.children, bottom_node.children = bottom_node.children, top_node.children
            # Then move the bottom node down.
            top_node.insert_child(bottom_node, idx=0)
        elif (
            top_node in bottom_node.parent.children
            # If moving down and the displaced node has children, we are
            # going into a new tree so skip this branch.
            and not (moving_down and top_node.children)
        ):
            log.notree.info("moving between siblings")
            # Swap nodes in sibling list.
            bottom_node.parent.insert_child(top_node, before=bottom_node)

            # If moving up, the top node (the one that's moving) could
            # have children. Move them down to the bottom node to keep
            # them in the same place.
            top_children = top_node.children
            top_node.children = []
            bottom_node.children = top_children
        elif moving_down:
            log.notree.info("moving into top of new tree")
            # Moving from a leaf node in one tree, to the top of a new
            # one. If the new tree is just a single node, insert the
            # bottom node as a sibling. Or if the new tree has children,
            # insert the bottom node as the first child.
            if top_node.children:
                top_node.insert_child(bottom_node, idx=0)
            else:
                top_node.parent.insert_child(bottom_node, after=top_node)
        else:
            log.notree.info("moving into bottom of new tree")
            # Moving from the top of a tree into a leaf node of a new one.
            # If the top node has children, promote the first child to
            # take the top node's place in the old tree.
            # This "promote a single node" logic is also in
            # `TreeTabbedBrowser._remove_tab()`.
            top_children = top_node.children
            first_child = top_children[0]
            for child in top_children[1:]:
                child.parent = first_child

            top_node.parent.insert_child(first_child, after=top_node)
            bottom_node.parent.insert_child(top_node, before=bottom_node)
