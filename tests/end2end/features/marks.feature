Feature: Setting positional marks

    Background:
        Given I open data/marks.html
        And I run :tab-only

    ## :set-mark, :jump-mark

    Scenario: Setting and jumping to a local mark
        When I run :scroll-px 5 10
        And I run :set-mark a
        And I run :scroll-px 0 20
        And I run :jump-mark a
        Then the page should be scrolled to 5 10

    Scenario: Jumping back after jumping to a particular percentage
        When I run :scroll-px 10 20
        And I run :scroll-perc 100
        And I run :jump-mark "'"
        Then the page should be scrolled to 10 20

    Scenario: Setting the same local mark on another page
        When I run :scroll-px 5 10
        And I run :set-mark a
        And I open data/marks.html
        And I run :scroll-px 0 20
        And I run :set-mark a
        And I run :jump-mark a
        Then the page should be scrolled to 0 20

    Scenario: Jumping to a local mark after returning to a page
        When I run :scroll-px 5 10
        And I run :set-mark a
        And I open data/numbers/1.txt
        And I run :set-mark a
        And I open data/marks.html
        And I run :jump-mark a
        Then the page should be scrolled to 5 10

    Scenario: Setting and jumping to a global mark
        When I run :scroll-px 5 20
        And I run :set-mark A
        And I open data/numbers/1.txt
        And I run :jump-mark A
        Then data/marks.html should be loaded
        And the page should be scrolled to 5 20

    Scenario: Jumping to an unset mark
        When I run :jump-mark b
        Then the error "Mark b is not set" should be shown

    Scenario: Jumping to a local mark that was set on another page
        When I run :set-mark b
        And I open data/numbers/1.txt
        And I run :jump-mark b
        Then the error "Mark b is not set" should be shown

    Scenario: Jumping to a local mark after changing fragments
        When I open data/marks.html#top
        And I run :scroll 'top'
        And I run :scroll-px 10 10
        And I run :set-mark a
        When I open data/marks.html#bottom
        And I run :jump-mark a
        Then the page should be scrolled to 10 10

    Scenario: Jumping back after following a link
        When I run :hint links normal
        And I run :follow-hint s
        And I wait until data/marks.html#bottom is loaded
        And I run :jump-mark "'"
        Then the page should be scrolled to 0 0

    Scenario: Jumping back after searching
        When I run :scroll-px 20 15
        And I run :search Waldo
        And I run :jump-mark "'"
        Then the page should be scrolled to 20 15

    Scenario: Jumping back after search-next
        When I run :search Grail
        And I run :search-next
        And I run :jump-mark "'"
        Then the page should be scrolled to 0 0

    Scenario: Hovering a hint does not set the ' mark
        When I run :scroll-px 30 20
        And  I run :scroll-perc 0
        And I run :hint links hover
        And I run :follow-hint s
        And I run :jump-mark "'"
        Then the page should be scrolled to 30 20
