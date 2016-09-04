Feature: Command bar completion

    Scenario: No warnings when completing with one entry (#1600)
        Given I open about:blank
        When I run :set-cmd-text -s :open
        And I run :completion-item-focus next
        Then no crash should happen

    Scenario: Hang with many spaces in completion (#1919)
        # Generate some history data
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt
        And I open data/numbers/3.txt
        And I open data/numbers/4.txt
        And I open data/numbers/5.txt
        And I open data/numbers/6.txt
        And I open data/numbers/7.txt
        And I open data/numbers/8.txt
        And I open data/numbers/9.txt
        And I open data/numbers/10.txt
        And I run :set-cmd-text :open a                             b
        # Make sure qutebrowser doesn't hang
        And I run :message-info "Still alive!"
        Then the message "Still alive!" should be shown
