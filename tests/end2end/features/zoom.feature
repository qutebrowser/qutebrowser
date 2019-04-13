# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Zooming in and out

    Background:
        Given I open data/hello.txt
        And I set zoom.levels to [50%, 90%, 100%, 110%, 120%]
        And I run :tab-only

    Scenario: Zooming in
        When I run :zoom-in
        Then the message "Zoom level: 110%" should be shown
        And the zoom should be 110%

    Scenario: Zooming out
        When I run :zoom-out
        Then the message "Zoom level: 90%" should be shown
        And the zoom should be 90%

    Scenario: Zooming in with count
        When I run :zoom-in with count 2
        Then the message "Zoom level: 120%" should be shown
        And the zoom should be 120%

    # https://github.com/qutebrowser/qutebrowser/issues/1118
    Scenario: Zooming in with very big count
        When I run :zoom-in with count 99999999999
        Then the message "Zoom level: 120%" should be shown
        And the zoom should be 120%

    # https://github.com/qutebrowser/qutebrowser/issues/1118
    Scenario: Zooming out with very big count
        When I run :zoom-out with count 99999999999
        Then the message "Zoom level: 50%" should be shown
        And the zoom should be 50%

    # https://github.com/qutebrowser/qutebrowser/issues/1118
    Scenario: Zooming in with very big count and snapping in
        When I run :zoom-in with count 99999999999
        And I run :zoom-out
        Then the message "Zoom level: 110%" should be shown
        And the zoom should be 110%

    Scenario: Zooming out with count
        When I run :zoom-out with count 2
        Then the message "Zoom level: 50%" should be shown
        And the zoom should be 50%

    Scenario: Setting zoom
        When I run :zoom 50
        Then the message "Zoom level: 50%" should be shown
        And the zoom should be 50%

    Scenario: Setting zoom with trailing %
        When I run :zoom 50%
        Then the message "Zoom level: 50%" should be shown
        And the zoom should be 50%

    Scenario: Setting zoom with count
        When I run :zoom with count 40
        Then the message "Zoom level: 40%" should be shown
        And the zoom should be 40%

    Scenario: Resetting zoom
        When I set zoom.default to 42%
        And I run :zoom 50
        And I run :zoom
        Then the message "Zoom level: 42%" should be shown
        And the zoom should be 42%

    Scenario: Setting zoom to invalid value
        When I run :zoom -1
        Then the error "Can't zoom -1%!" should be shown

    Scenario: Setting zoom with very big count
        When I run :zoom with count 99999999999
        Then the message "Zoom level: 99999999999%" should be shown

    Scenario: Setting zoom with argument and count
        When I run :zoom 50 with count 60
        Then the message "Zoom level: 60%" should be shown
        And the zoom should be 60%

    # https://github.com/qutebrowser/qutebrowser/issues/2507
    # Using 127.0.0.1 because separate domain is required to reproduce
    Scenario: Qutebrowser enforces correct zoom level
        When I run :zoom 150%
        And I open data/search.html
        And I run :open http://127.0.0.1:(port)/data/long_load.html
        And I wait until http://127.0.0.1:(port)/data/long_load.html is loaded
        And I run :back
        And I wait until data/search.html is loaded
        Then the zoom should be 150%

    # Fixed in QtWebEngine branch
    @xfail
    Scenario: Zooming in with cloned tab
        When I set zoom.default to 100%
        And I run :zoom-in
        And I wait for "Zoom level: 110%" in the log
        And I run :tab-clone
        And I wait until data/hello.txt is loaded
        And I run :zoom-in
        Then the message "Zoom level: 120%" should be shown
        And the zoom should be 120%

    # https://github.com/qutebrowser/qutebrowser/issues/2183
    @qtwebengine_flaky
    Scenario: Setting a default zoom
        When I set zoom.default to 200%
        And I open data/hello.txt in a new tab
        And I run :tab-only
        Then the zoom should be 200%

    Scenario: Zooming in with --quiet
        When I run :zoom-in --quiet
        Then "Zoom level: *" should not be logged

    Scenario: Zooming out with --quiet
        When I run :zoom-out --quiet
        Then "Zoom level: *" should not be logged

    Scenario: Zooming with --quiet
        When I run :zoom --quiet
        Then "Zoom level: *" should not be logged
