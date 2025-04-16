Feature: Tree tab management
    Tests for various :tree-tab-* commands.

    Background:
        # Open a new tree tab enabled window, close everything else
        Given I set tabs.tabs_are_windows to false
        And I set tabs.tree_tabs to true
        And I set tabs.position to left
        And I set tabs.width to 30%
        And I open about:blank?starting%20page in a new window
        And I clean up open tabs
        And I clear the log

    Scenario: Focus previous sibling tab
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-prev --sibling
        Then the following tabs should be open:
            """
            - data/numbers/1.txt (active)
              - data/numbers/2.txt
            - data/numbers/3.txt
            """

    Scenario: Focus next sibling tab
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 1
        And I run :tab-next --sibling
        Then the following tabs should be open:
            """
            - data/numbers/1.txt
              - data/numbers/2.txt
            - data/numbers/3.txt (active)
            """

    Scenario: Closing a tab promotes the first child in its place
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related tab
        And I open data/numbers/3.txt in a new related tab
        And I open data/numbers/4.txt in a new tab
        And I run :tab-focus 1
        And I run :tab-close
        Then the following tabs should be open:
            """
            - data/numbers/2.txt
              - data/numbers/3.txt
            - data/numbers/4.txt
            """

    Scenario: Focus a parent tab
        When I open data/numbers/1.txt
        And I open data/numbers/3.txt in a new related tab
        And I open data/numbers/2.txt in a new sibling tab
        And I run :tab-focus parent
        Then the following tabs should be open:
            """
            - data/numbers/1.txt (active)
              - data/numbers/2.txt
              - data/numbers/3.txt
            """

    Scenario: :tab-close --recursive
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related tab
        And I open data/numbers/3.txt in a new related tab
        And I open data/numbers/4.txt in a new tab
        And I run :tab-focus 1
        And I run :tab-close --recursive
        Then the following tabs should be open:
            """
            - data/numbers/4.txt
            """

    Scenario: :tab-close --recursive with pinned tab
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related tab
        And I open data/numbers/3.txt in a new related tab
        And I open data/numbers/4.txt in a new tab
        And I run :tab-focus 1
        And I run :cmd-run-with-count 2 tab-pin
        And I run :tab-close --recursive
        And I wait for "Asking question *" in the log
        And I run :prompt-accept yes
        Then the following tabs should be open:
            """
            - data/numbers/4.txt
            """

    Scenario: :tab-close --recursive with collapsed subtree
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related tab
        And I open data/numbers/3.txt in a new related tab
        And I open data/numbers/4.txt in a new tab
        And I run :tab-focus 2
        And I run :tree-tab-toggle-hide
        And I run :tab-focus 1
        And I run :tab-close --recursive
        Then the following tabs should be open:
            """
            - data/numbers/4.txt
            """

    Scenario: :tab-give --recursive with collapsed subtree
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related tab
        And I open data/numbers/3.txt in a new sibling tab
        And I open data/numbers/4.txt in a new related tab
        And I open data/numbers/5.txt in a new tab
        And I run :tab-focus 2
        And I run :tree-tab-toggle-hide
        And I run :tab-focus 1
        And I run :tab-give --recursive
        And I wait until data/numbers/4.txt is loaded
        Then the session should look like:
            """
            windows:
            - tabs:
              - history:
                - url: http://localhost:*/data/numbers/5.txt
            - tabs:
              - history:
                - url: http://localhost:*/data/numbers/1.txt
              - history:
                - url: http://localhost:*/data/numbers/3.txt
              - history:
                - url: http://localhost:*/data/numbers/4.txt
              - history:
                - url: http://localhost:*/data/numbers/2.txt
            """
        And I run :window-only
        And the following tabs should be open:
            """
            - data/numbers/1.txt (active)
              - data/numbers/3.txt (collapsed)
                - data/numbers/4.txt
              - data/numbers/2.txt
            """

    Scenario: Open a child tab
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related tab
        Then the following tabs should be open:
            """
            - data/numbers/1.txt
              - data/numbers/2.txt (active)
            """

    Scenario: Move a tab down to the given index
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related tab
        And I open data/numbers/3.txt in a new tab
        And I open data/numbers/4.txt in a new related tab
        And I run :tab-focus 3
        And I run :tab-move 1
        Then the following tabs should be open:
            """
            - data/numbers/3.txt
              - data/numbers/4.txt
            - data/numbers/1.txt
              - data/numbers/2.txt
            """

    Scenario: Move a tab up to given index
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related tab
        And I open data/numbers/3.txt in a new tab
        And I open data/numbers/4.txt in a new related tab
        And I run :tab-move 2
        Then the following tabs should be open:
            """
            - data/numbers/1.txt
              - data/numbers/4.txt
              - data/numbers/2.txt
            - data/numbers/3.txt
            """

    Scenario: Move a tab within siblings
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related tab
        And I open data/numbers/3.txt in a new sibling tab
        And I run :tab-move +
        Then the following tabs should be open:
            """
            - data/numbers/1.txt
              - data/numbers/2.txt
              - data/numbers/3.txt
            """

    Scenario: Move a tab to end
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related tab
        And I open data/numbers/3.txt in a new tab
        And I open data/numbers/4.txt in a new related tab
        And I run :tab-focus 2
        And I run :tab-move end
        Then the following tabs should be open:
            """
            - data/numbers/1.txt
            - data/numbers/3.txt
              - data/numbers/4.txt
              - data/numbers/2.txt
            """

    Scenario: Move a tab to start
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related tab
        And I open data/numbers/3.txt in a new tab
        And I open data/numbers/4.txt in a new related tab
        And I run :tab-move start
        Then the following tabs should be open:
            """
            - data/numbers/4.txt
            - data/numbers/1.txt
              - data/numbers/2.txt
            - data/numbers/3.txt
            """

    Scenario: Collapse a subtree
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related tab
        And I open data/numbers/3.txt in a new related tab
        And I run :tab-focus 2
        And I run :tree-tab-toggle-hide
        Then the following tabs should be open:
            """
            - data/numbers/1.txt
              - data/numbers/2.txt (active) (collapsed)
                - data/numbers/3.txt
            """

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
            """
            - data/numbers/1.txt
              - data/numbers/2.txt (active) (collapsed)
                - data/numbers/3.txt
            """

    Scenario: Uncollapse a subtree
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related tab
        And I open data/numbers/3.txt in a new related tab
        And I run :tab-focus 2
        And I run :tree-tab-toggle-hide
        And I run :tree-tab-toggle-hide
        Then the following tabs should be open:
            """
            - data/numbers/1.txt
              - data/numbers/2.txt (active)
                - data/numbers/3.txt
            """

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
          """
          - data/numbers/1.txt
            - data/numbers/2.txt (active) (collapsed)
              - data/numbers/3.txt
          - data/numbers/4.txt
          """

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
          """
          - about:blank?grandparent
            - about:blank?parent (active)
              - about:blank?child
          """

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
          """
          - about:blank?child (active)
          - about:blank?grandparent
          """

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
          """
          - about:blank?child (active)
            - about:blank?leaf
          - about:blank?grandparent
          """

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
          """
          - about:blank?grandparent
            - about:blank?parent (active)
          """

    Scenario: Undo a complex tree structure close
        When I open about:blank?one
        And I open about:blank?two in a new related tab
        And I open about:blank?three in a new related tab
        When I open about:blank?four in a new tab
        And I open about:blank?five in a new related tab
        And I run :tab-select ?two
        And I run :tab-only
        And I run :undo
        Then the following tabs should be open:
          """
          - about:blank?one (active)
            - about:blank?two
              - about:blank?three
          - about:blank?four
            - about:blank?five
          """

    Scenario: Tabs.select_on_remove prev selects previous sibling
        When I open about:blank?one
        And I open about:blank?two in a new related tab
        And I open about:blank?three in a new tab
        And I run :set tabs.select_on_remove prev
        And I run :tab-close
        And I run :config-unset tabs.select_on_remove
        Then the following tabs should be open:
          """
          - about:blank?one (active)
            - about:blank?two
          """

    Scenario: Tabs.select_on_remove prev selects parent
        When I open about:blank?one
        And I open about:blank?two in a new related tab
        And I open about:blank?three in a new sibling tab
        And I run :set tabs.select_on_remove prev
        And I run :tab-close
        And I run :config-unset tabs.select_on_remove
        Then the following tabs should be open:
          """
          - about:blank?one (active)
            - about:blank?two
          """

    Scenario: Tabs.select_on_remove prev can be overridden
        When I open about:blank?one
        And I open about:blank?two in a new related tab
        And I open about:blank?three in a new tab
        And I run :tab-select ?two
        And I run :set tabs.select_on_remove prev
        And I run :tab-close --next
        And I run :config-unset tabs.select_on_remove
        Then the following tabs should be open:
          """
          - about:blank?one
          - about:blank?three (active)
          """

    ## :tab-move, but with trees
    Scenario: Move tab out of a group
        When I open about:blank?one
        And I open about:blank?two in a new related tab
        And I open about:blank?three in a new related tab
        And I open about:blank?four in a new tab
        And I run :tab-select ?three
        And I run :tab-move 4
        Then the following tabs should be open:
          # one
          #   two
          #     three (active)
          # four
          """
          - about:blank?one
            - about:blank?two
          - about:blank?four
          - about:blank?three (active)
          """

    Scenario: Move multiple tabs out of a group
        When I open about:blank?one
        And I open about:blank?two in a new related tab
        And I open about:blank?three in a new related tab
        And I open about:blank?four in a new tab
        And I open about:blank?five in a new related tab
        And I run :tab-select ?two
        And I run :tab-move 4
        Then the following tabs should be open:
          # one
          #   two (active)
          #     three
          # four
          #   five
          """
          - about:blank?one
          - about:blank?four
            - about:blank?five
          - about:blank?two (active)
            - about:blank?three
          """

    Scenario: Move two sibling groups
        When I open about:blank?one
        And I open about:blank?two in a new related tab
        And I open about:blank?three in a new tab
        And I open about:blank?four in a new related tab
        And I run :tab-select ?three
        And I run :tab-move 1
        Then the following tabs should be open:
          # one
          #   two
          # three (active)
          #   four
          """
          - about:blank?three (active)
            - about:blank?four
          - about:blank?one
            - about:blank?two
          """

    Scenario: Move multiple tabs into another group
        When I open about:blank?one
        And I open about:blank?two in a new related tab
        And I open about:blank?three in a new related tab
        And I open about:blank?four in a new tab
        And I open about:blank?five in a new related tab
        And I run :tab-select ?two
        And I run :tab-move 5
        Then the following tabs should be open:
          # one
          #   two (active)
          #     three
          # four
          #   five
          """
          - about:blank?one
          - about:blank?four
            - about:blank?five
            - about:blank?two
              - about:blank?three
          """

    Scenario: Move a tab a single step over a group
        When I open about:blank?one
        And I open about:blank?two in a new tab
        And I open about:blank?three in a new related tab
        And I run :tab-select ?one
        And I run :tab-move 2
        Then the following tabs should be open:
          # one (active)
          # two
          #   three
          """
          - about:blank?two
            - about:blank?three
          - about:blank?one
          """

    ## Move tabs via mouse drags
    Scenario: Drag a tab down between siblings
        When I open about:blank?one
        And I open about:blank?two in a new tab
        And I run :tab-select ?one
        And I run :debug-mouse-move +
        Then the following tabs should be open:
          # one (active)
          # two
          """
          - about:blank?two
          - about:blank?one (active)
          """

    Scenario: Drag a tab down out of a group
        When I open about:blank?one
        And I open about:blank?two in a new related tab
        And I open about:blank?three in a new related tab
        And I open about:blank?four in a new tab
        And I run :tab-select ?three
        And I run :debug-mouse-move +
        Then the following tabs should be open:
          # one
          #   two
          #     three (active)
          # four
          """
          - about:blank?one
            - about:blank?two
          - about:blank?four
          - about:blank?three (active)
          """

    Scenario: Drag a tab down out of a group into another
        When I open about:blank?one
        And I open about:blank?two in a new related tab
        And I open about:blank?three in a new related tab
        And I open about:blank?four in a new tab
        And I open about:blank?five in a new related tab
        And I run :tab-select ?three
        And I run :debug-mouse-move +
        Then the following tabs should be open:
          # one
          #   two
          #     three (active)
          # four
          #   five
          """
          - about:blank?one
            - about:blank?two
          - about:blank?four
            - about:blank?three (active)
            - about:blank?five
          """

    Scenario: Drag a tab down a group
        When I open about:blank?one
        And I open about:blank?two in a new related tab
        And I open about:blank?three in a new related tab
        And I open about:blank?four in a new tab
        And I run :tab-select ?two
        And I run :debug-mouse-move +
        Then the following tabs should be open:
          # one
          #   two (active)
          #     three
          # four
          """
          - about:blank?one
            - about:blank?three
              - about:blank?two (active)
          - about:blank?four
          """

    Scenario: Drag a tab with children down a group
        When I open about:blank?one
        And I open about:blank?two in a new related tab
        And I open about:blank?five in a new related tab
        And I open about:blank?three in a new sibling tab
        And I open about:blank?four in a new related tab
        And I open about:blank?six in a new tab
        And I run :tab-select ?two
        And I run :debug-mouse-move +
        Then the following tabs should be open:
          # one
          #   two (active)
          #     three
          #       four
          #     five
          # six
          """
          - about:blank?one
            - about:blank?three
              - about:blank?two (active)
                - about:blank?four
              - about:blank?five
          - about:blank?six
          """

    # uppies

    ## Move tabs via mouse drags
    Scenario: Drag a tab up between siblings
        When I open about:blank?one
        And I open about:blank?two in a new tab
        And I open about:blank?three in a new related tab
        And I run :tab-select ?two
        And I run :debug-mouse-move -
        Then the following tabs should be open:
          # one (active)
          # two
          #   three
          """
          - about:blank?two (active)
          - about:blank?one
            - about:blank?three
          """

    Scenario: Drag a tab up out of a group
        When I open about:blank?one
        And I open about:blank?two in a new tab
        And I open about:blank?three in a new related tab
        And I open about:blank?four in a new related tab
        And I run :tab-select ?three
        And I run :debug-mouse-move -
        Then the following tabs should be open:
          # one
          # two
          #   three (active)
          #     four
          """
          - about:blank?one
          - about:blank?three (active)
            - about:blank?two
              - about:blank?four
          """

    Scenario: Drag a tab with children up into a group
        When I open about:blank?one
        And I open about:blank?two in a new related tab
        And I open about:blank?three in a new tab
        And I open about:blank?four in a new related tab
        And I open about:blank?five in a new tab
        And I run :tab-select ?three
        And I run :debug-mouse-move -
        Then the following tabs should be open:
          # one
          #   two
          # three (active)
          #   four
          # five
          """
          - about:blank?one
            - about:blank?three (active)
            - about:blank?two
          - about:blank?four
          - about:blank?five
          """

    Scenario: Drag a tab up a group
        When I open about:blank?one
        And I open about:blank?two in a new related tab
        And I open about:blank?three in a new related tab
        And I open about:blank?four in a new tab
        And I run :tab-select ?three
        And I run :debug-mouse-move -
        Then the following tabs should be open:
          # one
          #   two (active)
          #     three
          # four
          """
          - about:blank?one
            - about:blank?three (active)
              - about:blank?two
          - about:blank?four
          """

    Scenario: Drag a tab with children up a group
        When I open about:blank?one
        And I open about:blank?two in a new related tab
        And I open about:blank?five in a new related tab
        And I open about:blank?three in a new sibling tab
        And I open about:blank?four in a new related tab
        And I open about:blank?six in a new tab
        And I run :tab-select ?three
        And I run :debug-mouse-move -
        Then the following tabs should be open:
          # one
          #   two
          #     three (active)
          #       four
          #     five
          # six
          """
          - about:blank?one
            - about:blank?three (active)
              - about:blank?two
                - about:blank?four
              - about:blank?five
          - about:blank?six
          """
