# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: qute://* urls.

    Scenario: Open qute://version
        When I open qute://version
        Then the page should contain the plaintext "Version info"
