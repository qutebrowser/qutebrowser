Feature: Javascript stuff

    Integration with javascript.

    Scenario: Using console.log
        When I set general -> log-javascript-console to debug
        And I open data/javascript/consolelog.html
        Then the javascript message "console.log works!" should be logged

    # Causes segfaults...
    @qtwebengine_createWindow @xfail_norun
    Scenario: Opening/Closing a window via JS
        When I open data/javascript/window_open.html
        And I run :tab-only
        And I run :click-element id open-normal
        And I wait for "Changing title for idx 1 to 'about:blank'" in the log
        And I run :tab-focus 1
        And I run :click-element id close-normal
        Then "Focus object changed: *" should be logged

    # Causes segfaults...
    @qtwebengine_createWindow @xfail_norun
    Scenario: Opening/closing a modal window via JS
        When I open data/javascript/window_open.html
        And I run :tab-only
        And I run :click-element id open-modal
        And I wait for "Changing title for idx 1 to 'about:blank'" in the log
        And I run :tab-focus 1
        And I run :click-element id close-normal
        Then "Focus object changed: *" should be logged
        And "WebModalDialog requested, but we don't support that!" should be logged

    # https://github.com/The-Compiler/qutebrowser/issues/906

    @qtwebengine_skip
    Scenario: Closing a JS window twice (issue 906) - qtwebkit
        When I open about:blank
        And I run :tab-only
        When I open data/javascript/issue906.html in a new tab
        And I run :click-element id open-button
        And I wait for "Changing title for idx 2 to 'about:blank'" in the log
        And I run :tab-focus 2
        And I run :click-element id close-button
        Then "Requested to close * which does not exist!" should be logged

    @qtwebengine_createWindow @qtwebkit_skip
    Scenario: Closing a JS window twice (issue 906) - qtwebengine
        When I open about:blank
        And I run :tab-only
        And I open data/javascript/issue906.html in a new tab
        And I run :click-element id open-button
        And I wait for "WebDialog requested, but we don't support that!" in the log
        And I wait for "Changing title for idx 2 to 'about:blank'" in the log
        And I run :tab-focus 2
        And I run :click-element id close-button
        And I wait for "Focus object changed: *" in the log
        Then no crash should happen
