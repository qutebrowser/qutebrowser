# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Opening external editors

    ## :edit-url

    Scenario: Editing a URL
        When I open data/numbers/1.txt
        And I setup a fake editor replacing "1.txt" by "2.txt"
        And I run :edit-url
        Then data/numbers/2.txt should be loaded

    Scenario: Editing a URL with -t
        When I run :tab-only
        And I open data/numbers/1.txt
        And I setup a fake editor replacing "1.txt" by "2.txt"
        And I run :edit-url -t
        Then data/numbers/2.txt should be loaded
        And the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt (active)

    Scenario: Editing a URL with -rt
        When I set tabs.new_position.related to prev
        And I open data/numbers/1.txt
        And I run :tab-only
        And I setup a fake editor replacing "1.txt" by "2.txt"
        And I run :edit-url -rt
        Then data/numbers/2.txt should be loaded
        And the following tabs should be open:
            - data/numbers/2.txt (active)
            - data/numbers/1.txt

    Scenario: Editing a URL with -b
        When I run :tab-only
        And I open data/numbers/1.txt
        And I setup a fake editor replacing "1.txt" by "2.txt"
        And I run :edit-url -b
        Then data/numbers/2.txt should be loaded
        And the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/2.txt

    Scenario: Editing a URL with -w
        When I run :window-only
        And I open data/numbers/1.txt in a new tab
        And I run :tab-only
        And I setup a fake editor replacing "1.txt" by "2.txt"
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
        And I run :window-only
        And I setup a fake editor replacing "1.txt" by "2.txt"
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
        And I setup a fake editor replacing "http://localhost:(port)/data/hello.txt" by "foo!"
        And I run :edit-url
        Then the error "Invalid URL" should be shown

    Scenario: Spawning an editor successfully
        Given I have a fresh instance
        When I setup a fake editor returning "foobar"
        And I open data/editor.html
        And I run :click-element id qute-textarea
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :edit-text
        And I wait for "Read back: foobar" in the log
        Then the javascript message "text: foobar" should be logged

    Scenario: Spawning an editor in normal mode
        When I setup a fake editor returning "foobar"
        And I open data/editor.html
        And I run :click-element id qute-textarea
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :mode-leave
        And I wait for "Leaving mode KeyMode.insert (reason: leave current)" in the log
        And I run :edit-text
        And I wait for "Read back: foobar" in the log
        Then the javascript message "text: foobar" should be logged

    # Could not get signals working on Windows
    # There's no guarantee that the tab gets deleted...
    @posix
    Scenario: Spawning an editor and closing the tab
        When I setup a fake editor that writes "foobar" on save
        And I open data/editor.html
        And I run :click-element id qute-textarea
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :edit-text
        And I wait until the editor has started
        And I set tabs.last_close to blank
        And I run :tab-close
        And I kill the waiting editor
        Then the error "Edited element vanished" should be shown
        And the message "Editor backup at *" should be shown

    # Could not get signals working on Windows
    @posix
    Scenario: Spawning an editor and saving
        When I setup a fake editor that writes "foobar" on save
        And I open data/editor.html
        And I run :click-element id qute-textarea
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :edit-text
        And I wait until the editor has started
        And I save without exiting the editor
        And I wait for "Read back: foobar" in the log
        Then the javascript message "text: foobar" should be logged

    Scenario: Spawning an editor in caret mode
        When I setup a fake editor returning "foobar"
        And I open data/editor.html
        And I run :click-element id qute-textarea
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :mode-leave
        And I wait for "Leaving mode KeyMode.insert (reason: leave current)" in the log
        And I run :mode-enter caret
        And I wait for "Entering mode KeyMode.caret (reason: command)" in the log
        And I run :edit-text
        And I wait for "Read back: foobar" in the log
        And I run :mode-leave
        Then the javascript message "text: foobar" should be logged

    Scenario: Spawning an editor with existing text
        When I setup a fake editor replacing "foo" by "bar"
        And I open data/editor.html
        And I run :click-element id qute-textarea
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :insert-text foo
        And I wait for "Inserting text into element *" in the log
        And I run :edit-text
        And I wait for "Read back: bar" in the log
        Then the javascript message "text: bar" should be logged

    ## :edit-command

    Scenario: Edit a command and run it
        When I run :set-cmd-text :message-info foo
        And I setup a fake editor replacing "foo" by "bar"
        And I run :edit-command --run
        Then the message "bar" should be shown
        And "Leaving mode KeyMode.command (reason: cmd accept)" should be logged

    Scenario: Edit a command and omit the start char
        When I setup a fake editor returning "message-info foo"
        And I run :edit-command
        Then the error "command must start with one of :/?" should be shown
        And "Leaving mode KeyMode.command *" should not be logged

    Scenario: Edit a command to be empty
        When I run :set-cmd-text :
        When I setup a fake editor returning empty text
        And I run :edit-command
        Then the error "command must start with one of :/?" should be shown
        And "Leaving mode KeyMode.command *" should not be logged

    ## select single file

    Scenario: Select one file with single file command
        When I setup a fake single_file fileselector selecting "tests/end2end/data/numbers/1.txt" and writes to a temporary file
        And I open data/fileselect.html
        And I run :click-element id single_file
        Then the javascript message "Files: 1.txt" should be logged

    Scenario: Select one file with single file command that writes to stdout
        When I setup a fake single_file fileselector selecting "tests/end2end/data/numbers/1.txt" and writes to stdout
        And I open data/fileselect.html
        And I run :click-element id single_file
        Then the javascript message "Files: 1.txt" should be logged

    Scenario: Select two files with single file command
        When I setup a fake single_file fileselector selecting "tests/end2end/data/numbers/1.txt tests/end2end/data/numbers/2.txt" and writes to a temporary file

        And I open data/fileselect.html
        And I run :click-element id single_file
        Then the javascript message "Files: 1.txt" should be logged
        And the warning "More than one file/folder chosen, using only the first" should be shown

    ## select multiple files

    Scenario: Select one file with multiple files command
        When I setup a fake multiple_files fileselector selecting "tests/end2end/data/numbers/1.txt" and writes to a temporary file

        And I open data/fileselect.html
        And I run :click-element id multiple_files
        Then the javascript message "Files: 1.txt" should be logged

    Scenario: Select two files with multiple files command
        When I setup a fake multiple_files fileselector selecting "tests/end2end/data/numbers/1.txt tests/end2end/data/numbers/2.txt" and writes to a temporary file

        And I open data/fileselect.html
        And I run :click-element id multiple_files
        Then the javascript message "Files: 1.txt, 2.txt" should be logged

    ## No temporary file created

    Scenario: File selector deleting temporary file
        When I set fileselect.handler to external
        And I set fileselect.single_file.command to ['rm', '{}']
        And I open data/fileselect.html
        And I run :click-element id single_file
        Then the javascript message "Files: 1.txt" should not be logged
        And the error "Failed to open tempfile *" should be shown
        And "Failed to delete tempfile *" should be logged with level error

    ## Select non-existent file

    Scenario: Select non-existent file
        When I set fileselect.handler to external
        When I setup a fake single_file fileselector selecting "tests/end2end/data/numbers/non-existent.txt" and writes to a temporary file
        And I open data/fileselect.html
        And I run :click-element id single_file
        Then the javascript message "Files: non-existent.txt" should not be logged
        And the warning "Ignoring non-existent file *non-existent.txt'" should be shown

    ## Select folder when expecting file

    Scenario: Select folder for file
        When I set fileselect.handler to external
        When I setup a fake single_file fileselector selecting "tests/end2end/data/numbers" and writes to a temporary file
        And I open data/fileselect.html
        And I run :click-element id single_file
        Then the javascript message "Files: *" should not be logged
        And the warning "Expected file but got folder, ignoring *numbers'" should be shown

    ## Select file when expecting folder

    @qtwebkit_skip
    Scenario: Select file for folder
        When I set fileselect.handler to external
        When I setup a fake folder fileselector selecting "tests/end2end/data/numbers/1.txt" and writes to a temporary file
        And I open data/fileselect.html
        And I run :click-element id folder
        Then the javascript message "Files: 1.txt" should not be logged
        And the warning "Expected folder but got file, ignoring *1.txt'" should be shown

    ## Select folder

    @qtwebkit_skip
    Scenario: Select one folder with folder command
        When I set fileselect.handler to external
        And I setup a fake folder fileselector selecting "tests/end2end/data/backforward/" and writes to a temporary file
        And I open data/fileselect.html
        And I run :click-element id folder
        Then the javascript message "Files: 1.txt, 2.txt, 3.txt" should be logged
