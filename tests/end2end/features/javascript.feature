# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Javascript stuff

    Integration with javascript.

    Scenario: Using console.log
        When I open data/javascript/consolelog.html
        Then the javascript message "console.log works!" should be logged

    @skip   # Too flaky
    Scenario: Opening/Closing a window via JS
        When I open data/javascript/window_open.html
        And I run :tab-only
        And I run :click-element id open-normal
        And I wait for "Changing title for idx 1 to 'about:blank'" in the log
        And I run :tab-focus 1
        And I run :click-element id close-normal
        And I wait for "[*] window closed" in the log
        Then "Focus object changed: *" should be logged
        And the following tabs should be open:
            - data/javascript/window_open.html (active)

    @skip   # Too flaky
    Scenario: Opening/closing a modal window via JS
        When I open data/javascript/window_open.html
        And I run :tab-only
        And I run :click-element id open-modal
        And I wait for "Changing title for idx 1 to 'about:blank'" in the log
        And I run :tab-focus 1
        And I run :click-element id close-normal
        And I wait for "[*] window closed" in the log
        Then "Focus object changed: *" should be logged
        And "Web*Dialog requested, but we don't support that!" should be logged
        And the following tabs should be open:
            - data/javascript/window_open.html (active)

    # https://github.com/qutebrowser/qutebrowser/issues/906

    @qtwebengine_skip
    Scenario: Closing a JS window twice (issue 906) - qtwebkit
        When I open about:blank
        And I run :tab-only
        And I open data/javascript/window_open.html in a new tab
        And I run :click-element id open-normal
        And I wait for "Changing title for idx 2 to 'about:blank'" in the log
        And I run :tab-focus 2
        And I run :click-element id close-twice
        And I wait for "[*] window closed" in the log
        Then "Requested to close * which does not exist!" should be logged

    @qtwebkit_skip @flaky
    Scenario: Closing a JS window twice (issue 906) - qtwebengine
        When I open about:blank
        And I run :tab-only
        And I open data/javascript/window_open.html in a new tab
        And I run :click-element id open-normal
        And I wait for "Changing title for idx 2 to 'about:blank'" in the log
        And I run :buffer window_open.html
        And I run :click-element id close-twice
        And I wait for "Focus object changed: *" in the log
        And I wait for "[*] window closed" in the log
        Then no crash should happen

    @flaky
    Scenario: Opening window without user interaction with content.javascript.can_open_tabs_automatically set to true
        When I open data/hello.txt
        And I set content.javascript.can_open_tabs_automatically to true
        And I run :tab-only
        And I run :jseval if (window.open('about:blank')) { console.log('window opened'); } else { console.log('error while opening window'); }
        Then the javascript message "window opened" should be logged

    @flaky
    Scenario: Opening window without user interaction with javascript.can_open_tabs_automatically set to false
        When I open data/hello.txt
        And I set content.javascript.can_open_tabs_automatically to false
        And I run :tab-only
        And I run :jseval if (window.open('about:blank')) { console.log('window opened'); } else { console.log('error while opening window'); }
        Then the javascript message "error while opening window" should be logged

    Scenario: Executing jseval when javascript is disabled
        When I set content.javascript.enabled to false
        And I run :jseval console.log('jseval executed')
        And I set content.javascript.enabled to true
        Then the javascript message "jseval executed" should be logged

    ## webelement issues (mostly with QtWebEngine)

    # https://github.com/qutebrowser/qutebrowser/issues/2569
    Scenario: Clicking on form element with tagName child
        When I open data/issue2569.html
        And I run :click-element id tagnameform
        And I wait for "Sending fake click to *" in the log
        Then no crash should happen

    Scenario: Clicking on form element with text child
        When I open data/issue2569.html
        And I run :click-element id textform
        And I wait for "Sending fake click to *" in the log
        Then no crash should happen

    Scenario: Clicking on form element with value child
        When I open data/issue2569.html
        And I run :click-element id valueform
        And I wait for "Sending fake click to *" in the log
        Then no crash should happen

    Scenario: Clicking on svg element
        When I open data/issue2569.html
        And I run :click-element id icon
        And I wait for "Sending fake click to *" in the log
        Then no crash should happen

    Scenario: Clicking on li element
        When I open data/issue2569.html
        And I run :click-element id listitem
        And I wait for "Sending fake click to *" in the log
        Then no crash should happen

    # We load the tab in the background, and the HTML sets the window size for
    # when it's hidden.
    # Then, "the window sizes should be the same" uses :jseval to set the size
    # when it's shown, and compares the two.
    # https://github.com/qutebrowser/qutebrowser/issues/1190
    # https://github.com/qutebrowser/qutebrowser/issues/2495

    @flaky
    Scenario: Have a GreaseMonkey script run at page start
        When I have a GreaseMonkey file saved for document-start with noframes unset
        And I run :greasemonkey-reload
        And I open data/hints/iframe.html
        Then the javascript message "Script is running on /data/hints/iframe.html" should be logged

    Scenario: Have a GreaseMonkey script running on frames
        When I have a GreaseMonkey file saved for document-end with noframes unset
        And I run :greasemonkey-reload
        And I open data/hints/iframe.html
        Then the javascript message "Script is running on /data/hints/html/wrapped.html" should be logged

    @flaky
    Scenario: Have a GreaseMonkey script running on noframes
        When I have a GreaseMonkey file saved for document-end with noframes set
        And I run :greasemonkey-reload
        And I open data/hints/iframe.html
        Then the javascript message "Script is running on /data/hints/html/wrapped.html" should not be logged

    Scenario: Per-URL localstorage setting
        When I set content.local_storage to false
        And I run :set -tu http://localhost:*/data2/* content.local_storage true
        And I open data/javascript/localstorage.html
        And I wait for "[*] local storage is not working" in the log
        And I open data2/javascript/localstorage.html
        Then the javascript message "local storage is working" should be logged

    Scenario: Per-URL JavaScript setting
        When I set content.javascript.enabled to false
        And I run :set -tu http://localhost:*/data2/* content.javascript.enabled true
        And I open data2/javascript/enabled.html
        And I wait for "[*] JavaScript is enabled" in the log
        And I open data/javascript/enabled.html
        Then the page should contain the plaintext "JavaScript is disabled"

    @qtwebkit_skip
    Scenario: Error pages without JS enabled
        When I set content.javascript.enabled to false
        And I open 500 without waiting
        Then "Showing error page for* 500" should be logged
        And "Load error: *500" should be logged

    @flaky
    Scenario: Using JS after window.open
        When I open data/hello.txt
        And I set content.javascript.can_open_tabs_automatically to true
        And I run :jseval window.open('about:blank')
        And I open data/hello.txt
        And I run :tab-only
        And I open data/hints/html/simple.html
        And I run :hint all
        And I wait for "hints: a" in the log
        And I run :leave-mode
        Then "There was an error while getting hint elements" should not be logged
