# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Selecting files

    Background:
        Given I have a fresh instance

    ## select single file

    Scenario: Select file
        When I set up a fake single file fileselector selecting "foo.txt"
        And I trigger to upload a file
        Then "foo.txt" should be uploaded
