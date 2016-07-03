Feature: :spawn

    Scenario: Running :spawn
        When I run :spawn -v echo "Hello"
        Then the message "Command exited successfully." should be shown

    Scenario: Running :spawn with command that does not exist
        When I run :spawn command_does_not_exist127623
        Then the error "Error while spawning command: The process failed to start." should be shown

    Scenario: Starting a userscript which doesn't exist
        When I run :spawn -u this_does_not_exist
        Then the error "Error while spawning userscript: The process failed to start." should be shown

    # https://github.com/The-Compiler/qutebrowser/issues/1614
    @posix
    Scenario: Running :spawn with invalid quoting
        When I run :spawn ""'""
        Then the error "Error while splitting command: No closing quotation" should be shown

    Scenario: Running :spawn with url variable
        When I run :spawn echo {url}
        Then "Executing echo with args ['about:blank'], userscript=False" should be logged

    Scenario: Running :spawn with url variable in fully encoded format
        When I open data/title with spaces.html
        And I run :spawn echo {url}
        Then "Executing echo with args ['http://localhost:(port)/data/title%20with%20spaces.html'], userscript=False" should be logged

    Scenario: Running :spawn with url variable in pretty decoded format
        When I open data/title with spaces.html
        And I run :spawn echo {url:pretty}
        Then "Executing echo with args ['http://localhost:(port)/data/title with spaces.html'], userscript=False" should be logged

    @posix
    Scenario: Running :spawn with userscript
        When I open about:blank
        And I run :spawn -u (testdata)/userscripts/open_current_url
        And I wait until about:blank is loaded
        Then the following tabs should be open:
            - about:blank
            - about:blank (active)
