Feature: Tab management
    Tests for various :tab-* commands.

    Background:
        Given I clean up open tabs

    # :tab-close

    Scenario: :tab-close
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-close
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt (active)

    Scenario: :tab-close with count
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-close with count 1
        Then the following tabs should be open:
            - data/numbers/2.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-close with invalid count
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-close with count 23
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-close with select-on-remove = right
        When I set tabs -> select-on-remove to right
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-close with select-on-remove = left
        When I set tabs -> select-on-remove to left
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close
        Then the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/3.txt

    Scenario: :tab-close with select-on-remove = previous
        When I set tabs -> select-on-remove to previous
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I open data/numbers/4.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/3.txt
            - data/numbers/4.txt (active)

    Scenario: :tab-close with select-on-remove = left and --right
        When I set tabs -> select-on-remove to left
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close --right
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-close with select-on-remove = right and --left
        When I set tabs -> select-on-remove to right
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close --left
        Then the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/3.txt

    Scenario: :tab-close with select-on-remove = left and --opposite
        When I set tabs -> select-on-remove to left
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close --opposite
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-close with select-on-remove = right and --opposite
        When I set tabs -> select-on-remove to right
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close --opposite
        Then the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/3.txt

    Scenario: :tab-close with select-on-remove = previous and --opposite
        When I set tabs -> select-on-remove to previous
        And I run :tab-close --opposite
        Then the error "-o is not supported with 'tabs->select-on-remove' set to 'previous'!" should be shown

    Scenario: :tab-close should restore selection behaviour
        When I set tabs -> select-on-remove to right
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I open data/numbers/4.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close --left
        And I run :tab-focus 2
        And I run :tab-close
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/4.txt (active)

    # :tab-only

    Scenario: :tab-only
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-only
        Then the following tabs should be open:
            - data/numbers/3.txt (active)

    Scenario: :tab-only with --left
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-only --left
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt (active)

    Scenario: :tab-only with --right
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-only --right
        Then the following tabs should be open:
            - data/numbers/2.txt (active)
            - data/numbers/3.txt

    Scenario: :tab-only with --left and --right
        When I run :tab-only --left --right
        Then the error "Only one of -l/-r can be given!" should be shown

    # :tab-focus

    Scenario: :tab-focus with invalid index
        When I run :tab-focus foo
        Then the error "Invalid value foo." should be shown

    Scenario: :tab-focus with index
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt (active)
            - data/numbers/3.txt

    Scenario: :tab-focus without index/count
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-focus
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-focus with invalid index
        When I run :tab-focus 23
        Then the error "There's no tab with index 23!" should be shown

    Scenario: :tab-focus with very big index
        When I run :tab-focus 99999999999999
        Then the error "Numeric argument is too large for internal int representation." should be shown

    Scenario: :tab-focus with count
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus with count 2
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt (active)
            - data/numbers/3.txt

    Scenario: :tab-focus with count and index
        When I run :tab-focus 2 with count 2
        Then the error "Both count and argument given!" should be shown

    Scenario: :tab-focus last
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 1
        And I run :tab-focus 3
        And I run :tab-focus last
        Then the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/2.txt
            - data/numbers/3.txt

    Scenario: :tab-focus last with no last focused tab
        Given I have a fresh instance
        And I run :tab-focus last
        Then the error "No last focused tab!" should be shown

    # tab-prev/tab-next

    Scenario: :tab-prev
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I run :tab-prev
        Then the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/2.txt

    Scenario: :tab-next
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I run :tab-focus 1
        And I run :tab-next
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt (active)

    Scenario: :tab-prev with count
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-prev with count 2
        Then the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/2.txt
            - data/numbers/3.txt

    Scenario: :tab-next with count
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 1
        And I run :tab-next with count 2
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-prev on first tab without wrap
        When I set tabs -> wrap to false
        And I open data/numbers/1.txt
        And I run :tab-prev
        Then the error "First tab" should be shown

    Scenario: :tab-next with last tab without wrap
        When I set tabs -> wrap to false
        And I open data/numbers/1.txt
        And I run :tab-next
        Then the error "Last tab" should be shown

    Scenario: :tab-prev on first tab with wrap
        When I set tabs -> wrap to true
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 1
        And I run :tab-prev
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-next with last tab with wrap
        When I set tabs -> wrap to true
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-next
        Then the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/2.txt
            - data/numbers/3.txt

    Scenario: :tab-next with last tab, wrap and count
        When I set tabs -> wrap to true
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-next with count 2
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt (active)
            - data/numbers/3.txt
