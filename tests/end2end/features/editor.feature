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
        When I set general -> auto-search to false
        And I open data/hello.txt
        And I set up a fake editor replacing "http://localhost:(port)/data/hello.txt" by "foo!"
        And I run :edit-url
        Then the error "Invalid URL" should be shown

    Scenario: Spawning an editor successfully
        When I set up a fake editor returning "foobar"
        And I open data/editor.html
        And I run :hint all
        And I run :follow-hint a
        And I wait for "Clicked editable element!" in the log
        And I run :open-editor
        And I wait for "Read back: foobar" in the log
        And I run :hint all
        And I run :follow-hint s
        Then the javascript message "text: foobar" should be logged
