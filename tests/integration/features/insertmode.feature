Feature: Insert mode

    Background:

    # textarea tag

    Scenario: Basic insertion of text in textarea
        When I open data/inputs.html
        And I run :hint all
        And I run :follow-hint a
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
        When I open data/inputs.html
        And I run :hint all
        And I put "superqutebrowser" into the primary selection
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
        When I open data/inputs.html
        And I run :hint all
        And I run :follow-hint s
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
        When I open data/inputs.html
        And I run :hint all
        And I put "superqutebrowser" into the primary selection
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

    # input -> auto-insert-mode

    Scenario: With input -> auto-insert-mode enabled
        When I set input -> auto-insert-mode to true
        And I open data/inputs_autofocus.html
        And I press the keys "qutebrowser"
        And I run :hint all
        And I run :follow-hint a
        And I run :enter-mode caret
        And I run :toggle-selection
        And I run :move-to-prev-word
        And I run :yank-selected
        Then the message "11 chars yanked to clipboard" should be shown
        And the clipboard should contain "qutebrowser"


    # input -> auto-leave-insert-mode

    Scenario: With input -> auto-leave-insert-mode enabled
        When I set input -> auto-leave-insert-mode to true
        And I open data/inputs_autofocus.html
        And I press the keys "abcd"
        And I run :hint all
        And I run :follow-hint s
        And I run :paste-primary
        Then the error "paste-primary: This command is only allowed in insert mode." should be shown

    # Scenario: Select an option from a dropdown
    #     When I run :follow-hint d
    #     And I run :enter-mode insert
    #     And I press the keys "b"
    #     And I press the keys "<Enter>"
    #     Then the following tabs should be open:
    #         - about:blank (active)
