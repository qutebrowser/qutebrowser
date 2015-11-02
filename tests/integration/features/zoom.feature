Feature: Zooming in and out

    Background:
        Given I open data/hello.txt

    Scenario: Zooming in
        When I run :zoom-in
        Then the message "Zoom level: 110%" should be shown.
        And the session should look like:
            windows:
            - tabs:
              - ...
              - history:
                - zoom: 1.1

    Scenario: Zooming out
        When I run :zoom-out
        Then the message "Zoom level: 90%" should be shown.
        And the session should look like:
            windows:
            - tabs:
              - ...
              - history:
                - zoom: 0.9

    Scenario: Setting zoom
        When I run :zoom 50
        Then the message "Zoom level: 50%" should be shown.
        And the session should look like:
            windows:
            - tabs:
              - ...
              - history:
                - zoom: 0.5

    Scenario: Resetting zoom
        When I run :zoom 50
        And I run :zoom
        Then the message "Zoom level: 100%" should be shown.
        And the session should look like:
            windows:
            - tabs:
              - ...
              - history:
                - zoom: 1.0
