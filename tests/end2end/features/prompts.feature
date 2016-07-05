Feature: Prompts
    Various prompts (javascript, SSL errors, authentification, etc.)

    Background:
        Given I set general -> log-javascript-console to debug

    # Javascript

    Scenario: Javascript alert
        When I open data/prompt/jsalert.html
        And I click the button
        And I wait for a prompt
        And I run :prompt-accept
        Then the javascript message "Alert done" should be logged

    Scenario: Using content -> ignore-javascript-alert
        When I set content -> ignore-javascript-alert to true
        And I open data/prompt/jsalert.html
        And I click the button
        Then the javascript message "Alert done" should be logged

    Scenario: Javascript confirm - yes
        When I open data/prompt/jsconfirm.html
        And I click the button
        And I wait for a prompt
        And I run :prompt-yes
        Then the javascript message "confirm reply: true" should be logged

    Scenario: Javascript confirm - no
        When I open data/prompt/jsconfirm.html
        And I click the button
        And I wait for a prompt
        And I run :prompt-no
        Then the javascript message "confirm reply: false" should be logged

    Scenario: Javascript confirm - aborted
        When I open data/prompt/jsconfirm.html
        And I click the button
        And I wait for a prompt
        And I run :leave-mode
        Then the javascript message "confirm reply: false" should be logged

    @pyqt>=5.3.1
    Scenario: Javascript prompt
        When I open data/prompt/jsprompt.html
        And I click the button
        And I wait for a prompt
        And I press the keys "prompt test"
        And I run :prompt-accept
        Then the javascript message "Prompt reply: prompt test" should be logged

    @pyqt>=5.3.1
    Scenario: Rejected javascript prompt
        When I open data/prompt/jsprompt.html
        And I click the button
        And I wait for a prompt
        And I press the keys "prompt test"
        And I run :leave-mode
        Then the javascript message "Prompt reply: null" should be logged


    # Shift-Insert with prompt (issue 1299)

    @pyqt>=5.3.1
    Scenario: Pasting via shift-insert in prompt mode
        When selection is supported
        And I put "insert test" into the primary selection
        And I open data/prompt/jsprompt.html
        And I click the button
        And I wait for a prompt
        And I press the keys "<Shift-Insert>"
        And I run :prompt-accept
        Then the javascript message "Prompt reply: insert test" should be logged

    @pyqt>=5.3.1
    Scenario: Using content -> ignore-javascript-prompt
        When I set content -> ignore-javascript-prompt to true
        And I open data/prompt/jsprompt.html
        And I click the button
        Then the javascript message "Prompt reply: null" should be logged

    # SSL

    Scenario: SSL error with ssl-strict = false
        When I run :debug-clear-ssl-errors
        And I set network -> ssl-strict to false
        And I load an SSL page
        And I wait until the SSL page finished loading
        Then the error "SSL error: *" should be shown
        And the page should contain the plaintext "Hello World via SSL!"

    Scenario: SSL error with ssl-strict = true
        When I run :debug-clear-ssl-errors
        And I set network -> ssl-strict to true
        And I load an SSL page
        Then "Error while loading *: SSL handshake failed" should be logged
        And the page should contain the plaintext "Unable to load page"

    Scenario: SSL error with ssl-strict = ask -> yes
        When I run :debug-clear-ssl-errors
        And I set network -> ssl-strict to ask
        And I load an SSL page
        And I wait for a prompt
        And I run :prompt-yes
        And I wait until the SSL page finished loading
        Then the page should contain the plaintext "Hello World via SSL!"

    Scenario: SSL error with ssl-strict = ask -> no
        When I run :debug-clear-ssl-errors
        And I set network -> ssl-strict to ask
        And I load an SSL page
        And I wait for a prompt
        And I run :prompt-no
        Then "Error while loading *: SSL handshake failed" should be logged
        And the page should contain the plaintext "Unable to load page"

    # Geolocation

    Scenario: Always rejecting geolocation
        When I set content -> geolocation to false
        And I open data/prompt/geolocation.html in a new tab
        And I click the button
        Then the javascript message "geolocation permission denied" should be logged

    @ci @not_osx
    Scenario: Always accepting geolocation
        When I set content -> geolocation to true
        And I open data/prompt/geolocation.html in a new tab
        And I click the button
        Then the javascript message "geolocation permission denied" should not be logged

    @ci @not_osx
    Scenario: geolocation with ask -> true
        When I set content -> geolocation to ask
        And I open data/prompt/geolocation.html in a new tab
        And I click the button
        And I wait for a prompt
        And I run :prompt-yes
        Then the javascript message "geolocation permission denied" should not be logged

    Scenario: geolocation with ask -> false
        When I set content -> geolocation to ask
        And I open data/prompt/geolocation.html in a new tab
        And I click the button
        And I wait for a prompt
        And I run :prompt-no
        Then the javascript message "geolocation permission denied" should be logged

    Scenario: geolocation with ask -> abort
        When I set content -> geolocation to ask
        And I open data/prompt/geolocation.html in a new tab
        And I click the button
        And I wait for a prompt
        And I run :leave-mode
        Then the javascript message "geolocation permission denied" should be logged

    # Notifications

    Scenario: Always rejecting notifications
        When I set content -> notifications to false
        And I open data/prompt/notifications.html in a new tab
        And I click the button
        Then the javascript message "notification permission denied" should be logged

    Scenario: Always accepting notifications
        When I set content -> notifications to true
        And I open data/prompt/notifications.html in a new tab
        And I click the button
        Then the javascript message "notification permission granted" should be logged

    Scenario: notifications with ask -> false
        When I set content -> notifications to ask
        And I open data/prompt/notifications.html in a new tab
        And I click the button
        And I wait for a prompt
        And I run :prompt-no
        Then the javascript message "notification permission denied" should be logged

    Scenario: notifications with ask -> true
        When I set content -> notifications to ask
        And I open data/prompt/notifications.html in a new tab
        And I click the button
        And I wait for a prompt
        And I run :prompt-yes
        Then the javascript message "notification permission granted" should be logged

    # This actually gives us a denied rather than an aborted
    @xfail_norun
    Scenario: notifications with ask -> abort
        When I set content -> notifications to ask
        And I open data/prompt/notifications.html in a new tab
        And I click the button
        And I wait for a prompt
        And I run :leave-mode
        Then the javascript message "notification permission aborted" should be logged

    Scenario: answering notification after closing tab
        When I set content -> notifications to ask
        And I open data/prompt/notifications.html in a new tab
        And I click the button
        And I wait for a prompt
        And I run :tab-close
        And I wait for "Leaving mode KeyMode.yesno (reason: aborted)" in the log
        Then no crash should happen

    # Page authentication

    Scenario: Successful webpage authentification
        When I open basic-auth/user/password without waiting
        And I wait for a prompt
        And I press the keys "user"
        And I run :prompt-accept
        And I press the keys "password"
        And I run :prompt-accept
        And I wait until basic-auth/user/password is loaded
        Then the json on the page should be:
            {
              "authenticated": true,
              "user": "user"
            }
