Feature: Using hints

    Scenario: Following a hint.
        When I open data/hints/link.html
        And I run :hint links normal
        And I run :follow-hint a
        And I wait until data/hello.txt is loaded
        Then the requests should be:
            data/hints/link.html
            data/hello.txt

    Scenario: Using :follow-hint outside of hint mode (issue 1105)
        When I run :follow-hint
        Then the error "follow-hint: This command is only allowed in hint mode." should be shown.

    Scenario: Using :follow-hint with an invalid index.
        When I open data/hints/link.html
        And I run :hint links normal
        And I run :follow-hint xyz
        Then the error "No hint xyz!" should be shown.
