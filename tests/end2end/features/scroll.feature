# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Scrolling
    Tests the various scroll commands.

    Background:
        Given I open data/scroll/simple.html
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
        And I wait until the scroll position changed to 10/0
        And I run :scroll-px -10 0
        And I wait until the scroll position changed to 0/0
        Then the page should not be scrolled

    Scenario: Scrolling right and left
        When I run :scroll-px 0 10
        And I wait until the scroll position changed to 0/10
        And I run :scroll-px 0 -10
        And I wait until the scroll position changed to 0/0
        Then the page should not be scrolled

    Scenario: Scrolling down and up with count
        When I run :scroll-px 0 10 with count 2
        And I wait until the scroll position changed to 0/20
        When I run :scroll-px 0 -10
        When I run :scroll-px 0 -10
        And I wait until the scroll position changed to 0/0
        Then the page should not be scrolled

    @qtwebengine_flaky
    Scenario: Scrolling left and right with count
        When I run :scroll-px 10 0 with count 2
        And I wait until the scroll position changed to 20/0
        When I run :scroll-px -10 0
        When I run :scroll-px -10 0
        And I wait until the scroll position changed to 0/0
        Then the page should not be scrolled

    Scenario: :scroll-px with a very big value
        When I run :scroll-px 99999999999 0
        Then the error "Numeric argument is too large for internal int representation." should be shown

    Scenario: :scroll-px on a page without scrolling
        When I open data/hello.txt
        And I run :scroll-px 10 10
        Then the page should not be scrolled

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
        And I wait until the scroll position changed
        And I run :scroll up
        And I wait until the scroll position changed to 0/0
        Then the page should not be scrolled

    Scenario: Scrolling right
        When I run :scroll right
        Then the page should be scrolled horizontally

    Scenario: Scrolling right and left
        When I run :scroll right
        And I wait until the scroll position changed
        And I run :scroll left
        And I wait until the scroll position changed to 0/0
        Then the page should not be scrolled

    Scenario: Scrolling down with count 10
        When I run :scroll down with count 10
        Then no crash should happen

    Scenario: Scrolling with page down
        When I run :scroll page-down
        Then the page should be scrolled vertically

    Scenario: Scrolling with page down and page up
        When I run :scroll page-down
        And I wait until the scroll position changed
        And I run :scroll page-up
        And I wait until the scroll position changed to 0/0
        Then the page should not be scrolled

    Scenario: Scrolling to bottom
        When I run :scroll bottom
        Then the page should be scrolled vertically

    Scenario: Scrolling to bottom and to top
        When I run :scroll bottom
        And I wait until the scroll position changed
        And I run :scroll top
        And I wait until the scroll position changed to 0/0
        Then the page should not be scrolled

    Scenario: :scroll with invalid argument
        When I run :scroll foobar
        Then the error "Invalid value 'foobar' for direction - expected one of: bottom, down, left, page-down, page-up, right, top, up" should be shown
        And the page should not be scrolled

    Scenario: Scrolling down and up with count
        When I run :scroll down with count 2
        And I wait until the scroll position changed
        And I run :scroll up
        And I run :scroll up
        And I wait until the scroll position changed to 0/0
        Then the page should not be scrolled

    Scenario: Scrolling right
        When I run :scroll right
        Then the page should be scrolled horizontally

    Scenario: Scrolling right and left
        When I run :scroll right
        And I wait until the scroll position changed
        And I run :scroll left
        And I wait until the scroll position changed to 0/0
        Then the page should not be scrolled

    Scenario: Scrolling right and left with count
        When I run :scroll right with count 2
        And I wait until the scroll position changed
        And I run :scroll left
        And I run :scroll left
        And I wait until the scroll position changed to 0/0
        Then the page should not be scrolled

    @skip  # Too flaky
    Scenario: Scrolling down with a very big count
        When I run :scroll down with count 99999999999
        # Make sure it doesn't hang
        And I run :message-info "Still alive!"
        Then the message "Still alive!" should be shown

    Scenario: :scroll on a page without scrolling
        When I open data/hello.txt
        And I run :scroll down
        Then the page should not be scrolled

    ## :scroll-to-perc

    Scenario: Scrolling to bottom with :scroll-to-perc
        When I run :scroll-to-perc 100
        Then the page should be scrolled vertically

    @flaky
    Scenario: Scrolling to bottom and to top with :scroll-to-perc
        When I run :scroll-to-perc 100
        And I wait until the scroll position changed
        And I run :scroll-to-perc 0
        And I wait until the scroll position changed to 0/0
        Then the page should not be scrolled

    Scenario: Scrolling to middle with :scroll-to-perc
        When I run :scroll-to-perc 50
        Then the page should be scrolled vertically

    @flaky
    Scenario: Scrolling to middle with :scroll-to-perc (float)
        When I run :scroll-to-perc 50.5
        Then the page should be scrolled vertically

    @flaky
    Scenario: Scrolling to middle and to top with :scroll-to-perc
        When I run :scroll-to-perc 50
        And I wait until the scroll position changed
        And I run :scroll-to-perc 0
        And I wait until the scroll position changed to 0/0
        Then the page should not be scrolled

    Scenario: Scrolling to right with :scroll-to-perc
        When I run :scroll-to-perc --horizontal 100
        Then the page should be scrolled horizontally

    Scenario: Scrolling to right and to left with :scroll-to-perc
        When I run :scroll-to-perc --horizontal 100
        And I wait until the scroll position changed
        And I run :scroll-to-perc --horizontal 0
        And I wait until the scroll position changed to 0/0
        Then the page should not be scrolled

    Scenario: Scrolling to middle (horizontally) with :scroll-to-perc
        When I run :scroll-to-perc --horizontal 50
        Then the page should be scrolled horizontally

    Scenario: Scrolling to middle and to left with :scroll-to-perc
        When I run :scroll-to-perc --horizontal 50
        And I wait until the scroll position changed
        And I run :scroll-to-perc --horizontal 0
        And I wait until the scroll position changed to 0/0
        Then the page should not be scrolled

    Scenario: :scroll-to-perc without argument
        When I run :scroll-to-perc
        Then the page should be scrolled vertically

    Scenario: :scroll-to-perc without argument and --horizontal
        When I run :scroll-to-perc --horizontal
        Then the page should be scrolled horizontally

    Scenario: :scroll-to-perc with count
        When I run :scroll-to-perc with count 50
        Then the page should be scrolled vertically

    @qtwebengine_skip: Causes memory leak...
    Scenario: :scroll-to-perc with a very big value
        When I run :scroll-to-perc 99999999999
        Then no crash should happen

    Scenario: :scroll-to-perc on a page without scrolling
        When I open data/hello.txt
        And I run :scroll-to-perc 20
        Then the page should not be scrolled

    Scenario: :scroll-to-perc with count and argument
        When I run :scroll-to-perc 0 with count 50
        Then the page should be scrolled vertically

    # https://github.com/qutebrowser/qutebrowser/issues/1821
    @issue3572
    Scenario: :scroll-to-perc without doctype
        When I open data/scroll/no_doctype.html
        And I run :scroll-to-perc 100
        Then the page should be scrolled vertically

    ## :scroll-page

    Scenario: Scrolling down with :scroll-page
        When I run :scroll-page 0 1
        Then the page should be scrolled vertically

    Scenario: Scrolling down with :scroll-page (float)
        When I run :scroll-page 0 1.5
        Then the page should be scrolled vertically

    @flaky
    Scenario: Scrolling down and up with :scroll-page
        When I run :scroll-page 0 1
        And I wait until the scroll position changed
        And I run :scroll-page 0 -1
        And I wait until the scroll position changed to 0/0
        Then the page should not be scrolled

    Scenario: Scrolling right with :scroll-page
        When I run :scroll-page 1 0
        Then the page should be scrolled horizontally

    Scenario: Scrolling right with :scroll-page (float)
        When I run :scroll-page 1.5 0
        Then the page should be scrolled horizontally

    Scenario: Scrolling right and left with :scroll-page
        When I run :scroll-page 1 0
        And I wait until the scroll position changed
        And I run :scroll-page -1 0
        And I wait until the scroll position changed to 0/0
        Then the page should not be scrolled

    Scenario: Scrolling right and left with :scroll-page and count
        When I run :scroll-page 1 0 with count 2
        And I wait until the scroll position changed
        And I run :scroll-page -1 0
        And I wait until the scroll position changed
        And I run :scroll-page -1 0
        And I wait until the scroll position changed to 0/0
        Then the page should not be scrolled

    Scenario: :scroll-page with --bottom-navigate
        When I run :scroll-to-perc 100
        And I wait until the scroll position changed
        And I run :scroll-page --bottom-navigate next 0 1
        Then data/hello2.txt should be loaded

    @issue3572
    Scenario: :scroll-page with --bottom-navigate and zoom
        When I run :zoom 200
        And I run :scroll-to-perc 100
        And I wait until the scroll position changed
        And I run :scroll-page --bottom-navigate next 0 1
        Then data/hello2.txt should be loaded

    Scenario: :scroll-page with --bottom-navigate when not at the bottom
        When I run :scroll-px 0 10
        And I wait until the scroll position changed
        And I run :scroll-page --bottom-navigate next 0 1
        Then the following tabs should be open:
            - data/scroll/simple.html

    Scenario: :scroll-page with --top-navigate
        When I run :scroll-page --top-navigate prev 0 -1
        Then data/hello3.txt should be loaded

    @qtwebengine_skip: Causes memory leak...
    Scenario: :scroll-page with a very big value
        When I run :scroll-page 99999999999 99999999999
        Then the error "Numeric argument is too large for internal int representation." should be shown

    Scenario: :scroll-page on a page without scrolling
        When I open data/hello.txt
        And I run :scroll-page 1 1
        Then the page should not be scrolled

    ## issues

    @issue3572
    Scenario: Relative scroll position with a position:absolute page
        When I open data/scroll/position_absolute.html
        And I run :scroll-to-perc 100
        And I wait until the scroll position changed
        And I run :scroll-page --bottom-navigate next 0 1
        Then data/hello2.txt should be loaded

    Scenario: Scrolling to anchor in background tab
        When I open about:blank
        And I run :tab-only
        And I open data/scroll/simple.html#anchor in a new background tab
        And I run :tab-next
        And I run :jseval --world main checkAnchor()
        Then "[*] [PASS] Positions equal: *" should be logged

    ## frame scrolling

    @qtwebkit_skip: QtWebKit has its own native scrolling
    Scenario: Scrolling pixel-wise in a frame
        When I open data/scroll/frame.html
        And I run :tab-only
        And I hint with args "all" and follow a
        And I run :scroll-px 0 100
        Then the javascript message "scroll y px: 100" should be logged

    @qtwebkit_skip: QtWebKit has its own native scrolling
    Scenario: Scrolling to a position in a frame
        When I open data/scroll/frame.html
        And I run :tab-only
        And I hint with args "all" and follow a
        And I run :scroll-px 0 100
        And I wait for the javascript message "scroll y px: 100"
        And I run :scroll-to-perc 0
        Then the javascript message "scroll y px: 0" should be logged


    ## Nested element scrolling

    @qtwebkit_skip: QtWebKit has its own native scrolling
    Scenario: Scrolling pixel-wise in a pane
        When I open data/scroll/scroll_panes.html
        And I run :tab-only
        # Click on blub
        And I hint with args "all" and follow s
        And I run :scroll-px 0 100
        Then the javascript message "scroll y px: 100" should be logged

    @qtwebkit_skip: QtWebKit has its own native scrolling
    Scenario: Scrolling to a position in a pane
        When I open data/scroll/scroll_panes.html
        And I run :tab-only
        And I hint with args "all" and follow s
        And I run :scroll-px 0 100
        And I wait for the javascript message "scroll y px: 100"
        And I run :scroll-to-perc 0
        Then the javascript message "scroll y px: 0" should be logged
