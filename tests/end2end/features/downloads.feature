Feature: Downloading things from a website.

    Background:
        Given I set up a temporary download dir
        And I clean old downloads

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

    Scenario: Downloading a link without path information (issue 1243)
        When I set completion -> download-path-suggestion to filename
        And I set storage -> prompt-download-directory to true
        And I open data/downloads/issue1243.html
        And I run :hint links download
        And I run :follow-hint a
        And I wait for "Asking question <qutebrowser.utils.usertypes.Question default='qutebrowser-download' mode=<PromptMode.download: 5> text='Save file to:'>, *" in the log
        Then the error "Download error: No handler found for qute://!" should be shown

    Scenario: Downloading a data: link (issue 1214)
        When I set completion -> download-path-suggestion to filename
        And I set storage -> prompt-download-directory to true
        And I open data/downloads/issue1214.html
        And I run :hint links download
        And I run :follow-hint a
        And I wait for "Asking question <qutebrowser.utils.usertypes.Question default='binary blob' mode=<PromptMode.download: 5> text='Save file to:'>, *" in the log
        And I run :leave-mode
        Then no crash should happen

    Scenario: Downloading with SSL errors (issue 1413)
        When I run :debug-clear-ssl-errors
        And I set network -> ssl-strict to ask
        And I download an SSL page
        And I wait for "Entering mode KeyMode.* (reason: question asked)" in the log
        And I run :prompt-accept
        Then the error "Download error: SSL handshake failed" should be shown

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
        Then the error "No failed downloads!" should be shown

    Scenario: Retrying with no downloads
        When I run :download-retry
        Then the error "No failed downloads!" should be shown

    Scenario: :download with deprecated dest-old argument
        When I run :download http://localhost:(port)/ deprecated-argument
        Then the warning ":download [url] [dest] is deprecated - use download --dest [dest] [url]" should be shown

    Scenario: Two destinations given
        When I run :download --dest destination2 http://localhost:(port)/ destination1
        Then the warning ":download [url] [dest] is deprecated - use download --dest [dest] [url]" should be shown
        And the error "Can't give two destinations for the download." should be shown

    Scenario: :download --mhtml with a URL given
        When I run :download --mhtml http://foobar/
        Then the error "Can only download the current page as mhtml." should be shown

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

    ## :download-cancel

    Scenario: Cancelling a download
        When I run :download http://localhost:(port)/drip?numbytes=128&duration=5
        And I run :download-cancel
        Then "cancelled" should be logged

    Scenario: Cancelling a download which does not exist
        When I run :download-cancel with count 42
        Then the error "There's no download 42!" should be shown

    Scenario: Cancelling a download which is already done
        When I open data/downloads/download.bin
        And I wait until the download is finished
        And I run :download-cancel
        Then the error "Download 1 is already done!" should be shown

    Scenario: Cancelling a download which is already done (with count)
        When I open data/downloads/download.bin
        And I wait until the download is finished
        And I run :download-cancel with count 1
        Then the error "Download 1 is already done!" should be shown

    Scenario: Cancelling all downloads
        When I run :download http://localhost:(port)/drip?numbytes=128&duration=5
        And I run :download http://localhost:(port)/drip?numbytes=128&duration=5
        And I run :download-cancel --all
        Then "cancelled" should be logged
        And "cancelled" should be logged

    # https://github.com/The-Compiler/qutebrowser/issues/1535
    Scenario: Cancelling an MHTML download (issue 1535)
        When I open data/downloads/issue1535.html
        And I run :download --mhtml
        And I wait for "fetch: PyQt5.QtCore.QUrl('http://localhost:*/drip?numbytes=128&duration=2') -> drip" in the log
        And I run :download-cancel
        Then no crash should happen

    ## :download-delete

    Scenario: Deleting a download
        When I open data/downloads/download.bin
        And I wait until the download is finished
        And I run :download-delete
        And I wait for "deleted download *" in the log
        Then the downloaded file download.bin should not exist

    Scenario: Deleting a download which does not exist
        When I run :download-delete with count 42
        Then the error "There's no download 42!" should be shown

    Scenario: Deleting a download which is not done yet
        When I run :download http://localhost:(port)/drip?numbytes=128&duration=5
        And I run :download-delete
        Then the error "Download 1 is not done!" should be shown

    Scenario: Deleting a download which is not done yet (with count)
        When I run :download http://localhost:(port)/drip?numbytes=128&duration=5
        And I run :download-delete with count 1
        Then the error "Download 1 is not done!" should be shown

    ## :download-open

    # Scenario: Opening a download
    #     When I open data/downloads/download.bin
    #     And I wait until the download is finished
    #     And I run :download-open
    #     Then ...

    Scenario: Opening a download which does not exist
        When I run :download-open with count 42
        Then the error "There's no download 42!" should be shown

    Scenario: Opening a download which is not done yet
        When I run :download http://localhost:(port)/drip?numbytes=128&duration=5
        And I run :download-open
        Then the error "Download 1 is not done!" should be shown

    Scenario: Opening a download which is not done yet (with count)
        When I run :download http://localhost:(port)/drip?numbytes=128&duration=5
        And I run :download-open with count 1
        Then the error "Download 1 is not done!" should be shown

    ## completion -> download-path-suggestion

    Scenario: completion -> download-path-suggestion = path
        When I set storage -> prompt-download-directory to true
        And I set completion -> download-path-suggestion to path
        And I open data/downloads/download.bin
        Then the download prompt should be shown with "{downloaddir}/"

    Scenario: completion -> download-path-suggestion = filename
        When I set storage -> prompt-download-directory to true
        And I set completion -> download-path-suggestion to filename
        And I open data/downloads/download.bin
        Then the download prompt should be shown with "download.bin"

    Scenario: completion -> download-path-suggestion = both
        When I set storage -> prompt-download-directory to true
        And I set completion -> download-path-suggestion to both
        And I open data/downloads/download.bin
        Then the download prompt should be shown with "{downloaddir}/download.bin"

    ## https://github.com/The-Compiler/qutebrowser/issues/1242

    Scenario: Closing window with remove-finished-downloads timeout
        When I set ui -> remove-finished-downloads to 500
        And I open data/downloads/download.bin in a new window
        And I wait until the download is finished
        And I run :close
        And I wait 0.5s
        Then no crash should happen

    ## https://github.com/The-Compiler/qutebrowser/issues/846

    Scenario: Quitting with finished downloads and confirm-quit=downloads
        Given I have a fresh instance
        When I set storage -> prompt-download-directory to false
        And I set ui -> confirm-quit to downloads
        And I open data/downloads/download.bin
        And I wait until the download is finished
        And I run :close
        Then qutebrowser should quit
