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
