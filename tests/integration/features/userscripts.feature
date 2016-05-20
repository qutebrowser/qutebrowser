Scenario: Starting an userscript which doesn't exist
    When I run :spawn -u this_does_not_exist
    Then the error "Error while spawning userscript: The process failed to start." should be shown
