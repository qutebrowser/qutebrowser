Feature: Using :navigate

    Scenario: :navigate with invalid argument
        When I run :navigate foo
        Then the error "where: Invalid value foo - expected one of: prev, next, up, increment, decrement" should be shown

    # up

    Scenario: Navigating up
        When I open data/navigate/sub
        And I run :navigate up
        Then data/navigate should be loaded

    # prev/next

    Scenario: Navigating to previous page
        When I open data/navigate
        And I run :navigate prev
        Then data/navigate/prev.html should be loaded

    Scenario: Navigating to next page
        When I open data/navigate
        And I run :navigate next
        Then data/navigate/next.html should be loaded

    Scenario: Navigating to previous page without links
        When I open data/numbers/1.txt
        And I run :navigate prev
        Then the error "No prev links found!" should be shown

    Scenario: Navigating to next page without links
        When I open data/numbers/1.txt
        And I run :navigate next
        Then the error "No forward links found!" should be shown

    Scenario: Navigating to next page to a fragment
        When I open data/navigate#fragment
        And I run :navigate next
        Then data/navigate/next.html should be loaded

    # increment/decrement

    Scenario: Incrementing number in URL
        When I open data/numbers/1.txt
        And I run :navigate increment
        Then data/numbers/2.txt should be loaded

    Scenario: Decrementing number in URL
        When I open data/numbers/4.txt
        And I run :navigate decrement
        Then data/numbers/3.txt should be loaded

    Scenario: Decrementing with no number in URL
        When I open data/navigate
        And I run :navigate decrement
        Then the error "No number found in URL!" should be shown

    Scenario: Incrementing with no number in URL
        When I open data/navigate
        And I run :navigate increment
        Then the error "No number found in URL!" should be shown

    Scenario: Setting url-incdec-segments
        When I set general -> url-incdec-segments to anchor
        And I open data/numbers/1.txt
        And I run :navigate increment
        Then the error "No number found in URL!" should be shown
