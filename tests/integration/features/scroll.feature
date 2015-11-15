Feature: Scrolling
    Tests the various scroll commands.

    Background:
        Given I open data/scroll.html
        And I run :tab-only

    ## :scroll-px

    Scenario: Scrolling pixel-wise vertically
        When I run :scroll-px 0 10
        Then the page should be scrolled vertically.

    Scenario: Scrolling pixel-wise horizontally
        When I run :scroll-px 10 0
        Then the page should be scrolled horizontally.

    ## :scroll

    Scenario: Scrolling down
        When I run :scroll down
        Then the page should be scrolled vertically.

    Scenario: Scrolling down and up
        When I run :scroll down
        And I run :scroll up
        Then the page should not be scrolled.

    Scenario: Scrolling right
        When I run :scroll right
        Then the page should be scrolled horizontally.

    Scenario: Scrolling right and left
        When I run :scroll right
        And I run :scroll left
        Then the page should not be scrolled.

    Scenario: Scrolling with page down
        When I run :scroll page-down
        Then the page should be scrolled vertically.

    Scenario: Scrolling with page down and page up
        When I run :scroll page-down
        And I run :scroll page-up
        Then the page should not be scrolled.

    Scenario: Scrolling to bottom
        When I run :scroll bottom
        Then the page should be scrolled vertically.

    Scenario: Scrolling to bottom and to top
        When I run :scroll bottom
        And I run :scroll top
        Then the page should not be scrolled.

    Scenario: :scroll with invalid argument
        When I run :scroll foobar
        Then the error "Invalid value 'foobar' for direction - expected one of: bottom, down, left, page-down, page-up, right, top, up" should be shown.
        And the page should not be scrolled.

    Scenario: :scroll with deprecated pixel argument
        When I run :scroll 0 10
        Then the warning ":scroll with dx/dy arguments is deprecated - use :scroll-px instead!" should be shown.
        Then the page should be scrolled vertically.
