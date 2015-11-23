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

    Scenario: :download with deprecated dest-old argument
        When I run :download http://localhost:(port)/ deprecated-argument
        Then the warning ":download [url] [dest] is deprecated - use download --dest [dest] [url]" should be shown.

    Scenario: Two destinations given
        When I run :download --dest destination2 http://localhost:(port)/ destination1
        Then the warning ":download [url] [dest] is deprecated - use download --dest [dest] [url]" should be shown.
        And the error "Can't give two destinations for the download." should be shown.

    Scenario: :download --mhtml with an URL given
        When I run :download --mhtml http://foobar/
        Then the error "Can only download the current page as mhtml." should be shown.

    Scenario: Downloading as mhtml is available
        When I open html
        And I run :download --mhtml
        And I wait for "File successfully written." in the log
        Then no crash should happen

    Scenario: Downloading as mhtml with non-ASCII headers
        When I open response-headers?Content-Type=text%2Fpl%C3%A4in
        And I run :download --mhtml --dest mhtml-response-headers.mht
        And I wait for "File successfully written." in the log
        Then no crash should happen
