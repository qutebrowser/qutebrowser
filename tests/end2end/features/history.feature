# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Page history

    Make sure the global page history is saved correctly.

    Background:
        Given I run :history-clear --force

    Scenario: Simple history saving
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt
        Then the history should contain:
            http://localhost:(port)/data/numbers/1.txt
            http://localhost:(port)/data/numbers/2.txt

    Scenario: History item with title
        When I open data/title.html
        Then the history should contain:
            http://localhost:(port)/data/title.html Test title

    Scenario: History item with redirect
        When I open redirect-to?url=data/title.html without waiting
        And I wait until data/title.html is loaded
        Then the history should contain:
            r http://localhost:(port)/redirect-to?url=data/title.html Test title
            http://localhost:(port)/data/title.html Test title

    Scenario: History item with spaces in URL
        When I open data/title with spaces.html
        Then the history should contain:
            http://localhost:(port)/data/title%20with%20spaces.html Test title

    @unicode_locale
    Scenario: History item with umlauts
        When I open data/äöü.html
        Then the history should contain:
            http://localhost:(port)/data/%C3%A4%C3%B6%C3%BC.html Chäschüechli

    @flaky @qtwebengine_todo: Error page message is not implemented
    Scenario: History with an error
        When I run :open file:///does/not/exist
        And I wait for "Error while loading file:///does/not/exist: Error opening /does/not/exist: *" in the log
        Then the history should contain:
            file:///does/not/exist Error loading page: file:///does/not/exist

    @qtwebengine_todo: Error page message is not implemented
    Scenario: History with a 404
        When I open 404 without waiting
        And I wait for "Error while loading http://localhost:*/404: NOT FOUND" in the log
        Then the history should contain:
            http://localhost:(port)/404 Error loading page: http://localhost:(port)/404

    Scenario: History with invalid URL
        When I run :tab-only
        And I open data/javascript/window_open.html
        And I run :click-element id open-invalid
        Then "load status for * LoadStatus.success" should be logged

    Scenario: History with data URL
        When I open data/data_link.html
        And I run :click-element id link
        And I wait until data:;base64,cXV0ZWJyb3dzZXI= is loaded
        Then the history should contain:
            http://localhost:(port)/data/data_link.html data: link

    @qtwebkit_skip
    Scenario: History with view-source URL
        When I open data/title.html
        And I run :view-source
        And I wait for regex "Changing title for idx \d+ to 'view-source:(http://)?localhost:\d+/data/title.html'" in the log
        Then the history should contain:
            http://localhost:(port)/data/title.html Test title

    Scenario: Clearing history
        When I run :tab-only
        And I open data/title.html
        And I run :history-clear --force
        Then the history should be empty

    Scenario: Clearing history with confirmation
        When I open data/title.html
        And I run :history-clear
        And I wait for "Asking question <* title='Clear all browsing history?'>, *" in the log
        And I run :prompt-accept yes
        Then the history should be empty

    Scenario: History with yanked URL and 'add to history' flag
        When I open data/hints/html/simple.html
        And I hint with args "--add-history links yank" and follow a
        Then the history should contain:
            http://localhost:(port)/data/hints/html/simple.html Simple link
            http://localhost:(port)/data/hello.txt

    @flaky
    Scenario: Listing history
        When I open data/numbers/3.txt
        And I open data/numbers/4.txt
        And I open qute://history
        And I wait 2s
        Then the page should contain the plaintext "3.txt"
        Then the page should contain the plaintext "4.txt"

    @flaky
    Scenario: Listing history with qute:history redirect
        When I open data/numbers/3.txt
        And I open data/numbers/4.txt
        And I open qute:history without waiting
        And I wait until qute://history is loaded
        And I wait 2s
        Then the page should contain the plaintext "3.txt"
        Then the page should contain the plaintext "4.txt"

    @flaky
    Scenario: XSS in :history
        When I open data/issue4011.html
        And I open qute://history
        Then the javascript message "XSS" should not be logged

    @skip  # Too flaky
    Scenario: Escaping of URLs in :history
        When I open query?one=1&two=2
        And I open qute://history
        And I wait 2s  # JS loads the history async
        And I hint with args "links normal" and follow a
        And I wait until query?one=1&two=2 is loaded
        Then the query parameter two should be set to 2
