Feature: Javascript stuff

    Integration with javascript.

    Scenario: Using console.log
        When I set general -> log-javascript-console to debug
        And I open data/javascript/consolelog.html
        Then the javascript message "console.log works!" should be logged

    # Causes segfaults...
    @qtwebengine_createWindow
    Scenario: Opening/Closing a window via JS
        When I open data/javascript/window_open.html
        And I run :tab-only
        And I run :click-element id open-normal
        And I wait for "Changing title for idx 1 to 'about:blank'" in the log
        And I run :tab-focus 1
        And I run :click-element id close-normal
        Then "Focus object changed: *" should be logged

    # Causes segfaults...
    @qtwebengine_createWindow
    Scenario: Opening/closing a modal window via JS
        When I open data/javascript/window_open.html
        And I run :tab-only
        And I run :click-element id open-modal
        And I wait for "Changing title for idx 1 to 'about:blank'" in the log
        And I run :tab-focus 1
        And I run :click-element id close-normal
        Then "Focus object changed: *" should be logged
        # WebModalDialog with QtWebKit, WebDialog with QtWebEngine
        And "Web*Dialog requested, but we don't support that!" should be logged

    # https://github.com/The-Compiler/qutebrowser/issues/906

    @qtwebengine_skip
    Scenario: Closing a JS window twice (issue 906) - qtwebkit
        When I open about:blank
        And I run :tab-only
        When I open data/javascript/window_open.html in a new tab
        And I run :click-element id open-normal
        And I wait for "Changing title for idx 2 to 'about:blank'" in the log
        And I run :tab-focus 2
        And I run :click-element id close-twice
        Then "Requested to close * which does not exist!" should be logged

    @qtwebengine_createWindow @qtwebkit_skip
    Scenario: Closing a JS window twice (issue 906) - qtwebengine
        When I open about:blank
        And I run :tab-only
        And I open data/javascript/window_open.html in a new tab
        And I run :click-element id open-normal
        And I wait for "Changing title for idx 2 to 'about:blank'" in the log
        And I run :tab-focus 2
        And I run :click-element id close-twice
        And I wait for "Focus object changed: *" in the log
        Then no crash should happen

    @qtwebengine_createWindow
    Scenario: Opening window without user interaction with javascript-can-open-windows-automatically set to true
        When I open data/hello.txt
        And I set content -> javascript-can-open-windows-automatically to true
        And I run :tab-only
        And I run :jseval if (window.open('about:blank')) { console.log('window opened'); } else { console.log('error while opening window'); }
        Then the javascript message "window opened" should be logged

    @qtwebengine_createWindow
    Scenario: Opening window without user interaction with javascript-can-open-windows-automatically set to false
        When I open data/hello.txt
        And I set content -> javascript-can-open-windows-automatically to false
        And I run :tab-only
        And I run :jseval if (window.open('about:blank')) { console.log('window opened'); } else { console.log('error while opening window'); }
        Then the javascript message "error while opening window" should be logged
