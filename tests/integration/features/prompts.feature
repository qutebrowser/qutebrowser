Feature: Prompts
    Various prompts (javascript, SSL errors, authentification, etc.)

    Background:
        Given I set general -> log-javascript-console to debug

    # Javascript

    Scenario: Javascript alert
        When I open data/prompt/jsalert.html
        And I click the button
        And I run :prompt-accept
        Then the javascript message "Alert done" should be logged

    Scenario: Using content -> ignore-javascript-alert
        When I set content -> ignore-javascript-alert to true
        And I open data/prompt/jsalert.html
        # Can't use "I click the button" as it waits for a key mode change
        And I run :hint
        And I run :follow-hint a
        Then the javascript message "Alert done" should be logged

    Scenario: Javascript confirm - yes
        When I open data/prompt/jsconfirm.html
        And I click the button
        And I run :prompt-yes
        Then the javascript message "confirm reply: true" should be logged

    Scenario: Javascript confirm - no
        When I open data/prompt/jsconfirm.html
        And I click the button
        And I run :prompt-no
        Then the javascript message "confirm reply: false" should be logged

    Scenario: Javascript confirm - aborted
        When I open data/prompt/jsconfirm.html
        And I click the button
        And I run :leave-mode
        Then the javascript message "confirm reply: false" should be logged

    @pyqt531_or_newer
    Scenario: Javascript prompt
        When I open data/prompt/jsprompt.html
        And I click the button
        And I press the keys "prompt test"
        And I run :prompt-accept
        Then the javascript message "Prompt reply: prompt test" should be logged

    @pyqt531_or_newer
    Scenario: Rejected javascript prompt
        When I open data/prompt/jsprompt.html
        And I click the button
        And I press the keys "prompt test"
        And I run :leave-mode
        Then the javascript message "Prompt reply: null" should be logged

    @pyqt531_or_newer
    Scenario: Using content -> ignore-javascript-prompt
        When I set content -> ignore-javascript-prompt to true
        And I open data/prompt/jsprompt.html
        # Can't use "I click the button" as it waits for a key mode change
        And I run :hint
        And I run :follow-hint a
        Then the javascript message "Prompt reply: null" should be logged

    # SSL

    Scenario: SSL error with ssl-strict = false
        When I run :debug-clear-ssl-errors
        And I set network -> ssl-strict to false
        And I load a SSL page
        And I wait until the SSL page finished loading
        Then the error "SSL error: *" should be shown
        And the page should contain the plaintext "Hello World via SSL!"
