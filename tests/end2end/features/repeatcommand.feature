Feature: Repeating
    Test the repeat-command command.

    Background:
        Given I run :tab-only

    Scenario: :repeat-command
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-close with count 1
        And I run :repeat-command
        Then the following tabs should be open:
            - data/numbers/3.txt (active)

    Scenario: :repeat-command with count
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-close with count 1
        And I run :repeat-command with count 2
        Then the following tabs should be open:
            - data/numbers/2.txt (active)

    Scenario: :repeat-command with not-normal command inbetween
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-close with count 1
        And I run :prompt-accept
        And I run :repeat-command
        Then the following tabs should be open:
            - data/numbers/3.txt (active)
        And the error "prompt-accept: This command is only allowed in prompt/yesno mode." should be shown
