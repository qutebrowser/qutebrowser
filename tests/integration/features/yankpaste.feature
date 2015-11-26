Feature: Yanking and pasting.
    :yank and :paste can be used to copy/paste the URL or title from/to the
    clipboard and primary selection.

    Background:
        Given I run :tab-only

    #### :yank

    Scenario: Yanking URLs to clipboard
        When I open data/title.html
        And I run :yank
        Then the message "Yanked URL to clipboard: http://localhost:(port)/data/title.html" should be shown
        And the clipboard should contain "http://localhost:(port)/data/title.html"

    Scenario: Yanking URLs to primary selection
        When selection is supported
        And I open data/title.html
        And I run :yank --sel
        Then the message "Yanked URL to primary selection: http://localhost:(port)/data/title.html" should be shown
        And the primary selection should contain "http://localhost:(port)/data/title.html"

    Scenario: Yanking title to clipboard
        When I open data/title.html
        And I wait for regex "Changing title for idx \d to 'Test title'" in the log
        And I run :yank --title
        Then the message "Yanked title to clipboard: Test title" should be shown
        And the clipboard should contain "Test title"

    Scenario: Yanking domain to clipboard
        When I open data/title.html
        And I run :yank --domain
        Then the message "Yanked domain to clipboard: http://localhost:(port)" should be shown
        And the clipboard should contain "http://localhost:(port)"

    #### :paste

    Scenario: Pasting an URL
        When I put "http://localhost:(port)/data/hello.txt" into the clipboard
        And I run :paste
        And I wait until data/hello.txt is loaded
        Then the requests should be:
            data/hello.txt

    Scenario: Pasting an URL from primary selection
        When selection is supported
        And I put "http://localhost:(port)/data/hello2.txt" into the primary selection
        And I run :paste --sel
        And I wait until data/hello2.txt is loaded
        Then the requests should be:
            data/hello2.txt

    Scenario: Pasting with empty clipboard
        When I put "" into the clipboard
        And I run :paste
        Then the error "Clipboard is empty." should be shown

    Scenario: Pasting with empty selection
        When selection is supported
        And I put "" into the primary selection
        And I run :paste --sel
        Then the error "Primary selection is empty." should be shown

    Scenario: Pasting in a new tab
        Given I open about:blank
        When I run :tab-only
        And I put "http://localhost:(port)/data/hello.txt" into the clipboard
        And I run :paste -t
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - about:blank
            - data/hello.txt (active)

    Scenario: Pasting in a background tab
        Given I open about:blank
        When I run :tab-only
        And I put "http://localhost:(port)/data/hello.txt" into the clipboard
        And I run :paste -b
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - about:blank (active)
            - data/hello.txt

    Scenario: Pasting in a new window
        Given I have a fresh instance
        When I put "http://localhost:(port)/data/hello.txt" into the clipboard
        And I run :paste -w
        And I wait until data/hello.txt is loaded
        Then the session should look like:
            windows:
            - tabs:
              - active: true
                history:
                - active: true
                  url: about:blank
            - tabs:
              - active: true
                history:
                - active: true
                  url: http://localhost:*/data/hello.txt
