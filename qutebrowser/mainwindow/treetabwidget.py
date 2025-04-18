# SPDX-FileCopyrightText: Giuseppe Stelluto (pinusc) <giuseppe@gstelluto.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Extension of TabWidget for tree-tab functionality."""

from qutebrowser.mainwindow.tabwidget import TabWidget
from qutebrowser.misc.notree import Node
from qutebrowser.utils import log


class TreeTabWidget(TabWidget):
    """Tab widget used in TabbedBrowser, with tree-functionality.

    Handles correct rendering of the tree as a tab field, and correct
    positioning of tabs according to tree structure.
    """

    def __init__(self, win_id, parent=None):
        # root of the tab tree, common for all tabs in the window
        self.tree_root = Node(None)
        super().__init__(win_id, parent)
        self.tabBar().tabMoved.connect(self.on_tab_moved)
        self._recursion_guard = False

    def on_tab_moved(self, from_idx: int, to_idx: int):
        """Handle the tabMoved signal."""
        #if self._tabbed_browser.is_shutting_down:
        #    # Running through the tests we somehow wind up with a cycle in the
        #    # tree when a window is being closed down via :window-only in the
        #    # setup step. This guard lets the test run through, but I wonder
        #    # if there is some more comprehensive logic fix.
        #    return

        # QTabBar::mouseMoveEvent() passes the indices backwards, the tab being
        # dragged is the second arg and the tab we just replaced is first.
        # We care about which tab is being dragged because dragging a tab into
        # a tree group is different from dragging a tab out of a group (the
        # tab that got displaced should stay in the group).
        recursive = True
        if self.tabBar().drag_in_progress:
            from_idx, to_idx = to_idx, from_idx
            recursive = False

        log.misc.info(f"TAB MOVED: {from_idx=} {to_idx=} in_drag={self.tabBar().drag_in_progress} guard={self._recursion_guard}")

        def render(node=self.tree_root):
            for t in node.render():
                log.misc.info(f"{t[0]} {repr(t[1])}")
        render()

        # A tab has been moved. See if the tree structure needs to be updated.
        # The move could have been triggered from a tree-naive place like
        # QTabBar, or it could have been triggered by something like
        # _TreeUndoEntry which will have already updated the tree structure.

        # We assume tree tabs will always be in the same order as the tab bar.
        # This should be enforced by `update_tree_tab_positions()`.
        # If indexing into the list of tree nodes doesn't yield the same tab
        # as indexing into the tab bar, then we have work to do.
        moved_tab = self._tab_by_idx(to_idx)
        nodes = list(self.tree_root.traverse(render_collapsed=False))[1:]
        node_at_current_position = nodes[to_idx]
        if moved_tab.node == node_at_current_position:
            return

        if self._recursion_guard:
            # If we are moving a tab with children, then move events will fire
            # as we move the children up tree_tab_update(). We already take
            # care to correctly position children in the initial move event.
            return
        self._recursion_guard = True

        log.misc.debug(f"Updating tree structure after tab move {moved_tab.node=} {node_at_current_position=}")

        if from_idx > to_idx:
            moving_down = False  # moving down the tree, increasing in index
        else:
            moving_down = True

        moved_node = self._tab_by_idx(to_idx).node
        if moving_down:
            displaced_node = self._tab_by_idx(to_idx - 1).node
        else:
            displaced_node = self._tab_by_idx(to_idx + 1).node

        if recursive:
            # Detach the moved node and insert it in the right place in the
            # displaced tab's sibling list.
            displaced_parent = displaced_node.parent
            moved_node.parent = None  # detach the node now to avoid duplicate errors
            displaced_siblings = list(displaced_parent.children)
            displaced_rel_index = displaced_siblings.index(displaced_node)

            log.misc.info(f"{moved_node=} {moving_down=} {displaced_node=} {displaced_rel_index=} {displaced_siblings=}")

            # Sanity check something weird isn't going on, this can happen without
            # the recursion guard.
            assert moved_node not in displaced_node.path

            if moving_down:
                displaced_siblings.insert(displaced_rel_index + 1, moved_node)
            else:
                displaced_siblings.insert(displaced_rel_index, moved_node)
            displaced_parent.children = displaced_siblings
        else:
            # The below logic assumes we are moving one tab bar index at a
            # time. Which means if you keep moving a tab like this it'll do a
            # depth first traversal of the tree.
            if moving_down:
                assert abs(to_idx - from_idx) == 1, f"{to_idx=} {from_idx=}"
            else:
                log.misc.info(f"{to_idx=} {from_idx=}")

            # The general strategy here is to go with the positioning that
            # QTabBar used and try to make that work. QTabBar will always swap
            # the moved node with the displaced one. So we adjust parents,
            # and children to work around that.

            ## Ahhh, remember this code is called for both drags and big jumps with
            ## :tab-move!

            # When moving single node, it will move in depth first fashion.
            # Need to swap moved node and displaced node?
            # What about children and siblings?
            # Write more examples and catalog them, come up with generic
            #   components to apply.
            # one
            #   two (active)
            #     three
            #       four
            #     five
            # :tab-move +
            # one
            #   three
            #     two (active)
            #       four
            #     five
            # ^ swap moved and displaced - seems to be the case for any
            # one-level move down
            #
            # one
            #   two (active)
            # three
            #   four
            # :tab-move +
            # one
            # two (active)
            #   three
            #     four
            #
            # one
            #   two
            #     three (active)
            #   four
            #     five
            # :tab-move +
            # one
            #   two
            #   three (active)
            #     four
            #       five
            # ^ any move into a new tree will shunt the tree down under the
            # moved node, which shouldn't have children by this point.
            # How to define a new tree here? Any node that isn't descendant?
            #
            # v not sure about these ones v
            # one
            #   two (active)
            #   three
            #     four
            #       five
            #     six
            # :tab-move +
            # one
            #   three (active)
            #     two
            #       four
            #         five
            #       six
            # one
            #   three (active)
            #     two
            #     four
            #       five
            #     six
            # ^ we can't swap them here, else three would have been moved out
            # of the tree.
            # TODO:
            # * check with dragging onto collapsed nodes, they should have
            #   the same behaviour as no-children nodes: https://github.com/brimdata/react-arborist/issues/181
            # * move this logic into notree? At least so it's easier to unit test?
            # * review comments (and logic) below to make sure it's clear,
            #   concise and accurate
            # * look for opportunities to consolidate between branches

            if moving_down:
                if moved_node == displaced_node.parent:
                    log.misc.info("moving down a branch")
                    # =swap nodes
                    # We want to swap the node moving down with the one it's
                    # displacing.
                    # We also swap their children, so the child nodes stay at
                    # the same level.

                    # Detach moved node and insert displaced node in its
                    # place.
                    moved_node.parent.insert_child(displaced_node, after=moved_node)

                    # Swap the children and add the moved node as the first
                    # child of the displaced node.
                    displaced_node.children, moved_node.children = moved_node.children, displaced_node.children
                    displaced_node.insert_child(moved_node, idx=0)
                elif (
                    displaced_node in moved_node.parent.children  # moving down in siblings
                    and not displaced_node.children
                ):
                    log.misc.info("moving between siblings")
                    # Moving between siblings, no new tree to worry about.
                    # Make the moved node the next sibling of the displaced
                    # one.
                    displaced_node.parent.insert_child(moved_node, after=displaced_node)
                else:
                    log.misc.info("moving into a new tree")
                    # Moving into new tree, either of a sibling node or an ancestor.
                    # Insert as first child of new tree

                    # We need to put the moved node after the displaced one.
                    # If it has children, that means putting it in the tree as
                    # the first child of the displaced node. Otherwise it's
                    # just the next sibling of the displaced node.
                    if displaced_node.children:
                        displaced_node.insert_child(moved_node, idx=0)
                    else:
                        displaced_node.parent.insert_child(moved_node, after=displaced_node)
            else:
                if moved_node.parent == displaced_node:
                    log.misc.info("moving up a branch")
                    # Swap nodes and then swap children to keep them in the
                    # same place
                    # Exact inverse of moving down a group

                    # Insert moved node into displaced node's place.
                    displaced_node.parent.insert_child(moved_node, before=displaced_node)

                    # Swap the children and add the displaced node as the first
                    # child of the moved node.
                    displaced_node.children, moved_node.children = moved_node.children, displaced_node.children
                    moved_node.insert_child(displaced_node, idx=0)
                elif (
                    displaced_node in moved_node.parent.children  # moving up in siblings
                ):
                    log.misc.info("moving between siblings")
                    # Swap nodes in sibling list. Switch children of moved
                    # node to displaced node
                    assert not displaced_node.children

                    moved_node.parent = None
                    displaced_node.parent.insert_child(moved_node, before=displaced_node)

                    moved_children = moved_node.children
                    moved_node.children = []
                    displaced_node.children = moved_children
                else:
                    log.misc.info("moving into a new tree")
                    # Make moved node sibling of last node in tree. Promote
                    # first child of moved node to take it's place.

                    # This "promote a single node" logic is also in
                    # `TreeTabbedBrowser._remove_tab()`.
                    moved_children = moved_node.children
                    first_child = moved_children[0]
                    for child in moved_children[1:]:
                        child.parent = first_child

                    moved_node.parent.insert_child(first_child, after=moved_node)
                    displaced_node.parent.insert_child(moved_node, idx=0)

        render()
        self.tree_tab_update()
        self._recursion_guard = False

    def get_tab_fields(self, idx):
        """Add tree field data to normal tab field data."""
        fields = super().get_tab_fields(idx)

        if len(self.tree_root.children) == 0:
            # Presumably the window is still being initialized
            log.misc.vdebug(f"Tree root has no children. Are we starting up? fields={fields}")
            return fields

        rendered_tree = self.tree_root.render()
        tab = self.widget(idx)
        found = [
            prefix
            for prefix, node in rendered_tree
            if node.value == tab
        ]

        if len(found) == 1:
            # we remove the first two chars because every tab is child of tree
            # root and that gets rendered as well
            fields['tree'] = found[0][2:]
            fields['collapsed'] = '[...] ' if tab.node.collapsed else ''
            return fields

        # Beyond here we have a mismatch between the tab widget and the tree.
        # Try to identify known situations where this happens precisely and
        # handle them gracefully. Blow up on unknown situations so we don't
        # miss them.

        # Just sanity checking, we haven't seen this yet.
        assert len(found) == 0, (
            "Found multiple tree nodes with the same tab as value: tab={tab}"
        )

        # Having more tabs in the widget when loading a session with a
        # collapsed group in is a known case. Check for it with a heuristic
        # (for now) and assert if that doesn't look like that's how we got
        # here.
        all_nodes = self.tree_root.traverse()
        node = [n for n in all_nodes if n.value == tab][0]
        is_hidden = any(n.collapsed for n in node.path)

        tabs = [str(self.widget(idx)) for idx in range(self.count())]
        difference = len(rendered_tree) - 1 - len(tabs)
        # empty_urls here is a proxy for "there is a session being loaded into
        # this window"
        empty_urls = all(
            not self.widget(idx).url().toString() for idx in range(self.count())
        )
        if empty_urls and is_hidden:
            # All tabs will be added to the tab widget during session load
            # and they will only be removed later when the widget is
            # updated from the tree. Meanwhile, if we get here we'll have
            # hidden tabs present in the widget but absent from the node.
            # To detect this situation more clearly we could do something like
            # have a is_starting_up or is_loading_session attribute on the
            # tabwidget/tabbbedbrowser. Or have the session manager add all
            # nodes to the tree uncollapsed initially and then go through and
            # collapse them.
            log.misc.vdebug(
                "get_tab_fields() called with different amount of tabs in "
                f"widget vs in the tree: difference={difference} "
                f"tree={rendered_tree[1:]} tabs={tabs}"
            )
        else:
            # If we get here then we have another case to investigate.
            assert difference == 0, (
                "Different amount of nodes in tree than widget. "
                f"difference={difference} tree={rendered_tree[1:]} tabs={tabs}"
            )

        return fields

    def update_tree_tab_positions(self):
        """Update tab positions according to the tree structure."""
        nodes = self.tree_root.traverse(render_collapsed=False)
        for idx, node in enumerate(nodes):
            if idx > 0:
                cur_idx = self.indexOf(node.value)
                self.tabBar().moveTab(cur_idx, idx-1)

    def update_tree_tab_visibility(self):
        """Hide collapsed tabs and show uncollapsed ones.

        Sync the internal tree to the tabs the user can actually see.
        """
        for node in self.tree_root.traverse():
            if node.value is None:
                continue

            should_be_hidden = any(ancestor.collapsed for ancestor in node.path[:-1])
            is_shown = self.indexOf(node.value) != -1
            if should_be_hidden and is_shown:
                # node should be hidden but is shown
                cur_tab = node.value
                idx = self.indexOf(cur_tab)
                if idx != -1:
                    self.removeTab(idx)
            elif not should_be_hidden and not is_shown:
                # node should be shown but is hidden
                parent = node.parent
                tab = node.value
                name = tab.title()
                icon = tab.icon()
                parent_idx = self.indexOf(node.parent.value)
                self.insertTab(parent_idx + 1, tab, icon, name)
                tab.node.parent = parent  # insertTab resets node

    def tree_tab_update(self):
        """Update titles and positions."""
        with self._disable_tab_title_updates():
            self.update_tree_tab_visibility()
            self.update_tree_tab_positions()
        self.update_tab_titles()
