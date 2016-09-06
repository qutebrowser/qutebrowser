Feature: Setting positional marks

    Background:
        Given I open data/marks.html
        And I run :tab-only

    ## :set-mark, :jump-mark

    Scenario: Setting and jumping to a local mark
        When I run :scroll-px 5 10
        And I wait for "Scroll position changed to PyQt5.QtCore.QPoint(5, 10)" in the log
        And I run :set-mark a
        And I run :scroll-px 0 20
        And I wait for "Scroll position changed to PyQt5.QtCore.QPoint(5, 30)" in the log
        And I run :jump-mark a
        And I wait for "Scroll position changed to PyQt5.QtCore.QPoint(5, 10)" in the log
        Then the page should be scrolled to 5 10

    Scenario: Jumping back after jumping to a particular percentage
        When I run :scroll-px 10 20
        And I wait for "Scroll position changed to PyQt5.QtCore.QPoint(10, 20)" in the log
        And I run :scroll-perc 100
        And I wait for "Scroll position changed to *" in the log
        And I run :jump-mark "'"
        And I wait for "Scroll position changed to PyQt5.QtCore.QPoint(10, 20)" in the log
        Then the page should be scrolled to 10 20

    Scenario: Setting the same local mark on another page
        When I run :scroll-px 5 10
        And I wait for "Scroll position changed to PyQt5.QtCore.QPoint(5, 10)" in the log
        And I run :set-mark a
        And I open data/marks.html
        And I run :scroll-px 0 20
        And I wait for "Scroll position changed to PyQt5.QtCore.QPoint(0, 20)" in the log
        And I run :set-mark a
        And I run :jump-mark a
        Then the page should be scrolled to 0 20

    Scenario: Jumping to a local mark after returning to a page
        When I run :scroll-px 5 10
        And I wait for "Scroll position changed to PyQt5.QtCore.QPoint(5, 10)" in the log
        And I run :set-mark a
        And I run :scroll-px 0 20
        And I wait for "Scroll position changed to PyQt5.QtCore.QPoint(5, 30)" in the log
        And I open data/numbers/1.txt
        And I run :set-mark a
        And I open data/marks.html
        And I run :jump-mark a
        And I wait for "Scroll position changed to PyQt5.QtCore.QPoint(5, 10)" in the log
        Then the page should be scrolled to 5 10

    Scenario: Setting and jumping to a global mark
        When I run :scroll-px 5 20
        And I wait for "Scroll position changed to PyQt5.QtCore.QPoint(5, 20)" in the log
        And I run :set-mark A
        And I open data/numbers/1.txt
        And I wait for "Scroll position changed to PyQt5.QtCore.QPoint()" in the log
        And I run :jump-mark A
        And I wait for "Scroll position changed to PyQt5.QtCore.QPoint(5, 20)" in the log
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

    @qtwebengine_todo: Does not emit loaded signal for fragments?
    Scenario: Jumping to a local mark after changing fragments
        When I open data/marks.html#top
        And I run :scroll 'top'
        And I wait for "Scroll position changed to PyQt5.QtCore.QPoint()" in the log
        And I run :scroll-px 10 10
        And I wait for "Scroll position changed to PyQt5.QtCore.QPoint(10, 10)" in the log
        And I run :set-mark a
        When I open data/marks.html#bottom
        And I run :jump-mark a
        And I wait for "Scroll position changed to PyQt5.QtCore.QPoint(10, 10)" in the log
        Then the page should be scrolled to 10 10

    @qtwebengine_todo: Does not emit loaded signal for fragments?
    Scenario: Jumping back after following a link
        When I hint with args "links normal" and follow s
        And I wait until data/marks.html#bottom is loaded
        And I run :jump-mark "'"
        And I wait for "Scroll position changed to PyQt5.QtCore.QPoint()" in the log
        Then the page should be scrolled to 0 0

    Scenario: Jumping back after searching
        When I run :scroll-px 20 15
        And I wait for "Scroll position changed to PyQt5.QtCore.QPoint(20, 15)" in the log
        And I run :search Waldo
        And I wait for "Scroll position changed to *" in the log
        And I run :jump-mark "'"
        And I wait for "Scroll position changed to PyQt5.QtCore.QPoint(20, 15)" in the log
        Then the page should be scrolled to 20 15

    # FIXME:qtwebengine
    @qtwebengine_skip: Does not find Grail on Travis for some reason?
    Scenario: Jumping back after search-next
        When I run :search Grail
        And I run :search-next
        And I wait for "Scroll position changed to *" in the log
        And I run :jump-mark "'"
        And I wait for "Scroll position changed to PyQt5.QtCore.QPoint()" in the log
        Then the page should be scrolled to 0 0

    Scenario: Hovering a hint does not set the ' mark
        When I run :scroll-px 30 20
        And I wait for "Scroll position changed to PyQt5.QtCore.QPoint(30, 20)" in the log
        And  I run :scroll-perc 0
        And I wait for "Scroll position changed to *" in the log
        And I hint with args "links hover" and follow s
        And I run :jump-mark "'"
        And I wait for "Scroll position changed to PyQt5.QtCore.QPoint(30, 20)" in the log
        Then the page should be scrolled to 30 20
