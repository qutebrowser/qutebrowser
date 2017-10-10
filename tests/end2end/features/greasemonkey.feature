# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Checking correct greasemonkey script support.

    Scenario: Have a gresemonkey script run on a page
        When I have a greasemonkey file saved
        And I run :greasemonkey-reload
        And I open data/title.html
        # This second reload is required in webengine < 5.8 for scripts
        # registered to run at document-start, some sort of timing issue.
        And I run :reload
        Then the javascript message "Script is running." should be logged
