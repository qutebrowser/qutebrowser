Feature: Setting settings.

    Background:
        Given I set ui -> message-timeout to 100

    Scenario: Using :set
        When I run :set colors statusbar.bg magenta
        Then colors -> statusbar.bg should be magenta

    Scenario: Only a section
        When I run :set colors
        Then the error "set: Either both section and option have to be given, or neither!" should be shown

    Scenario: Without value
        When I run :set colors statusbar.bg
        Then the error "set: The following arguments are required: value" should be shown

    Scenario: Invalid section
        When I run :set blah blub foo
        Then the error "set: Section 'blah' does not exist!" should be shown

    Scenario: Invalid option
        When I run :set general blub foo
        Then the error "set: No option 'blub' in section 'general'" should be shown

    Scenario: Toggling an option
        When I run :set general auto-save-config false
        And I run :set general auto-save-config!
        Then general -> auto-save-config should be true

    Scenario: Toggling a non-bool option
        When I run :set colors statusbar.bg!
        Then the error "set: Attempted inversion of non-boolean value." should be shown

    Scenario: Getting an option
        When I run :set colors statusbar.bg magenta
        And I run :set colors statusbar.bg?
        Then the message "colors statusbar.bg = magenta" should be shown

    Scenario: Using -p
        When I run :set -p colors statusbar.bg red
        Then the message "colors statusbar.bg = red" should be shown

    Scenario: Using ! and -p
        When I run :set general auto-save-config false
        And I run :set -p general auto-save-config!
        Then the message "general auto-save-config = true" should be shown

    Scenario: Setting an invalid value
        When I run :set general auto-save-config blah
        Then the error "set: Invalid value 'blah' - must be a boolean!" should be shown

    Scenario: Setting a temporary option
        # We don't actually check if the option is temporary as this isn't easy
        # to check.
        When I run :set -t colors statusbar.bg green
        Then colors -> statusbar.bg should be green

    Scenario: Opening qute:settings
        When I run :set
        And I wait until qute:settings is loaded
        Then the following tabs should be open:
            - qute:settings (active)

    Scenario: Empty option with ? (issue 1109)
        When I run :set general ?
        Then the error "set: The following arguments are required: value" should be shown

    Scenario: Invalid section and empty option with ? (issue 1109)
        When I run :set blah ?
        Then the error "set: The following arguments are required: value" should be shown

    Scenario: Invalid option with ? (issue 1109)
        When I run :set general foo?
        Then the error "set: No option 'foo' in section 'general'" should be shown

    Scenario: Invalid section/option with ? (issue 1109)
        When I run :set blah foo ?
        Then the error "set: Section 'blah' does not exist!" should be shown

    Scenario: Empty option with !
        When I run :set general !
        Then the error "set: The following arguments are required: value" should be shown

    Scenario: Invalid section and empty option with !
        When I run :set blah !
        Then the error "set: The following arguments are required: value" should be shown

    Scenario: Invalid option with !
        When I run :set general foo!
        Then the error "set: No option 'foo' in section 'general'" should be shown

    Scenario: Invalid section/option with !
        When I run :set blah foo !
        Then the error "set: Section 'blah' does not exist!" should be shown
