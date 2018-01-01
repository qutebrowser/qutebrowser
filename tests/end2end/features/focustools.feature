# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Using focustools

    # https://bugreports.qt.io/browse/QTBUG-58381
    Background:
        Given I clean up open tabs

    Scenario: Clear focus on mode leave
        When I open data/hints/input.html
        And I set input.blur_on_mode_leave to true
        And I hint with args "inputs" and follow a
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :leave-mode
        # The actual check is already done above
        Then no element should be focused

    Scenario: Don't clear focus on mode leave
        When I open data/hints/input.html
        And I set input.blur_on_mode_leave to false
        And I hint with args "inputs" and follow a
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :leave-mode
        # The actual check is already done above
        Then an element should be focused

    Scenario: Clear autofocusable elements on page load
        When I set input.blur_on_load.enabled to true
        And I open data/autofocus.html
        Then no element should be focused

    Scenario: Don't clear autofocusable elements on page load
        When I set input.blur_on_load.enabled to false
        And I open data/autofocus.html
        Then an element should be focused


    # TODO test delayed autofocusable elements as well
