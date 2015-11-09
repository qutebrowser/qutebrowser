Feature: Downloading things from a website.

    Background:
        Given I set storage -> prompt-download-directory to false
        And I run :download-clear

    Scenario: Downloading which redirects with closed tab (issue 889)
        When I set tabs -> last-close to blank
        And I open data/downloads/issue889.html
        And I run :hint links download
        And I run :follow-hint a
        And I run :tab-close
        And I wait for "* Handling redirect" in the log
        Then no crash should happen

    Scenario: Downloading with error in closed tab (issue 889)
        When I set tabs -> last-close to blank
        And I open data/downloads/issue889.html
        And I run :hint links download
        And I run :follow-hint s
        And I run :tab-close
        And I wait for the error "Download error: * - server replied: NOT FOUND"
        And I run :download-retry
        And I wait for the error "Download error: * - server replied: NOT FOUND"
        Then no crash should happen

    Scenario: Retrying a failed download
        When I run :download http://localhost:(port)/does-not-exist
        And I wait for the error "Download error: * - server replied: NOT FOUND"
        And I run :download-retry
        And I wait for the error "Download error: * - server replied: NOT FOUND"
        Then the requests should be:
            does-not-exist
            does-not-exist

    Scenario: Retrying with no failed downloads
        When I open data/downloads/download.bin
        And I wait until the download is finished
        And I run :download-retry
        Then the error "No failed downloads!" should be shown.

    Scenario: Retrying with no downloads
        When I run :download-retry
        Then the error "No failed downloads!" should be shown.
