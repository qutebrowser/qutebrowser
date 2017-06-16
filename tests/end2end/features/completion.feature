# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Using completion

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

    Scenario: Crash when pasting emoji into the command line (#2007)
        Given I open about:blank
        When I run :set-cmd-text -s :🌀
        Then no crash should happen

    Scenario: Using command completion
        When I run :set-cmd-text :
        Then the completion model should be CommandCompletionModel

    Scenario: Using help completion
        When I run :set-cmd-text -s :help
        Then the completion model should be HelpCompletionModel

    Scenario: Using quickmark completion
        When I run :set-cmd-text -s :quickmark-load
        Then the completion model should be QuickmarkCompletionModel

    Scenario: Using bookmark completion
        When I run :set-cmd-text -s :bookmark-load
        Then the completion model should be BookmarkCompletionModel

    # FIXME:conf

    # Scenario: Using bind completion
    #     When I run :set-cmd-text -s :bind X
    #     Then the completion model should be BindCompletionModel

    Scenario: Using session completion
        Given I open data/hello.txt
        And I run :session-save hello
        When I run :set-cmd-text -s :session-load
        And I run :completion-item-focus next
        And I run :completion-item-focus next
        And I run :session-delete hello
        And I run :command-accept
        Then the error "Session hello not found!" should be shown

    # FIXME:conf

    # Scenario: Using option completion
    #     When I run :set-cmd-text -s :set colors
    #     Then the completion model should be SettingOptionCompletionModel

    # Scenario: Using value completion
    #     When I run :set-cmd-text -s :set colors statusbar.bg
    #     Then the completion model should be SettingValueCompletionModel

    Scenario: Updating the completion in realtime
        Given I have a fresh instance
        And I set completion.quick to false
        When I open data/hello.txt
        And I run :set-cmd-text -s :buffer
        And I run :completion-item-focus next
        And I open data/hello2.txt in a new background tab
        And I run :completion-item-focus next
        And I open data/hello3.txt in a new background tab
        And I run :completion-item-focus next
        And I run :command-accept
        Then the following tabs should be open:
            - data/hello.txt
            - data/hello2.txt
            - data/hello3.txt (active)

    Scenario: Updating the value completion in realtime
        Given I set colors.statusbar.bg to green
        When I run :set-cmd-text -s :set colors statusbar.bg
        And I set colors.statusbar.bg to yellow
        And I run :completion-item-focus next
        And I run :completion-item-focus next
        And I set colors.statusbar.bg to red
        And I run :command-accept
        Then colors -> statusbar.bg should be yellow

    Scenario: Deleting an open tab via the completion
        Given I have a fresh instance
        When I open data/hello.txt
        And I open data/hello2.txt in a new tab
        And I run :set-cmd-text -s :buffer
        And I run :completion-item-focus next
        And I run :completion-item-focus next
        And I run :completion-item-del
        Then the following tabs should be open:
            - data/hello.txt (active)

    Scenario: Go to tab after moving a tab
        Given I have a fresh instance
        When I open data/hello.txt
        And I open data/hello2.txt in a new tab
        # Tricking completer into not updating tabs
        And I run :set-cmd-text -s :buffer
        And I run :tab-move 1
        And I run :buffer hello2.txt
        Then the following tabs should be open:
            - data/hello2.txt (active)
            - data/hello.txt
