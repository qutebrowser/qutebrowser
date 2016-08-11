Feature: Using completion

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

    Scenario: Using bind completion
        When I run :set-cmd-text -s :bind X
        Then the completion model should be BindCompletionModel

    Scenario: Using session completion
        Given I open data/hello.txt
        And I run :session-save hello
        When I run :set-cmd-text -s :session-load
        And I run :completion-item-focus next
        And I run :completion-item-focus next
        And I run :session-delete hello
        And I run :command-accept
        Then the error "Session hello not found!" should be shown

    Scenario: Using option completion
        When I run :set-cmd-text -s :set colors
        Then the completion model should be SettingOptionCompletionModel

    Scenario: Using value completion
        When I run :set-cmd-text -s :set colors statusbar.bg
        Then the completion model should be SettingValueCompletionModel

    Scenario: Using value completion multiple times
        When I run :set-cmd-text -s :set --cycle colors statusbar.bg black
        Then the completion model should be SettingValueCompletionModel

    Scenario: Updating the completion in realtime
        Given I have a fresh instance
        And I set completion -> quick-complete to false
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
        Given I set colors -> statusbar.bg to green
        When I run :set-cmd-text -s :set colors statusbar.bg
        And I set colors -> statusbar.bg to yellow
        And I run :completion-item-focus next
        And I run :completion-item-focus next
        And I set colors -> statusbar.bg to red
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
