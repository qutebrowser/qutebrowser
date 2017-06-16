# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Opening external editors

    ## :edit-url

    Scenario: Editing a URL
        When I open data/numbers/1.txt
        And I set up a fake editor replacing "1.txt" by "2.txt"
        And I run :edit-url
        Then data/numbers/2.txt should be loaded

    Scenario: Editing a URL with -t
        When I run :tab-only
        And I open data/numbers/1.txt
        And I set up a fake editor replacing "1.txt" by "2.txt"
        And I run :edit-url -t
        Then data/numbers/2.txt should be loaded
        And the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt (active)

    Scenario: Editing a URL with -b
        When I run :tab-only
        And I open data/numbers/1.txt
        And I set up a fake editor replacing "1.txt" by "2.txt"
        And I run :edit-url -b
        Then data/numbers/2.txt should be loaded
        And the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/2.txt

    Scenario: Editing a URL with -w
        When I open data/numbers/1.txt in a new tab
        And I run :tab-only
        And I set up a fake editor replacing "1.txt" by "2.txt"
        And I run :edit-url -w
        Then data/numbers/2.txt should be loaded
        And the session should look like:
            windows:
            - tabs:
              - active: true
                history:
                - active: true
                  url: http://localhost:*/data/numbers/1.txt
            - tabs:
              - active: true
                history:
                - active: true
                  url: http://localhost:*/data/numbers/2.txt

    Scenario: Editing a URL with -t and -b
        When I run :edit-url -t -b
        Then the error "Only one of -t/-b/-w can be given!" should be shown

    Scenario: Editing a URL with invalid URL
        When I set auto_search to never
        And I open data/hello.txt
        And I set up a fake editor replacing "http://localhost:(port)/data/hello.txt" by "foo!"
        And I run :edit-url
        Then the error "Invalid URL" should be shown

    Scenario: Spawning an editor successfully
        When I set up a fake editor returning "foobar"
        And I open data/editor.html
        And I run :click-element id qute-textarea
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :open-editor
        And I wait for "Read back: foobar" in the log
        And I run :click-element id qute-button
        Then the javascript message "text: foobar" should be logged

    Scenario: Spawning an editor in normal mode
        When I set up a fake editor returning "foobar"
        And I open data/editor.html
        And I run :click-element id qute-textarea
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :leave-mode
        And I wait for "Leaving mode KeyMode.insert (reason: leave current)" in the log
        And I run :open-editor
        And I wait for "Read back: foobar" in the log
        And I run :click-element id qute-button
        Then the javascript message "text: foobar" should be logged

    @qtwebengine_todo: Caret mode is not implemented yet
    Scenario: Spawning an editor in caret mode
        When I set up a fake editor returning "foobar"
        And I open data/editor.html
        And I run :click-element id qute-textarea
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :leave-mode
        And I wait for "Leaving mode KeyMode.insert (reason: leave current)" in the log
        And I run :enter-mode caret
        And I wait for "Entering mode KeyMode.caret (reason: command)" in the log
        And I run :open-editor
        And I wait for "Read back: foobar" in the log
        And I run :click-element id qute-button
        Then the javascript message "text: foobar" should be logged

    Scenario: Spawning an editor with existing text
        When I set up a fake editor replacing "foo" by "bar"
        And I open data/editor.html
        And I run :click-element id qute-textarea
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :insert-text foo
        And I wait for "Inserting text into element *" in the log
        And I run :open-editor
        And I wait for "Read back: bar" in the log
        And I run :click-element id qute-button
        Then the javascript message "text: bar" should be logged
