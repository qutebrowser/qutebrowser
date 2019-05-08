# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2019 Giuseppe Stelluto (pinusc) <giuseppe@gstelluto.com>
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

import pytest_bdd as bdd
import re
from qutebrowser.misc import notree
from logging import debug as log


def tree_from_session(session_tree):
    root_data = session_tree.get(1)
    assert(root_data is not None)
    root_node = notree.Node(None)

    def recursive_load_node(uid):
        node_data = session_tree[uid]
        children_uids = node_data['children']

        children = [recursive_load_node(uid) for uid in children_uids]

        new_node = notree.Node(node_data['tab'],
                               parent=root_node, childs=children)

        return new_node

    for child_uid in root_data['children']:
        child = recursive_load_node(child_uid)
        child.parent = root_node

    return root_node


@bdd.given(bdd.parsers.parse("I initialize tree-tabs"))
def init_tree_tabs(quteproc):
    quteproc.set_setting("tabs.tree_tabs", "true")
    quteproc.set_setting("tabs.tabs_are_windows", "false")


@bdd.then(bdd.parsers.parse("the following tree should be shown:\n{tree}"))
def check_open_tabs(quteproc, request, tree):
    """Check the list of open tabs in the session.

    This is a lightweight alternative for "The session should look like: ...".

    It expects a list of URLs, with an optional "(active)" suffix.
    """
    session = quteproc.get_session()
    active_suffix = ' (active)'
    pinned_suffix = ' (pinned)'
    tree = tree.splitlines()
    assert len(session['windows']) == 1
    assert len(session['windows'][0]['tree']) - 1 == len(tree)  # remove root

    # If we don't have (active) anywhere, don't check it
    has_active = any(active_suffix in line for line in tree)
    has_pinned = any(pinned_suffix in line for line in tree)

    session_tree = tree_from_session(session['windows'][0]['tree'])
    rendered = [char + str(n.value['history'][-1]['url'] if n.value else "/")
                for char, n in session_tree.render()]
    log('\n' + '\n'.join(rendered))
    traversed = list(session_tree.traverse())

    pattern = re.compile(r'(.*)- (.*)')
    ancestors = []
    current = None
    min_indent = 0
    for i, line in enumerate(tree):
        match = pattern.match(line)
        indent, url = len(match.group(1)), match.group(2)
        assert(indent % 4 == 0)
        if min_indent is None:
            min_indent = indent
        depth = (indent - min_indent) // 4
        if depth > len(ancestors):
            assert depth == len(ancestors) + 1
            ancestors.append(current)
        elif depth < len(ancestors):
            ancestors = ancestors[:depth]
        current = url
        # line = line.strip()
        # assert line.startswith('- ')
        # line = line[2:]  # remove "- " prefix
        line = url

        active = False
        pinned = False

        while line.endswith(active_suffix) or line.endswith(pinned_suffix):
            if line.endswith(active_suffix):
                # active
                line = line[:-len(active_suffix)]
                active = True
            else:
                # pinned
                line = line[:-len(pinned_suffix)]
                pinned = True

        session_tab = traversed[i + 1]
        current_page = session_tab.value['history'][-1]
        assert current_page['url'] == quteproc.path_to_url(line)
        if ancestors:
            assert session_tab.parent is not None
            assert session_tab.parent.value is not None
            session_parent_url = session_tab.parent.value['history'][-1]['url']
            assert session_parent_url == quteproc.path_to_url(ancestors[-1])
        else:
            assert session_tab.parent is session_tree  # i.e. root
        if active:
            assert session_tab['active']
        elif has_active:
            assert 'active' not in session_tab

        if pinned:
            assert current_page['pinned']
        elif has_pinned:
            assert not current_page['pinned']


bdd.scenarios('tree-tabs.feature')
