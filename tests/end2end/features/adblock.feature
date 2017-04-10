# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Ad blocking

    Scenario: Simple adblock update
        When I set up "simple" as block lists
        And I run :adblock-update
        Then the message "adblock: Read 1 hosts from 1 sources." should be shown
