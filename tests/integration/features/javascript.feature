Feature: Javascript stuff

    Integration with javascript.

    # https://github.com/The-Compiler/qutebrowser/issues/906

    Scenario: Closing a JS window twice (issue 906)
        When I open about:blank
        And I open data/javascript/issue906.html in a new tab
        And I run :hint
        And I run :follow-hint a
        And I run :tab-focus 2
        And I run :hint
        And I run :follow-hint s
        Then "Requested to close * which does not exist!" should be logged
