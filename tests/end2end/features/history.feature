Feature: Page history

    Make sure the global page history is saved correctly.

    Background:
        Given I run :history-clear

    Scenario: Simple history saving
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt
        Then the history file should contain:
            http://localhost:(port)/data/numbers/1.txt
            http://localhost:(port)/data/numbers/2.txt
            
    Scenario: History item with title
        When I open data/title.html
        Then the history file should contain:
            http://localhost:(port)/data/title.html Test title

    Scenario: History item with redirect
        When I open redirect-to?url=data/title.html without waiting
        And I wait until data/title.html is loaded
        Then the history file should contain:
            r http://localhost:(port)/redirect-to?url=data/title.html Test title
            http://localhost:(port)/data/title.html Test title
            
    Scenario: History item with spaces in URL
        When I open data/title with spaces.html
        Then the history file should contain:
            http://localhost:(port)/data/title%20with%20spaces.html Test title

    Scenario: History item with umlauts
        When I open data/äöü.html
        Then the history file should contain:
            http://localhost:(port)/data/%C3%A4%C3%B6%C3%BC.html Chäschüechli
            
    @flaky_once
    Scenario: History with an error
        When I run :open file:///does/not/exist
        And I wait for "Error while loading file:///does/not/exist: Error opening /does/not/exist: *" in the log
        Then the history file should contain:
            file:///does/not/exist Error loading page: file:///does/not/exist

    Scenario: History with a 404
        When I open status/404 without waiting
        And I wait for "Error while loading http://localhost:*/status/404: NOT FOUND" in the log
        Then the history file should contain:
            http://localhost:(port)/status/404 Error loading page: http://localhost:(port)/status/404

    Scenario: Clearing history
        When I open data/title.html
        And I run :history-clear
        Then the history file should be empty
