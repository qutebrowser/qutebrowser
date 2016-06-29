Feature: Scrolling
    Tests the various scroll commands.

    Background:
        Given I open data/scroll.html
        And I run :tab-only

    ## :scroll-px

    Scenario: Scrolling pixel-wise vertically
        When I run :scroll-px 0 10
        Then the page should be scrolled vertically

    Scenario: Scrolling pixel-wise horizontally
        When I run :scroll-px 10 0
        Then the page should be scrolled horizontally

    Scenario: Scrolling down and up
        When I run :scroll-px 10 0
        And I run :scroll-px -10 0
        Then the page should not be scrolled

    Scenario: Scrolling right and left
        When I run :scroll-px 0 10
        And I run :scroll-px 0 -10
        Then the page should not be scrolled

    Scenario: Scrolling down and up with count
        When I run :scroll-px 0 10 with count 2
        When I run :scroll-px 0 -10
        When I run :scroll-px 0 -10
        Then the page should not be scrolled

    Scenario: Scrolling left and right with count
        When I run :scroll-px 10 0 with count 2
        When I run :scroll-px -10 0
        When I run :scroll-px -10 0
        Then the page should not be scrolled

    Scenario: :scroll-px with a very big value
        When I run :scroll-px 99999999999 0
        Then the error "Numeric argument is too large for internal int representation." should be shown

    Scenario: :scroll-px on a page without scrolling
        When I open data/hello.txt
        And I run :scroll-px 10 10
        Then no crash should happen

    Scenario: :scroll-px with floats
        # This used to be allowed, but doesn't make much sense.
        When I run :scroll-px 2.5 2.5
        Then the error "dx: Invalid int value 2.5" should be shown
        And the page should not be scrolled

    ## :scroll

    Scenario: Scrolling down
        When I run :scroll down
        Then the page should be scrolled vertically

    Scenario: Scrolling down and up
        When I run :scroll down
        And I run :scroll up
        Then the page should not be scrolled

    Scenario: Scrolling right
        When I run :scroll right
        Then the page should be scrolled horizontally

    Scenario: Scrolling right and left
        When I run :scroll right
        And I run :scroll left
        Then the page should not be scrolled

    Scenario: Scrolling with page down
        When I run :scroll page-down
        Then the page should be scrolled vertically

    Scenario: Scrolling with page down and page up
        When I run :scroll page-down
        And I run :scroll page-up
        Then the page should not be scrolled

    Scenario: Scrolling to bottom
        When I run :scroll bottom
        Then the page should be scrolled vertically

    Scenario: Scrolling to bottom and to top
        When I run :scroll bottom
        And I run :scroll top
        Then the page should not be scrolled

    Scenario: :scroll with invalid argument
        When I run :scroll foobar
        Then the error "Invalid value 'foobar' for direction - expected one of: bottom, down, left, page-down, page-up, right, top, up" should be shown
        And the page should not be scrolled

    Scenario: Scrolling down and up with count
        When I run :scroll down with count 2
        And I run :scroll up
        And I run :scroll up
        Then the page should not be scrolled

    Scenario: Scrolling right
        When I run :scroll right
        Then the page should be scrolled horizontally

    Scenario: Scrolling right and left
        When I run :scroll right
        And I run :scroll left
        Then the page should not be scrolled

    Scenario: Scrolling right and left with count
        When I run :scroll right with count 2
        And I run :scroll left
        And I run :scroll left
        Then the page should not be scrolled

    Scenario: Scrolling down with a very big count
        When I run :scroll down with count 99999999999
        # Make sure it doesn't hang
        And I run :message-info "Still alive!"
        Then the message "Still alive!" should be shown

    Scenario: :scroll on a page without scrolling
        When I open data/hello.txt
        And I run :scroll down
        Then no crash should happen

    ## :scroll-perc

    Scenario: Scrolling to bottom with :scroll-perc
        When I run :scroll-perc 100
        Then the page should be scrolled vertically

    Scenario: Scrolling to bottom and to top with :scroll-perc
        When I run :scroll-perc 100
        And I run :scroll-perc 0
        Then the page should not be scrolled

    Scenario: Scrolling to middle with :scroll-perc
        When I run :scroll-perc 50
        Then the page should be scrolled vertically

    Scenario: Scrolling to middle with :scroll-perc (float)
        When I run :scroll-perc 50.5
        Then the page should be scrolled vertically

    Scenario: Scrolling to middle and to top with :scroll-perc
        When I run :scroll-perc 50
        And I run :scroll-perc 0
        Then the page should not be scrolled

    Scenario: Scrolling to right with :scroll-perc
        When I run :scroll-perc --horizontal 100
        Then the page should be scrolled horizontally

    Scenario: Scrolling to right and to left with :scroll-perc
        When I run :scroll-perc --horizontal 100
        And I run :scroll-perc --horizontal 0
        Then the page should not be scrolled

    Scenario: Scrolling to middle (horizontally) with :scroll-perc
        When I run :scroll-perc --horizontal 50
        Then the page should be scrolled horizontally

    Scenario: Scrolling to middle and to left with :scroll-perc
        When I run :scroll-perc --horizontal 50
        And I run :scroll-perc --horizontal 0
        Then the page should not be scrolled

    Scenario: :scroll-perc without argument
        When I run :scroll-perc
        Then the page should be scrolled vertically

    Scenario: :scroll-perc without argument and --horizontal
        When I run :scroll-perc --horizontal
        Then the page should be scrolled horizontally

    Scenario: :scroll-perc with count
        When I run :scroll-perc with count 50
        Then the page should be scrolled vertically

    Scenario: :scroll-perc with a very big value
        When I run :scroll-perc 99999999999
        Then no crash should happen

    Scenario: :scroll-perc on a page without scrolling
        When I open data/hello.txt
        And I run :scroll-perc 20
        Then no crash should happen

    Scenario: :scroll-perc with count and argument
        When I run :scroll-perc 0 with count 50
        Then the page should be scrolled vertically

    ## :scroll-page

    Scenario: Scrolling down with :scroll-page
        When I run :scroll-page 0 1
        Then the page should be scrolled vertically

    Scenario: Scrolling down with :scroll-page (float)
        When I run :scroll-page 0 1.5
        Then the page should be scrolled vertically

    Scenario: Scrolling down and up with :scroll-page
        When I run :scroll-page 0 1
        And I run :scroll-page 0 -1
        Then the page should not be scrolled

    Scenario: Scrolling right with :scroll-page
        When I run :scroll-page 1 0
        Then the page should be scrolled horizontally

    Scenario: Scrolling right with :scroll-page (float)
        When I run :scroll-page 1.5 0
        Then the page should be scrolled horizontally

    Scenario: Scrolling right and left with :scroll-page
        When I run :scroll-page 1 0
        And I run :scroll-page -1 0
        Then the page should not be scrolled

    Scenario: Scrolling right and left with :scroll-page and count
        When I run :scroll-page 1 0 with count 2
        And I run :scroll-page -1 0
        And I run :scroll-page -1 0
        Then the page should not be scrolled

    Scenario: :scroll-page with --bottom-navigate
        When I run :scroll-perc 100
        And I run :scroll-page --bottom-navigate next 0 1
        Then data/hello2.txt should be loaded

    Scenario: :scroll-page with --top-navigate
        When I run :scroll-page --top-navigate prev 0 -1
        Then data/hello3.txt should be loaded

    Scenario: :scroll-page with a very big value
        When I run :scroll-page 99999999999 99999999999
        Then the error "Numeric argument is too large for internal int representation." should be shown

    Scenario: :scroll-page on a page without scrolling
        When I open data/hello.txt
        And I run :scroll-page 1 1
        Then no crash should happen
