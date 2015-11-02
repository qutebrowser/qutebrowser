Feature: Yanking and pasting.
    :yank and :paste can be used to copy/paste the URL or title from/to the
    clipboard and primary selection.

    Background:
        Given I open data/yankpaste/test.html

    Scenario: Yanking URLs to clipboard
        When I run :yank
        Then the message "Yanked URL to clipboard: http://localhost:(port)/data/yankpaste/test.html" should be shown.
        And the clipboard should contain "http://localhost:(port)/data/yankpaste/test.html"

    Scenario: Yanking URLs to primary selection
        When I run :yank --sel
        Then the message "Yanked URL to primary selection: http://localhost:(port)/data/yankpaste/test.html" should be shown.
        And the primary selection should contain "http://localhost:(port)/data/yankpaste/test.html"

    Scenario: Yanking title to clipboard
        When I run :yank --title
        Then the message "Yanked title to clipboard: Test title" should be shown.
        And the clipboard should contain "Test title"

    Scenario: Yanking domain to clipboard
        When I run :yank --domain
        Then the message "Yanked domain to clipboard: http://localhost:(port)" should be shown.
        And the clipboard should contain "http://localhost:(port)"
