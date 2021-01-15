# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Selecting files

    Background:
        Given I have a fresh instance

    ## select single file

    Scenario: Select one file with single command
        When I set up a fake single file fileselector selecting "tests/end2end/data/numbers/1.txt"
        And I open data/fileselect/fileselect.html
        And I run :click-element id single_file
        Then the javascript message "File selected: 1.txt" should be logged

    Scenario: Select two files with single command
        When I set up a fake single file fileselector selecting "tests/end2end/data/numbers/1.txt tests/end2end/data/numbers/2.txt"
        And I open data/fileselect/fileselect.html
        And I run :click-element id single_file
        Then the javascript message "File selected: 1.txt" should be logged
        Then the javascript message "File selected: 2.txt" should not be logged

    ## select multiple files

    Scenario: Select one file with multiple command
        When I set up a fake multiple files fileselector selecting "tests/end2end/data/numbers/1.txt"
        And I open data/fileselect/fileselect.html
        And I run :click-element id multiple_files
        Then the javascript message "File selected: 1.txt" should be logged

    Scenario: Select two files with multiple command
        When I set up a fake multiple files fileselector selecting "tests/end2end/data/numbers/1.txt tests/end2end/data/numbers/2.txt"
        And I open data/fileselect/fileselect.html
        And I run :click-element id multiple_files
        Then the javascript message "File selected: 1.txt" should be logged
        And the javascript message "File selected: 2.txt" should be logged
