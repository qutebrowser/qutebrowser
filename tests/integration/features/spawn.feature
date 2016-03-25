Feature: :spawn

    Scenario: Running :spawn
        When I run :spawn -v echo "Hello"
        Then the message "Command exited successfully." should be shown

    Scenario: Running :spawn with command that does not exist
        When I run :spawn command_does_not_exist127623
        Then the error "Error while spawning command: The process failed to start." should be shown

    Scenario: Running :spawn with invalid quoting
        When I run :spawn """
        Then the error "Error while splitting command: No closing quotation" should be shown

    Scenario: Running :spawn with url variable
        When I run :spawn echo {url}
        Then "Executing echo with args ['about:blank'], userscript=False" should be logged
