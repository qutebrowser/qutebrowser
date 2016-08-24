Feature: Javascript stuff

    Integration with javascript.

    Scenario: Using console.log
        When I set general -> log-javascript-console to debug
        And I open data/javascript/consolelog.html
        Then the javascript message "console.log works!" should be logged

    # https://github.com/The-Compiler/qutebrowser/issues/906

    @qtwebengine_todo: createWindow is not implemented yet
    Scenario: Closing a JS window twice (issue 906)
        When I open about:blank
        And I open data/javascript/issue906.html in a new tab
        And I run :click-element id open-button
        And I wait for "Changing title for idx 2 to 'about:blank'" in the log
        And I run :tab-focus 2
        And I run :click-element id close-button
        Then "Requested to close * which does not exist!" should be logged
