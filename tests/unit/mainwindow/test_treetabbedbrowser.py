# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from qutebrowser.config.configtypes import NewTabPosition, NewChildPosition
from qutebrowser.misc.notree import Node
from qutebrowser.mainwindow import treetabbedbrowser, treetabwidget


@pytest.fixture
def mock_browser(mocker):
    # Mock browser used as `self` below because we are actually testing mostly
    # standalone functionality apart from the tab stack related counters.
    # Which are also only defined in __init__, not on the class, so mock
    # doesn't see them. Hence specifying them manually here.
    browser = mocker.Mock(
        spec=treetabbedbrowser.TreeTabbedBrowser,
        widget=mocker.Mock(spec=treetabwidget.TreeTabWidget),
        _tree_tab_child_rel_idx=0,
        _tree_tab_sibling_rel_idx=0,
        _tree_tab_toplevel_rel_idx=0,
    )

    # Sad little workaround to create a bound method on a mock, because
    # _position_tab calls a method on self but we are using a mock as self to
    # avoid initializing the whole tabbed browser class.
    def reset_passthrough():
        return treetabbedbrowser.TreeTabbedBrowser._reset_stack_counters(
            browser
        )
    browser._reset_stack_counters = reset_passthrough

    return browser


class TestPositionTab:
    """Test TreeTabbedBrowser._position_tab()."""

    @pytest.mark.parametrize(
        "     relation, cur_node, pos, expected", [
            ("sibling", "three", "first", "one",),
            ("sibling", "three", "prev", "two",),
            ("sibling", "three", "next", "three",),
            ("sibling", "three", "last", "six",),
            ("sibling", "one", "first", "root",),
            ("sibling", "one", "prev", "root",),
            ("sibling", "one", "next", "one",),
            ("sibling", "one", "last", "seven",),

            ("related", "one", "first", "one",),
            ("related", "one", "last", "six",),
            ("related", "two", "first", "two",),
            ("related", "two", "last", "two",),

            (None, "five", "first", "root",),
            (None, "five", "prev", "root",),
            (None, "five", "next", "one",),
            (None, "five", "last", "seven",),
            (None, "seven", "prev", "one",),
            (None, "seven", "next", "seven",),
        ]
    )
    def test_position_tab(
        self,
        config_stub,
        mock_browser,
        # parameterized
        relation,
        cur_node,
        pos,
        expected,
    ):
        """Test tree tab positioning.

        How to use the parameters above:
        * refer to the tree structure being passed to create_tree() below, that's
          our starting state
        * specify how the new node should be related to the current one
        * specify cur_node by value, which is the tab currently focused when the
          new tab is opened and the one the "sibling" and "related" arguments
          refer to
        * set "pos" which is the position of the new node in the list of
          siblings it's going to end up in. It should be one of first, list, prev,
          next (except the "related" relation doesn't support prev and next)
        * specify the expected preceding node (the preceding sibling if there is
          one, otherwise the parent) after the new node is positioned, "root" is
          a valid value for this

        Having the expectation being the preceding tab (sibling or parent) is
        a bit limited, in particular if the new tab somehow ends up as a child
        instead of the next sibling you wouldn't be able to tell those
        situations apart. But I went this route to avoid having to specify
        multiple trees in the parameters.
        """
        root = self.create_tree(
            """
            - one
              - two
              - three
              - four
                - five
              - six
            - seven
            """,
        )
        new_node = Node("new", parent=root)

        config_stub.val.tabs.new_position.stacking = False
        self.call_position_tab(
            mock_browser,
            root,
            cur_node,
            new_node,
            pos,
            relation,
        )

        preceding_node = None
        if new_node.parent.children[0] == new_node:
            preceding_node = new_node.parent
        else:
            for n in new_node.parent.children:
                if n.value == "new":
                    break
                preceding_node = n
            else:
                pytest.fail("new tab not found")

        assert preceding_node.value == expected

    def call_position_tab(
        self,
        mock_browser,
        root,
        cur_node,
        new_node,
        pos,
        relation,
        background=False,
    ):
        sibling = related = False
        if relation == "sibling":
            sibling = True
        elif relation == "related":
            related = True
        elif relation == "background":
            background = True
        elif relation is not None:
            pytest.fail(
                "Valid values for relation are: "
                "sibling, related, background, None"
            )

        # This relation -> parent mapping is copied from
        # TreeTabbedBrowser.tabopen().
        cur_node = next(n for n in root.traverse() if n.value == cur_node)
        assert not (related and sibling)
        if related:
            parent = cur_node
            NewChildPosition().from_str(pos)
        elif sibling:
            parent = cur_node.parent
            NewTabPosition().from_str(pos)
        else:
            parent = root
            NewTabPosition().from_str(pos)

        treetabbedbrowser.TreeTabbedBrowser._position_tab(
            mock_browser,
            cur_node=cur_node,
            new_node=new_node,
            pos=pos,
            parent=parent,
            sibling=sibling,
            related=related,
            background=background,
        )

    def create_tree(self, tree_str):
        # Construct a notree.Node tree from the test string.
        root = Node("root")
        previous_indent = ''
        previous_node = root
        for line in tree_str.splitlines():
            if not line.strip():
                continue
            indent, value = line.split("-")
            node = Node(value.strip())
            if len(indent) > len(previous_indent):
                node.parent = previous_node
            elif len(indent) == len(previous_indent):
                node.parent = previous_node.parent
            else:
                # TODO: handle going up in jumps of more than one rank
                node.parent = previous_node.parent.parent
            previous_indent = indent
            previous_node = node
        return root

    @pytest.mark.parametrize(
        "     test_tree, relation, pos, expected", [
            ("tree_one", "sibling", "next", "one,two,new1,new2,new3",),
            ("tree_one", "sibling", "prev", "one,new3,new2,new1,two",),
            ("tree_one", None, "next", "one,two,new1,new2,new3",),
            ("tree_one", None, "prev", "new3,new2,new1,one,two",),
            ("tree_one", "related", "first", "one,two,new1,new2,new3",),
            ("tree_one", "related", "last", "one,two,new1,new2,new3",),
        ]
    )
    def test_position_tab_stacking(
        self,
        config_stub,
        mock_browser,
        # parameterized
        test_tree,
        relation,
        pos,
        expected,
    ):
        """Test tree tab positioning with tab stacking enabled.

        With tab stacking enabled the first background tab should be opened
        beside the current one, successive background tabs should be opened on
        the other side of prior opened tabs, not beside the current tab.
        This test covers what is currently implemented, I'm not sure all the
        desired behavior is implemented currently though.
        """
        # Simpler tree here to make the assert string a bit simpler.
        # Tab "two" is hardcoded as cur_tab.
        root = self.create_tree(
            """
            - one
              - two
            """,
        )
        config_stub.val.tabs.new_position.stacking = True

        for val in ["new1", "new2", "new3"]:
            new_node = Node(val, parent=root)

            self.call_position_tab(
                mock_browser,
                root,
                "two",
                new_node,
                pos,
                relation,
                background=True,
            )

        actual = ",".join([n.value for n in root.traverse()])
        actual = actual[len("root,"):]
        assert actual == expected
