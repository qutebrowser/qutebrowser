Feature: Tree tab management
    Tests for various :tree-tab-* commands.

    Background:
        # Open a new tree tab enabled window, close everything else
        Given I set tabs.tabs_are_windows to false
        And I set tabs.tree_tabs to true
        And I open about:blank?starting%20page in a new window
        And I clean up open tabs
        And I clear the log

    Scenario: Closing a tab promotes the first child in its place
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related tab
        And I open data/numbers/3.txt in a new related tab
        And I open data/numbers/4.txt in a new tab
        And I run :tab-focus 1
        And I run :tab-close
        Then the following tabs should be open:
            - data/numbers/2.txt
              - data/numbers/3.txt
            - data/numbers/4.txt

    Scenario: Focus a parent tab
        When I open data/numbers/1.txt
        And I open data/numbers/3.txt in a new related tab
        And I open data/numbers/2.txt in a new sibling tab
        And I run :tab-focus parent
        Then the following tabs should be open:
            - data/numbers/1.txt (active)
              - data/numbers/2.txt
              - data/numbers/3.txt

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
