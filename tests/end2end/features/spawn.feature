# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: :spawn

    Scenario: Running :spawn
        When I run :spawn -v (echo-exe) "Hello"
        Then the message "Command exited successfully." should be shown

    Scenario: Running :spawn with command that does not exist
        When I run :spawn command_does_not_exist127623
        Then the error "Error while spawning command: *" should be shown

    Scenario: Starting a userscript which doesn't exist
        When I run :spawn -u this_does_not_exist
        Then the error "Userscript 'this_does_not_exist' not found in userscript directories *" should be shown

    Scenario: Starting a userscript with absoloute path which doesn't exist
        When I run :spawn -u /this_does_not_exist
        Then the error "Userscript '/this_does_not_exist' not found" should be shown

    # https://github.com/qutebrowser/qutebrowser/issues/1614
    @posix
    Scenario: Running :spawn with invalid quoting
        When I run :spawn ""'""
        Then the error "Error while splitting command: No closing quotation" should be shown

    Scenario: Running :spawn with url variable
        When I run :spawn (echo-exe) {url}
        Then "Executing * with args ['about:blank'], userscript=False" should be logged

    Scenario: Running :spawn with url variable in fully encoded format
        When I open data/title with spaces.html
        And I run :spawn (echo-exe) {url}
        Then "Executing * with args ['http://localhost:(port)/data/title%20with%20spaces.html'], userscript=False" should be logged

    Scenario: Running :spawn with url variable in pretty decoded format
        When I open data/title with spaces.html
        And I run :spawn (echo-exe) {url:pretty}
        Then "Executing * with args ['http://localhost:(port)/data/title with spaces.html'], userscript=False" should be logged

    Scenario: Running :spawn with -m
        When I run :spawn -m (echo-exe) Message 1
        Then the message "Message 1" should be shown

    Scenario: Running :spawn with -u -m
        When I run :spawn -u -m (echo-exe) Message 2
        Then the message "Message 2" should be shown

    @posix
    Scenario: Running :spawn with userscript
        When I open data/hello.txt
        And I run :spawn -u (testdata)/userscripts/open_current_url
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - data/hello.txt
            - data/hello.txt (active)

    @posix
    Scenario: Running :spawn with userscript and count
        When I run :spawn -u (testdata)/userscripts/hello_if_count with count 5
        Then the message "Count is five!" should be shown

    @posix
    Scenario: Running :spawn with userscript and no count
        When I run :spawn -u (testdata)/userscripts/hello_if_count
        Then the message "No count!" should be shown


    @windows
    Scenario: Running :spawn with userscript on Windows
        When I open data/hello.txt
        And I run :spawn -u (testdata)/userscripts/open_current_url.bat
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - data/hello.txt
            - data/hello.txt (active)

    @posix
    Scenario: Running :spawn with userscript that expects the stdin getting closed
        When I run :spawn -u (testdata)/userscripts/stdinclose.py
        Then the message "stdin closed" should be shown
