# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Setting settings.

    Background:
        Given I set messages.timeout to 100

    Scenario: Using :set
        When I run :set colors.statusbar.normal.bg magenta
        Then colors.statusbar.normal.bg should be set to magenta

    Scenario: Without value
        When I run :set colors.statusbar.normal.bg
        Then the error "set: The following arguments are required: value" should be shown

    Scenario: Invalid option
        When I run :set blub foo
        Then the error "set: No option 'blub'" should be shown

    Scenario: Toggling an option
        When I run :set auto_save.config false
        And I run :set auto_save.config!
        Then auto_save.config should be set to true

    Scenario: Toggling a non-bool option
        When I run :set colors.statusbar.normal.bg!
        Then the error "set: Attempted inversion of non-boolean value." should be shown

    Scenario: Cycling an option
        When I run :set colors.statusbar.normal.bg magenta
        And I run :set colors.statusbar.normal.bg green magenta blue yellow
        Then colors.statusbar.normal.bg should be set to blue

    Scenario: Cycling an option through the end of the list
        When I run :set colors.statusbar.normal.bg yellow
        And I run :set colors.statusbar.normal.bg green magenta blue yellow
        Then colors.statusbar.normal.bg should be set to green

    Scenario: Cycling an option that's not on the list
        When I run :set colors.statusbar.normal.bg red
        And I run :set colors.statusbar.normal.bg green magenta blue yellow
        Then colors.statusbar.normal.bg should be set to green

    Scenario: Cycling through a single option
        When I run :set colors.statusbar.normal.bg red
        And I run :set colors.statusbar.normal.bg red
        Then colors.statusbar.normal.bg should be set to red

    Scenario: Getting an option
        When I run :set colors.statusbar.normal.bg magenta
        And I run :set colors.statusbar.normal.bg?
        Then the message "colors.statusbar.normal.bg = magenta" should be shown

    Scenario: Using -p
        When I run :set -p colors.statusbar.normal.bg red
        Then the message "colors.statusbar.normal.bg = red" should be shown

    Scenario: Using ! and -p
        When I run :set auto_save.config false
        And I run :set -p auto_save.config!
        Then the message "auto_save.config = true" should be shown

    Scenario: Setting an invalid value
        When I run :set auto_save.config blah
        Then the error "set: Invalid value 'blah' - must be a boolean!" should be shown

    Scenario: Setting a temporary option
        # We don't actually check if the option is temporary as this isn't easy
        # to check.
        When I run :set -t colors.statusbar.normal.bg green
        Then colors.statusbar.normal.bg should be set to green

    # qute://settings isn't actually implemented on QtWebEngine, but this works
    # (and displays a page saying it's not available)
    Scenario: Opening qute://settings
        When I run :set
        And I wait until qute://settings is loaded
        Then the following tabs should be open:
            - qute://settings (active)

    Scenario: Focusing input fields in qute://settings and entering valid value
        When I set ignore_case to never
        And I open qute://settings
        # scroll to the right - the table does not fit in the default screen
        And I run :scroll-perc -x 100
        And I hint with args "inputs" and follow a
        And I wait for "Entering mode KeyMode.insert *" in the log
        And I press the key "<Ctrl+Backspace>"
        And I press the keys "always"
        And I press the key "<Escape>"
        # an explicit Tab to unfocus the input field seems to stabilize the tests
        And I press the key "<Tab>"
        Then ignore_case should be set to always

    Scenario: Focusing input fields in qute://settings and entering invalid value
        When I open qute://settings
        # scroll to the right - the table does not fit in the default screen
        And I run :scroll-perc -x 100
        And I hint with args "inputs" and follow a
        And I wait for "Entering mode KeyMode.insert *" in the log
        And I press the key "<Ctrl+Backspace>"
        And I press the keys "foo"
        And I press the key "<Escape>"
        # an explicit Tab to unfocus the input field seems to stabilize the tests
        And I press the key "<Tab>"
        Then "Invalid value 'foo' *" should be logged

    Scenario: Empty option with ? (issue 1109)
        When I run :set ?
        Then the error "set: The following arguments are required: value" should be shown

    Scenario: Invalid option with ? (issue 1109)
        When I run :set foo?
        Then the error "set: No option 'foo'" should be shown

    Scenario: Invalid option with !
        When I run :set foo!
        Then the error "set: No option 'foo'" should be shown
