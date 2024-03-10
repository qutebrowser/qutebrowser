Feature: Tree tab management
    Tests for various :tree-tab-* commands.

    Background:
        # Open a new tree tab enabled window, close everything else
        Given I set tabs.tabs_are_windows to false
        And I set tabs.tree_tabs to true
        And I open about:blank?starting%20page in a new window
        And I clean up open tabs
        And I clear the log

    Scenario: :tab-close --recursive
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related tab
        And I open data/numbers/3.txt in a new related tab
        And I open data/numbers/4.txt in a new tab
        And I run :tab-focus 1
        And I run :tab-close --recursive
        Then the following tabs should be open:
            - data/numbers/4.txt

    Scenario: Open a child tab
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related tab
        Then the following tabs should be open:
            - data/numbers/1.txt
              - data/numbers/2.txt (active)

    Scenario: Collapse a subtree
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related tab
        And I open data/numbers/3.txt in a new related tab
        And I run :tab-focus 2
        And I run :tree-tab-toggle-hide
        Then the following tabs should be open:
            - data/numbers/1.txt
              - data/numbers/2.txt (active) (collapsed)
                - data/numbers/3.txt

    Scenario: Load a collapsed subtree
        # Same setup as above
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related tab
        And I open data/numbers/3.txt in a new related tab
        And I run :tab-focus 2
        And I run :tree-tab-toggle-hide
        # Now actually load the saved session
        And I run :session-save foo
        And I run :session-load -c foo
        And I wait until data/numbers/1.txt is loaded
        And I wait until data/numbers/2.txt is loaded
        And I wait until data/numbers/3.txt is loaded
        # And of course the same assertion as above too
        Then the following tabs should be open:
            - data/numbers/1.txt
              - data/numbers/2.txt (active) (collapsed)
                - data/numbers/3.txt

    Scenario: Uncollapse a subtree
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related tab
        And I open data/numbers/3.txt in a new related tab
        And I run :tab-focus 2
        And I run :tree-tab-toggle-hide
        And I run :tree-tab-toggle-hide
        Then the following tabs should be open:
            - data/numbers/1.txt
              - data/numbers/2.txt (active)
                - data/numbers/3.txt

    # Same as a test in sessions.feature but tree tabs and the related
    # settings.
    Scenario: TreeTabs: Loading a session with tabs.new_position.related=prev
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related tab
        And I open data/numbers/3.txt in a new related tab
        And I open data/numbers/4.txt in a new tab
        And I run :tab-focus 2
        And I run :tree-tab-toggle-hide
        And I run :session-save foo
        And I set tabs.new_position.related to prev
        And I set tabs.new_position.tree.new_child to last
        And I set tabs.new_position.tree.new_toplevel to prev
        And I run :session-load -c foo
        And I wait until data/numbers/1.txt is loaded
        And I wait until data/numbers/2.txt is loaded
        And I wait until data/numbers/3.txt is loaded
        And I wait until data/numbers/4.txt is loaded
        Then the following tabs should be open:
          - data/numbers/1.txt
            - data/numbers/2.txt (active) (collapsed)
              - data/numbers/3.txt
          - data/numbers/4.txt

    Scenario: Undo a tab close restores tree structure
        # Restored node should be put back in the right place in the tree with
        # same parent and child.
        When I open about:blank?grandparent
        And I open about:blank?parent in a new related tab
        And I open about:blank?child in a new related tab
        And I run :tab-select ?parent
        And I run :tab-close
        And I run :undo
        Then the following tabs should be open:
          - about:blank?grandparent
            - about:blank?parent (active)
              - about:blank?child

    Scenario: Undo a tab close when the parent has already been closed
        # Close the child first, then the parent. When the child is restored
        # it should be placed back at the root.
        When I open about:blank?grandparent
        And I open about:blank?parent in a new related tab
        And I open about:blank?child in a new related tab
        And I run :tab-close
        And I run :tab-close
        And I run :undo 2
        Then the following tabs should be open:
          - about:blank?child (active)
          - about:blank?grandparent

    Scenario: Undo a tab close when the parent has already been closed - with children
        # Close the child first, then the parent. When the child is restored
        # it should be placed back at the root, and its previous child should
        # be re-attached to it. (Not sure if this is the best behavior.)
        When I open about:blank?grandparent
        And I open about:blank?parent in a new related tab
        And I open about:blank?child in a new related tab
        And I open about:blank?leaf in a new related tab
        And I run :tab-select ?child
        And I run :tab-close
        And I run :tab-select ?parent
        And I run :tab-close
        And I run :undo 2
        Then the following tabs should be open:
          - about:blank?child (active)
            - about:blank?leaf
          - about:blank?grandparent

    Scenario: Undo a tab close when the child has already been closed
        # Close the parent first, then the child. Make sure we don't crash
        # when trying to re-parent the child.
        When I open about:blank?grandparent
        And I open about:blank?parent in a new related tab
        And I open about:blank?child in a new related tab
        And I run :tab-select ?parent
        And I run :tab-close
        And I run :tab-close
        And I run :undo 2
        Then the following tabs should be open:
          - about:blank?grandparent
            - about:blank?parent (active)
