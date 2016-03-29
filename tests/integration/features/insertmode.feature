Feature: Insert mode

    Background:
      Given I open data/inputs.html
      And I run :hint all

    # textarea tag

    Scenario: Basic insertion of text in textarea
        When I run :follow-hint a
        And I press the keys "qutebrowser"
        And I run :hint all
        And I run :follow-hint a
        And I run :enter-mode caret
        And I run :toggle-selection
        And I run :move-to-prev-word
        And I run :yank-selected
        Then the message "11 chars yanked to clipboard" should be shown
        And the clipboard should contain "qutebrowser"

    Scenario: Paste from primary selection into textarea
        When I put "superqutebrowser" into the primary selection
        And I run :follow-hint a
        And I run :paste-primary
        And I run :hint all
        And I run :follow-hint a
        And I run :enter-mode caret
        And I run :toggle-selection
        And I run :move-to-prev-word
        And I run :yank-selected
        Then the message "16 chars yanked to clipboard" should be shown
        And the clipboard should contain "superqutebrowser"

    # input tag

    Scenario: Basic insertion of text in input field
        When I run :follow-hint s
        And I press the keys "qutebrowser"
        And I run :hint all
        And I run :follow-hint s
        And I run :enter-mode caret
        And I run :toggle-selection
        And I run :move-to-prev-word
        And I run :yank-selected
        Then the message "11 chars yanked to clipboard" should be shown
        And the clipboard should contain "qutebrowser"

    Scenario: Paste from primary selection into input field
        When I put "superqutebrowser" into the primary selection
        And I run :follow-hint s
        And I run :paste-primary
        And I run :hint all
        And I run :follow-hint s
        And I run :enter-mode caret
        And I run :toggle-selection
        And I run :move-to-prev-word
        And I run :yank-selected
        Then the message "16 chars yanked to clipboard" should be shown
        And the clipboard should contain "superqutebrowser"

    # # select/option tag

    # Scenario: Select an option from a dropdown
    #     When I run :follow-hint d
    #     And I run :enter-mode insert
    #     And I press the keys "b"
    #     And I press the keys "<Enter>"
    #     Then the following tabs should be open:
    #         - about:blank (active)
