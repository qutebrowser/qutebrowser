# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Prompts
    Various prompts (javascript, SSL errors, authentification, etc.)

    # Javascript

    Scenario: Javascript alert
        When I open data/prompt/jsalert.html
        And I run :click-element id button
        And I wait for a prompt
        And I run :prompt-accept
        Then the javascript message "Alert done" should be logged

    Scenario: Using content.javascript.alert
        When I set content.javascript.alert to false
        And I open data/prompt/jsalert.html
        And I run :click-element id button
        Then the javascript message "Alert done" should be logged

    Scenario: Javascript confirm - yes
        When I open data/prompt/jsconfirm.html
        And I run :click-element id button
        And I wait for a prompt
        And I run :prompt-accept yes
        Then the javascript message "confirm reply: true" should be logged

    Scenario: Javascript confirm - no
        When I open data/prompt/jsconfirm.html
        And I run :click-element id button
        And I wait for a prompt
        And I run :prompt-accept no
        Then the javascript message "confirm reply: false" should be logged

    Scenario: Javascript confirm - aborted
        When I open data/prompt/jsconfirm.html
        And I run :click-element id button
        And I wait for a prompt
        And I run :leave-mode
        Then the javascript message "confirm reply: false" should be logged

    Scenario: Javascript prompt
        When I open data/prompt/jsprompt.html
        And I run :click-element id button
        And I wait for a prompt
        And I press the keys "prompt test"
        And I run :prompt-accept
        Then the javascript message "Prompt reply: prompt test" should be logged

    Scenario: Javascript prompt with default
        When I open data/prompt/jsprompt.html
        And I run :click-element id button-default
        And I wait for a prompt
        And I run :prompt-accept
        Then the javascript message "Prompt reply: default" should be logged

    Scenario: Rejected javascript prompt
        When I open data/prompt/jsprompt.html
        And I run :click-element id button
        And I wait for a prompt
        And I press the keys "prompt test"
        And I run :leave-mode
        Then the javascript message "Prompt reply: null" should be logged

    # Multiple prompts

    @qtwebengine_skip: QtWebEngine refuses to load anything with a JS question
    Scenario: Blocking question interrupted by blocking one
        When I set content.javascript.alert to true
        And I open data/prompt/jsalert.html
        And I run :click-element id button
        And I wait for a prompt
        And I open data/prompt/jsconfirm.html in a new tab
        And I run :click-element id button
        And I wait for a prompt
        # JS confirm
        And I run :prompt-accept yes
        # JS alert
        And I run :prompt-accept
        Then the javascript message "confirm reply: true" should be logged
        And the javascript message "Alert done" should be logged

    @qtwebengine_skip: QtWebEngine refuses to load anything with a JS question
    Scenario: Blocking question interrupted by async one
        Given I have a fresh instance
        When I set content.javascript.alert to true
        And I set content.notifications to ask
        And I open data/prompt/jsalert.html
        And I run :click-element id button
        And I wait for a prompt
        And I open data/prompt/notifications.html in a new tab
        And I run :click-element id button
        And I wait for a prompt
        # JS alert
        And I run :prompt-accept
        # notification permission
        And I run :prompt-accept yes
        Then the javascript message "Alert done" should be logged
        And the javascript message "notification permission granted" should be logged

    @qtwebengine_notifications
    Scenario: Async question interrupted by async one
        Given I have a fresh instance
        When I set content.notifications to ask
        And I open data/prompt/notifications.html in a new tab
        And I run :click-element id button
        And I wait for a prompt
        And I run :quickmark-save
        And I wait for a prompt
        # notification permission
        And I run :prompt-accept yes
        # quickmark
        And I run :prompt-accept test
        Then the javascript message "notification permission granted" should be logged
        And "Added quickmark test for *" should be logged

    @qtwebengine_notifications
    Scenario: Async question interrupted by blocking one
        Given I have a fresh instance
        When I set content.notifications to ask
        And I set content.javascript.alert to true
        And I open data/prompt/notifications.html in a new tab
        And I run :click-element id button
        And I wait for a prompt
        And I open data/prompt/jsalert.html in a new tab
        And I run :click-element id button
        And I wait for a prompt
        # JS alert
        And I run :prompt-accept
        # notification permission
        And I run :prompt-accept yes
        Then the javascript message "Alert done" should be logged
        And the javascript message "notification permission granted" should be logged

    # Shift-Insert with prompt (issue 1299)

    Scenario: Pasting via shift-insert in prompt mode
        When selection is supported
        And I put "insert test" into the primary selection
        And I open data/prompt/jsprompt.html
        And I run :click-element id button
        And I wait for a prompt
        And I press the keys "<Shift-Insert>"
        And I run :prompt-accept
        Then the javascript message "Prompt reply: insert test" should be logged

    Scenario: Pasting via shift-insert without it being supported
        When selection is not supported
        And I put "insert test" into the primary selection
        And I put "clipboard test" into the clipboard
        And I open data/prompt/jsprompt.html
        And I run :click-element id button
        And I wait for a prompt
        And I press the keys "<Shift-Insert>"
        And I run :prompt-accept
        Then the javascript message "Prompt reply: clipboard test" should be logged

    Scenario: Using content.javascript.prompt
        When I set content.javascript.prompt to false
        And I open data/prompt/jsprompt.html
        And I run :click-element id button
        Then the javascript message "Prompt reply: null" should be logged

    # SSL

    Scenario: SSL error with content.ssl_strict = false
        When I clear SSL errors
        And I set content.ssl_strict to false
        And I load an SSL page
        And I wait until the SSL page finished loading
        Then the error "Certificate error: *" should be shown
        And the page should contain the plaintext "Hello World via SSL!"

    Scenario: SSL error with content.ssl_strict = true
        When I clear SSL errors
        And I set content.ssl_strict to true
        And I load an SSL page
        Then a SSL error page should be shown

    Scenario: SSL error with content.ssl_strict = ask -> yes
        When I clear SSL errors
        And I set content.ssl_strict to ask
        And I load an SSL page
        And I wait for a prompt
        And I run :prompt-accept yes
        And I wait until the SSL page finished loading
        Then the page should contain the plaintext "Hello World via SSL!"

    Scenario: SSL error with content.ssl_strict = ask -> no
        When I clear SSL errors
        And I set content.ssl_strict to ask
        And I load an SSL page
        And I wait for a prompt
        And I run :prompt-accept no
        Then a SSL error page should be shown

    Scenario: SSL error with content.ssl_strict = ask -> abort
        When I clear SSL errors
        And I set content.ssl_strict to ask
        And I load an SSL page
        And I wait for a prompt
        And I run :leave-mode
        Then a SSL error page should be shown

    # Geolocation

    Scenario: Always rejecting geolocation
        When I set content.geolocation to false
        And I open data/prompt/geolocation.html in a new tab
        And I run :click-element id button
        Then the javascript message "geolocation permission denied" should be logged

    Scenario: geolocation with ask -> false
        When I set content.geolocation to ask
        And I open data/prompt/geolocation.html in a new tab
        And I run :click-element id button
        And I wait for a prompt
        And I run :prompt-accept no
        Then the javascript message "geolocation permission denied" should be logged

    Scenario: geolocation with ask -> false and save
        When I set content.geolocation to ask
        And I open data/prompt/geolocation.html in a new tab
        And I run :click-element id button
        And I wait for a prompt
        And I run :prompt-accept --save no
        Then the javascript message "geolocation permission denied" should be logged
        And the per-domain option content.geolocation should be set to false for http://localhost:(port)

    Scenario: geolocation with ask -> abort
        When I set content.geolocation to ask
        And I open data/prompt/geolocation.html in a new tab
        And I run :click-element id button
        And I wait for a prompt
        And I run :leave-mode
        Then the javascript message "geolocation permission denied" should be logged

    # Notifications

    @qtwebengine_notifications
    Scenario: Always rejecting notifications
        Given I have a fresh instance
        When I set content.notifications to false
        And I open data/prompt/notifications.html in a new tab
        And I run :click-element id button
        Then the javascript message "notification permission denied" should be logged

    @qtwebengine_notifications
    Scenario: Always accepting notifications
        Given I have a fresh instance
        When I set content.notifications to true
        And I open data/prompt/notifications.html in a new tab
        And I run :click-element id button
        Then the javascript message "notification permission granted" should be logged

    @qtwebengine_notifications
    Scenario: notifications with ask -> false
        Given I have a fresh instance
        When I set content.notifications to ask
        And I open data/prompt/notifications.html in a new tab
        And I run :click-element id button
        And I wait for a prompt
        And I run :prompt-accept no
        Then the javascript message "notification permission denied" should be logged

    @qtwebengine_notifications
    Scenario: notifications with ask -> false and save
        Given I have a fresh instance
        When I set content.notifications to ask
        And I open data/prompt/notifications.html in a new tab
        And I run :click-element id button
        And I wait for a prompt
        And I run :prompt-accept --save no
        Then the javascript message "notification permission denied" should be logged
        And the per-domain option content.notifications should be set to false for http://localhost:(port)

    @qtwebengine_notifications
    Scenario: notifications with ask -> true
        Given I have a fresh instance
        When I set content.notifications to ask
        And I open data/prompt/notifications.html in a new tab
        And I run :click-element id button
        And I wait for a prompt
        And I run :prompt-accept yes
        Then the javascript message "notification permission granted" should be logged

    @qtwebengine_notifications
    Scenario: notifications with ask -> true and save
        Given I have a fresh instance
        When I set content.notifications to ask
        And I open data/prompt/notifications.html in a new tab
        And I run :click-element id button
        And I wait for a prompt
        And I run :prompt-accept --save yes
        Then the javascript message "notification permission granted" should be logged
        And the per-domain option content.notifications should be set to true for http://localhost:(port)

    # This actually gives us a denied rather than an aborted
    @xfail_norun
    Scenario: notifications with ask -> abort
        Given I have a fresh instance
        When I set content.notifications to ask
        And I open data/prompt/notifications.html in a new tab
        And I run :click-element id button
        And I wait for a prompt
        And I run :leave-mode
        Then the javascript message "notification permission aborted" should be logged

    @qtwebengine_notifications
    Scenario: answering notification after closing tab
        Given I have a fresh instance
        When I set content.notifications to ask
        And I open data/prompt/notifications.html in a new tab
        And I run :click-element id button
        And I wait for a prompt
        And I run :tab-close
        And I wait for "Leaving mode KeyMode.yesno (reason: aborted)" in the log
        Then no crash should happen

    # Page authentication

    Scenario: Successful webpage authentification
        When I open basic-auth/user1/password1 without waiting
        And I wait for a prompt
        And I press the keys "user1"
        And I run :prompt-accept
        And I press the keys "password1"
        And I run :prompt-accept
        And I wait until basic-auth/user1/password1 is loaded
        Then the json on the page should be:
            {
              "authenticated": true,
              "user": "user1"
            }

    Scenario: Authentication with :prompt-accept value
        When I open about:blank in a new tab
        And I open basic-auth/user2/password2 without waiting
        And I wait for a prompt
        And I run :prompt-accept user2:password2
        And I wait until basic-auth/user2/password2 is loaded
        Then the json on the page should be:
            {
              "authenticated": true,
              "user": "user2"
            }

    Scenario: Authentication with invalid :prompt-accept value
        When I open about:blank in a new tab
        And I open basic-auth/user3/password3 without waiting
        And I wait for a prompt
        And I run :prompt-accept foo
        And I run :prompt-accept user3:password3
        Then the error "Value needs to be in the format username:password, but foo was given" should be shown

    Scenario: Tabbing between username and password
        When I open about:blank in a new tab
        And I open basic-auth/user4/password4 without waiting
        And I wait for a prompt
        And I press the keys "us"
        And I run :prompt-item-focus next
        And I press the keys "password4"
        And I run :prompt-item-focus prev
        And I press the keys "er4"
        And I run :prompt-accept
        And I run :prompt-accept
        And I wait until basic-auth/user4/password4 is loaded
        Then the json on the page should be:
            {
              "authenticated": true,
              "user": "user4"
            }

    @qtwebengine_skip
    Scenario: Cancellling webpage authentification with QtWebKit
        When I open basic-auth/user6/password6 without waiting
        And I wait for a prompt
        And I run :leave-mode
        Then basic-auth/user6/password6 should be loaded

    # :prompt-accept with value argument

    Scenario: Javascript alert with value
        When I set content.javascript.alert to true
        And I open data/prompt/jsalert.html
        And I run :click-element id button
        And I wait for a prompt
        And I run :prompt-accept foobar
        And I run :prompt-accept
        Then the javascript message "Alert done" should be logged
        And the error "No value is permitted with alert prompts!" should be shown

    Scenario: Javascript prompt with value
        When I set content.javascript.prompt to true
        And I open data/prompt/jsprompt.html
        And I run :click-element id button
        And I wait for a prompt
        And I press the keys "prompt test"
        And I run :prompt-accept "overridden value"
        Then the javascript message "Prompt reply: overridden value" should be logged

    Scenario: Javascript confirm with invalid value
        When I open data/prompt/jsconfirm.html
        And I run :click-element id button
        And I wait for a prompt
        And I run :prompt-accept nope
        And I run :prompt-accept yes
        Then the javascript message "confirm reply: true" should be logged
        And the error "Invalid value nope - expected yes/no!" should be shown

    Scenario: Javascript confirm with default value
        When I open data/prompt/jsconfirm.html
        And I run :click-element id button
        And I wait for a prompt
        And I run :prompt-accept
        And I run :prompt-accept yes
        Then the javascript message "confirm reply: true" should be logged
        And the error "No default value was set for this question!" should be shown

    # Other

    @qtwebengine_skip
    Scenario: Shutting down with a question
        When I open data/prompt/jsconfirm.html
        And I run :click-element id button
        And I wait for a prompt
        And I run :quit
        Then the javascript message "confirm reply: false" should be logged
        And qutebrowser should quit

    Scenario: Using :prompt-open-download with a prompt which does not support it
        When I open data/hello.txt
        And I run :quickmark-save
        And I wait for a prompt
        And I run :prompt-open-download
        And I run :prompt-accept test-prompt-open-download
        Then "Added quickmark test-prompt-open-download for *" should be logged

    Scenario: Using :prompt-item-focus with a prompt which does not support it
        When I open data/hello.txt
        And I run :quickmark-save
        And I wait for a prompt
        And I run :prompt-item-focus next
        And I run :prompt-accept test-prompt-item-focus
        Then "Added quickmark test-prompt-item-focus for *" should be logged

    Scenario: Getting question in command mode
        When I open data/hello.txt
        And I run :later 500 quickmark-save
        And I run :set-cmd-text :
        And I wait for a prompt
        And I run :prompt-accept prompt-in-command-mode
        Then "Added quickmark prompt-in-command-mode for *" should be logged

    # https://github.com/qutebrowser/qutebrowser/issues/1093
    @qtwebengine_skip: QtWebEngine doesn't open the second page/prompt
    Scenario: Keyboard focus with multiple auth prompts
        When I open basic-auth/user5/password5 without waiting
        And I open basic-auth/user6/password6 in a new tab without waiting
        And I wait for a prompt
        And I wait for a prompt
        # Second prompt (showed first)
        And I press the keys "user6"
        And I press the key "<Enter>"
        And I press the keys "password6"
        And I press the key "<Enter>"
        And I wait until basic-auth/user6/password6 is loaded
        # First prompt
        And I press the keys "user5"
        And I press the key "<Enter>"
        And I press the keys "password5"
        And I press the key "<Enter>"
        And I wait until basic-auth/user5/password5 is loaded
        # We're on the second page
        Then the json on the page should be:
            {
              "authenticated": true,
              "user": "user6"
            }

    # https://github.com/qutebrowser/qutebrowser/issues/1249#issuecomment-175205531
    # https://github.com/qutebrowser/qutebrowser/pull/2054#issuecomment-258285544
    @qtwebengine_notifications
    Scenario: Interrupting SSL prompt during a notification prompt
        Given I have a fresh instance
        When I set content.notifications to ask
        And I set content.ssl_strict to ask
        And I open data/prompt/notifications.html in a new tab
        And I run :click-element id button
        And I wait for a prompt
        And I open about:blank in a new tab
        And I load an SSL page
        And I wait for a prompt
        And I run :tab-close
        And I run :prompt-accept yes
        Then the javascript message "notification permission granted" should be logged
