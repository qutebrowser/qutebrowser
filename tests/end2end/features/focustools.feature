# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Using focustools

    # https://bugreports.qt.io/browse/QTBUG-58381
    Background:
        Given I clean up open tabs

    Scenario: Clear focus on mode leave
        When I open data/hints/input.html
        And I set input.focus.blur_on_mode_leave to true
        And I hint with args "inputs" and follow a
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :leave-mode
        Then no element should be focused

    Scenario: Refocus cleared element on mode enter
        When I open data/hints/input.html
        And I set input.focus.blur_on_mode_leave to true
        And I set input.focus.focus_on_mode_enter to true
        And I hint with args "inputs" and follow a
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :leave-mode
        And I run :enter-mode insert
        Then an element should be focused

    Scenario: Don't clear focus on mode leave
        When I open data/hints/input.html
        And I set input.focus.blur_on_mode_leave to false
        And I hint with args "inputs" and follow a
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :leave-mode
        Then an element should be focused


    Scenario: Clear autofocusable elements on page load
        When I set input.focus.blur_on_load_enabled to true
        And I open data/autofocus.html
        Then no element should be focused

    Scenario: Don't clear autofocusable elements on page load
        When I set input.focus.blur_on_load_enabled to false
        And I open data/autofocus.html
        Then an element should be focused

    Scenario: Clear delayed focused elements on page load
        When I set input.focus.blur_on_load_enabled to true
        And I open data/autofocus_delayed.html
        Then no element should be focused
