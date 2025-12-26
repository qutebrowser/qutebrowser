Feature: Tab selection on remove (firefox behavior)
    Tests for tabs.select_on_remove = firefox

    Background:
        Given I clean up open tabs
        And I set tabs.tabs_are_windows to false
        And I set tabs.background to false
        And I clear the log

    Scenario: :tab-close with tabs.select_on_remove = firefox
        When I set tabs.select_on_remove to firefox
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I open data/numbers/4.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close
        Then the following tabs should be open:
            """
            - data/numbers/1.txt
            - data/numbers/3.txt (active)
            - data/numbers/4.txt
            """

    Scenario: :tab-close with tabs.select_on_remove = firefox
        When I set tabs.select_on_remove to firefox
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 1
        And I open data/numbers/4.txt in a new tab
        And I run :tab-close
        Then the following tabs should be open:
            """
            - data/numbers/1.txt (active)
            - data/numbers/2.txt
            - data/numbers/3.txt
            """

    Scenario: Error with --opposite
        When I set tabs.select_on_remove to firefox
        And I run :tab-close --opposite
        Then the error "-o is not supported with 'tabs.select_on_remove' set to 'firefox'!" should be shown

    Scenario: Override with --next
        When I set tabs.select_on_remove to firefox
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I open data/numbers/4.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close --next
        Then the following tabs should be open:
            """
            - data/numbers/1.txt
            - data/numbers/3.txt (active)
            - data/numbers/4.txt
            """

    Scenario: Override with --prev
        When I set tabs.select_on_remove to firefox
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I open data/numbers/4.txt in a new tab
        And I run :tab-focus 3
        And I run :tab-close --prev
        Then the following tabs should be open:
            """
            - data/numbers/1.txt
            - data/numbers/2.txt (active)
            - data/numbers/4.txt
            """

    Scenario: :tab-close with tabs.select_on_remove = firefox and --opposite
        When I set tabs.select_on_remove to firefox
        And I run :tab-close --opposite
        Then the error "-o is not supported with 'tabs.select_on_remove' set to 'firefox'!" should be shown
