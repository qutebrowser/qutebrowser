Feature: Downloading things from a website.

    Background:
        Given I set up a temporary download dir
        And I clean old downloads
        And I set ui -> remove-finished-downloads to -1

    ## starting downloads

    Scenario: Clicking an unknown link
        When I set storage -> prompt-download-directory to false
        And I open data/downloads/downloads.html
        And I run :click-element id download
        And I wait until the download is finished
        Then the downloaded file download.bin should exist

    Scenario: Using :download
        When I set storage -> prompt-download-directory to false
        When I run :download http://localhost:(port)/data/downloads/download.bin
        And I wait until the download is finished
        Then the downloaded file download.bin should exist

    Scenario: Using hints
        When I set storage -> prompt-download-directory to false
        And I open data/downloads/downloads.html
        And I hint with args "links download" and follow a
        And I wait until the download is finished
        Then the downloaded file download.bin should exist

    Scenario: Using rapid hints
        # We don't expect any prompts with rapid hinting even if this is true
        When I set storage -> prompt-download-directory to true
        And I open data/downloads/downloads.html
        And I hint with args "--rapid links download" and follow a
        And I run :follow-hint s
        And I wait until the download download.bin is finished
        And I wait until the download download2.bin is finished
        Then the downloaded file download.bin should exist
        Then the downloaded file download2.bin should exist

    ## Regression tests

    Scenario: Downloading which redirects with closed tab (issue 889)
        When I set tabs -> last-close to blank
        And I open data/downloads/issue889.html
        And I hint with args "links download" and follow a
        And I run :tab-close
        And I wait for "* Handling redirect" in the log
        Then no crash should happen

    Scenario: Downloading with error in closed tab (issue 889)
        When I set tabs -> last-close to blank
        And I open data/downloads/issue889.html
        And I hint with args "links download" and follow s
        And I run :tab-close
        And I wait for the error "Download error: * - server replied: NOT FOUND"
        And I run :download-retry
        And I wait for the error "Download error: * - server replied: NOT FOUND"
        Then no crash should happen

    Scenario: Downloading a link without path information (issue 1243)
        When I set completion -> download-path-suggestion to filename
        And I set storage -> prompt-download-directory to true
        And I open data/downloads/issue1243.html
        And I hint with args "links download" and follow a
        And I wait for "Asking question <qutebrowser.utils.usertypes.Question default='qutebrowser-download' mode=<PromptMode.download: 5> text='Save file to:'>, *" in the log
        Then the error "Download error: No handler found for qute://!" should be shown

    Scenario: Downloading a data: link (issue 1214)
        When I set completion -> download-path-suggestion to filename
        And I set storage -> prompt-download-directory to true
        And I open data/downloads/issue1214.html
        And I hint with args "links download" and follow a
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

    Scenario: Closing window with remove-finished-downloads timeout (issue 1242)
        When I set ui -> remove-finished-downloads to 500
        And I open data/downloads/download.bin in a new window
        And I wait until the download is finished
        And I run :close
        And I wait 0.5s
        Then no crash should happen

    Scenario: Quitting with finished downloads and confirm-quit=downloads (issue 846)
        Given I have a fresh instance
        When I set storage -> prompt-download-directory to false
        And I set ui -> confirm-quit to downloads
        And I open data/downloads/download.bin
        And I wait until the download is finished
        And I run :close
        Then qutebrowser should quit

    ## :download-retry

    Scenario: Retrying a failed download
        When I run :download http://localhost:(port)/does-not-exist
        And I wait for the error "Download error: * - server replied: NOT FOUND"
        And I run :download-retry
        And I wait for the error "Download error: * - server replied: NOT FOUND"
        Then the requests should be:
            does-not-exist
            does-not-exist

    Scenario: Retrying with count
        When I run :download http://localhost:(port)/data/downloads/download.bin
        And I run :download http://localhost:(port)/does-not-exist
        And I wait for the error "Download error: * - server replied: NOT FOUND"
        And I run :download-retry with count 2
        And I wait for the error "Download error: * - server replied: NOT FOUND"
        Then the requests should be:
            data/downloads/download.bin
            does-not-exist
            does-not-exist

    Scenario: Retrying with two failed downloads
        When I run :download http://localhost:(port)/does-not-exist
        And I run :download http://localhost:(port)/does-not-exist-2
        And I wait for the error "Download error: * - server replied: NOT FOUND"
        And I wait for the error "Download error: * - server replied: NOT FOUND"
        And I run :download-retry
        And I wait for the error "Download error: * - server replied: NOT FOUND"
        Then the requests should be:
            does-not-exist
            does-not-exist-2
            does-not-exist

    Scenario: Retrying a download which does not exist
        When I run :download-retry with count 42
        Then the error "There's no download 42!" should be shown

    Scenario: Retrying a download which did not fail
        When I run :download http://localhost:(port)/data/downloads/download.bin
        And I wait until the download is finished
        And I run :download-retry with count 1
        Then the error "Download 1 did not fail!" should be shown

    Scenario: Retrying a download with no failed ones
        When I run :download http://localhost:(port)/data/downloads/download.bin
        And I wait until the download is finished
        And I run :download-retry
        Then the error "No failed downloads!" should be shown

    ## Wrong invocations

    Scenario: :download with deprecated dest-old argument
        When I run :download http://localhost:(port)/ deprecated-argument
        Then the warning ":download [url] [dest] is deprecated - use :download --dest [dest] [url]" should be shown

    Scenario: Two destinations given
        When I run :download --dest destination2 http://localhost:(port)/ destination1
        Then the warning ":download [url] [dest] is deprecated - use :download --dest [dest] [url]" should be shown
        And the error "Can't give two destinations for the download." should be shown

    Scenario: :download --mhtml with a URL given
        When I run :download --mhtml http://foobar/
        Then the error "Can only download the current page as mhtml." should be shown

    Scenario: :download with a directory which doesn't exist
        When I run :download --dest (tmpdir)/somedir/filename http://localhost:(port)/
        Then the error "Download error: No such file or directory" should be shown

    ## mhtml downloads

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

    Scenario: Cancelling with no download and no ID
        When I run :download-cancel
        Then the error "There's no download!" should be shown

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

    ## :download-remove / :download-clear

    Scenario: Removing a download
        When I open data/downloads/download.bin
        And I wait until the download is finished
        And I run :download-remove
        Then "Removed download *" should be logged

    Scenario: Removing a download which does not exist
        When I run :download-remove with count 42
        Then the error "There's no download 42!" should be shown

    Scenario: Removing a download which is not done yet
        When I run :download http://localhost:(port)/drip?numbytes=128&duration=5
        And I run :download-remove
        Then the error "Download 1 is not done!" should be shown

    Scenario: Removing a download which is not done yet (with count)
        When I run :download http://localhost:(port)/drip?numbytes=128&duration=5
        And I run :download-remove with count 1
        Then the error "Download 1 is not done!" should be shown

    Scenario: Removing all downloads via :download-remove
        When I open data/downloads/download.bin
        And I wait until the download is finished
        And I open data/downloads/download2.bin
        And I wait until the download is finished
        And I run :download-remove --all
        Then "Removed download *" should be logged

    Scenario: Removing all downloads via :download-clear
        When I open data/downloads/download.bin
        And I wait until the download is finished
        And I open data/downloads/download2.bin
        And I wait until the download is finished
        And I run :download-clear
        Then "Removed download *" should be logged

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

    Scenario: Opening a download
        When I open data/downloads/download.bin
        And I wait until the download is finished
        And I open the download
        Then "Opening *download.bin* with [*python*]" should be logged

    Scenario: Opening a download with a placeholder
        When I open data/downloads/download.bin
        And I wait until the download is finished
        And I open the download with a placeholder
        Then "Opening *download.bin* with [*python*]" should be logged

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

    ## opening a file directly (prompt-open-download)

    Scenario: Opening a download directly
        When I set storage -> prompt-download-directory to true
        And I open data/downloads/download.bin
        And I directly open the download
        And I wait until the download is finished
        Then "Opening *download.bin* with [*python*]" should be logged

    # https://github.com/The-Compiler/qutebrowser/issues/1728

    Scenario: Cancelling a download that should be opened
        When I set storage -> prompt-download-directory to true
        And I run :download http://localhost:(port)/drip?numbytes=128&duration=5
        And I directly open the download
        And I run :download-cancel
        Then "* finished but not successful, not opening!" should be logged

    # https://github.com/The-Compiler/qutebrowser/issues/1725

    Scenario: Directly open a download with a very long filename
        When I set storage -> prompt-download-directory to true
        And I open data/downloads/issue1725.html
        And I run :click-element id long-link
        And I wait for "Asking question <qutebrowser.utils.usertypes.Question default=* mode=<PromptMode.download: 5> text='Save file to:'>, *" in the log
        And I directly open the download
        And I wait until the download is finished
        Then "Opening * with [*python*]" should be logged

    ## completion -> download-path-suggestion

    Scenario: completion -> download-path-suggestion = path
        When I set storage -> prompt-download-directory to true
        And I set completion -> download-path-suggestion to path
        And I open data/downloads/download.bin
        Then the download prompt should be shown with "(tmpdir)/"

    Scenario: completion -> download-path-suggestion = filename
        When I set storage -> prompt-download-directory to true
        And I set completion -> download-path-suggestion to filename
        And I open data/downloads/download.bin
        Then the download prompt should be shown with "download.bin"

    Scenario: completion -> download-path-suggestion = both
        When I set storage -> prompt-download-directory to true
        And I set completion -> download-path-suggestion to both
        And I open data/downloads/download.bin
        Then the download prompt should be shown with "(tmpdir)/download.bin"

    ## storage -> remember-download-directory

    Scenario: Remembering the last download directory
        When I set storage -> prompt-download-directory to true
        And I set completion -> download-path-suggestion to both
        And I set storage -> remember-download-directory to true
        And I open data/downloads/download.bin
        And I wait for the download prompt for "*/download.bin"
        And I run :prompt-accept (tmpdir)(dirsep)subdir
        And I open data/downloads/download2.bin
        Then the download prompt should be shown with "(tmpdir)/subdir/download2.bin"

    Scenario: Not remembering the last download directory
        When I set storage -> prompt-download-directory to true
        And I set completion -> download-path-suggestion to both
        And I set storage -> remember-download-directory to false
        And I open data/downloads/download.bin
        And I wait for the download prompt for "(tmpdir)/download.bin"
        And I run :prompt-accept (tmpdir)(dirsep)subdir
        And I open data/downloads/download2.bin
        Then the download prompt should be shown with "(tmpdir)/download2.bin"

    # Overwriting files

    Scenario: Not overwriting an existing file
        When I set storage -> prompt-download-directory to false
        And I run :download http://localhost:(port)/data/downloads/download.bin
        And I wait until the download is finished
        And I run :download http://localhost:(port)/data/downloads/download2.bin --dest download.bin
        And I wait for "Entering mode KeyMode.yesno *" in the log
        And I run :prompt-accept no
        Then the downloaded file download.bin should contain 1 bytes

    Scenario: Overwriting an existing file
        When I set storage -> prompt-download-directory to false
        And I run :download http://localhost:(port)/data/downloads/download.bin
        And I wait until the download is finished
        And I run :download http://localhost:(port)/data/downloads/download2.bin --dest download.bin
        And I wait for "Entering mode KeyMode.yesno *" in the log
        And I run :prompt-accept yes
        And I wait until the download is finished
        Then the downloaded file download.bin should contain 2 bytes

    @linux
    Scenario: Not overwriting a special file
        When I set storage -> prompt-download-directory to false
        And I run :download http://localhost:(port)/data/downloads/download.bin --dest fifo
        And I wait for "Entering mode KeyMode.yesno *" in the log
        And I run :prompt-accept no
        Then the FIFO should still be a FIFO

    ## Redirects

    Scenario: Downloading with infinite redirect
        When I set storage -> prompt-download-directory to false
        And I run :download http://localhost:(port)/redirect/12 --dest redirection
        Then the error "Download error: Maximum redirection count reached!" should be shown
        And "Deleted *redirection" should be logged
        And the downloaded file redirection should not exist

    Scenario: Downloading with redirect to itself
        When I set storage -> prompt-download-directory to false
        And I run :download http://localhost:(port)/custom/redirect-self
        And I wait until the download is finished
        Then the downloaded file redirect-self should exist

    Scenario: Downloading with absolute redirect
        When I set storage -> prompt-download-directory to false
        And I run :download http://localhost:(port)/absolute-redirect/1
        And I wait until the download is finished
        Then the downloaded file 1 should exist

    Scenario: Downloading with relative redirect
        When I set storage -> prompt-download-directory to false
        And I run :download http://localhost:(port)/relative-redirect/1
        And I wait until the download is finished
        Then the downloaded file 1 should exist

    ## Other

    Scenario: Download without a content-size
        When I set storage -> prompt-download-directory to false
        When I run :download http://localhost:(port)/custom/content-size
        And I wait until the download is finished
        Then the downloaded file content-size should exist

    @posix
    Scenario: Downloading to unwritable destination
        When I set storage -> prompt-download-directory to false
        And I run :download http://localhost:(port)/data/downloads/download.bin --dest (tmpdir)/unwritable
        Then the error "Download error: Permission denied" should be shown

    Scenario: Downloading 20MB file
        When I set storage -> prompt-download-directory to false
        And I run :download http://localhost:(port)/custom/twenty-mb
        And I wait until the download is finished
        Then the downloaded file twenty-mb should contain 20971520 bytes

    Scenario: Downloading 20MB file with late prompt confirmation
        When I set storage -> prompt-download-directory to true
        And I run :download http://localhost:(port)/custom/twenty-mb
        And I wait 1s
        And I run :prompt-accept
        And I wait until the download is finished
        Then the downloaded file twenty-mb should contain 20971520 bytes

    Scenario: Downloading invalid URL
        When I set storage -> prompt-download-directory to false
        And I set general -> auto-search to false
        And I run :download foo!
        Then the error "Invalid URL" should be shown

    Scenario: Downloading via pdfjs
        Given pdfjs is available
        When I set storage -> prompt-download-directory to false
        And I set content -> enable-pdfjs to true
        And I open data/misc/test.pdf
        And I wait for the javascript message "PDF * [*] (PDF.js: *)"
        And I run :click-element id download
        And I wait until the download is finished
        Then the downloaded file test.pdf should exist
