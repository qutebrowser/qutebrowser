# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Selecting files

    Background:
        Given I have a fresh instance

    ## select single file

    Scenario: Select one file with single command
        When I set up a fake single file fileselector selecting "foo.txt"
        And I open data/fileselect/single_fileselect.html
        And I run :click-element id file_upload
        Then the javascript message "File selected: foo.txt" should be logged

    Scenario: Select two files with single command
        When I set up a fake single file fileselector selecting "foo.txt bar.txt"
        And I open data/fileselect/single_fileselect.html
        And I run :click-element id file_upload
        Then the javascript message "File selected: foo.txt" should be logged
        Then the javascript message "File selected: bar.txt" should not be logged

    ## select multiple files

    Scenario: Select one file with multiple command
        When I set up a fake multiple files fileselector selecting "foo.txt"
        And I open data/fileselect/multiple_fileselect.html
        And I run :click-element id file_upload
        Then the javascript message "File selected: foo.txt" should be logged

    Scenario: Select two files with multiple command
        When I set up a fake multiple files fileselector selecting "foo.txt bar.txt"
        And I open data/fileselect/multiple_fileselect.html
        And I run :click-element id file_upload
        Then the javascript message "File selected: foo.txt" should be logged
        And the javascript message "File selected: bar.txt" should be logged
