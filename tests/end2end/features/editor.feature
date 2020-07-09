# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Opening external editors

    Background:
        Given I have a fresh instance

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

    Scenario: Editing a URL with -rt
        When I set tabs.new_position.related to prev
        And I open data/numbers/1.txt
        And I set up a fake editor replacing "1.txt" by "2.txt"
        And I run :edit-url -rt
        Then data/numbers/2.txt should be loaded
        And the following tabs should be open:
            - data/numbers/2.txt (active)
            - data/numbers/1.txt

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

    Scenario: Editing a URL with -p
        When I open data/numbers/1.txt in a new tab
        And I run :tab-only
        And I set up a fake editor replacing "1.txt" by "2.txt"
        And I run :edit-url -p
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
              private: true

    Scenario: Editing a URL with -t and -b
        When I run :edit-url -t -b
        Then the error "Only one of -t/-b/-w can be given!" should be shown

    @flaky
    Scenario: Editing a URL with invalid URL
        When I set url.auto_search to never
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
        Then the javascript message "text: foobar" should be logged

    # Could not get signals working on Windows
    # There's no guarantee that the tab gets deleted...
    @posix
    Scenario: Spawning an editor and closing the tab
        When I set up a fake editor that writes "foobar" on save
        And I open data/editor.html
        And I run :click-element id qute-textarea
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :open-editor
        And I wait until the editor has started
        And I set tabs.last_close to blank
        And I run :tab-close
        And I kill the waiting editor
        Then the error "Edited element vanished" should be shown
        And the message "Editor backup at *" should be shown

    # Could not get signals working on Windows
    @posix
    Scenario: Spawning an editor and saving
        When I set up a fake editor that writes "foobar" on save
        And I open data/editor.html
        And I run :click-element id qute-textarea
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :open-editor
        And I wait until the editor has started
        And I save without exiting the editor
        And I wait for "Read back: foobar" in the log
        Then the javascript message "text: foobar" should be logged

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
        Then the javascript message "text: bar" should be logged

    ## :edit-command

    Scenario: Edit a command and run it
        When I run :set-cmd-text :message-info foo
        And I set up a fake editor replacing "foo" by "bar"
        And I run :edit-command --run
        Then the message "bar" should be shown
        And "Leaving mode KeyMode.command (reason: cmd accept)" should be logged

    Scenario: Edit a command and omit the start char
        When I set up a fake editor returning "message-info foo"
        And I run :edit-command
        Then the error "command must start with one of :/?" should be shown
        And "Leaving mode KeyMode.command *" should not be logged

    Scenario: Edit a command to be empty
        When I run :set-cmd-text :
        When I set up a fake editor returning empty text
        And I run :edit-command
        Then the error "command must start with one of :/?" should be shown
        And "Leaving mode KeyMode.command *" should not be logged
