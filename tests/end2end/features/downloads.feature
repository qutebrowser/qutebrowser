# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Downloading things from a website.

    Background:
        Given I set up a temporary download dir
        And I clean old downloads
        And I set downloads.remove_finished to -1

    ## starting downloads

    Scenario: Clicking an unknown link
        When I set downloads.location.prompt to false
        And I open data/downloads/downloads.html
        And I run :click-element id download
        And I wait until the download is finished
        Then the downloaded file download.bin should exist

    Scenario: Using :download
        When I set downloads.location.prompt to false
        When I run :download http://localhost:(port)/data/downloads/download.bin
        And I wait until the download is finished
        Then the downloaded file download.bin should exist

    Scenario: Using :download with no URL
        When I set downloads.location.prompt to false
        And I open data/downloads/downloads.html
        And I run :download
        And I wait until the download is finished
        Then the downloaded file Simple downloads.html should exist

    Scenario: Using :download with no URL on an image
        When I set downloads.location.prompt to false
        And I open data/downloads/qutebrowser.png
        And I run :download
        And I wait until the download is finished
        Then the downloaded file qutebrowser.png should exist

    Scenario: Using hints
        When I set downloads.location.prompt to false
        And I open data/downloads/downloads.html
        And I hint with args "links download" and follow a
        And I wait until the download is finished
        Then the downloaded file download.bin should exist

    Scenario: Using rapid hints
        # We don't expect any prompts with rapid hinting even if this is true
        When I set downloads.location.prompt to true
        And I open data/downloads/downloads.html
        And I hint with args "--rapid links download" and follow a
        And I run :hint-follow s
        And I wait until the download download.bin is finished
        And I wait until the download download2.bin is finished
        Then the downloaded file download.bin should exist
        Then the downloaded file download2.bin should exist

    ## Regression tests

    Scenario: Downloading which redirects with closed tab (issue 889)
        When I set tabs.last_close to blank
        And I open data/downloads/issue889.html
        And I hint with args "links download" and follow a
        And I run :tab-close
        And I wait for "* Handling redirect" in the log
        Then no crash should happen

    Scenario: Downloading with error in closed tab (issue 889)
        When I set tabs.last_close to blank
        And I open data/downloads/issue889.html
        And I hint with args "links download" and follow s
        And I run :tab-close
        And I wait for the error "Download error: * - server replied: NOT FOUND"
        And I run :download-retry
        And I wait for the error "Download error: * - server replied: NOT FOUND"
        Then no crash should happen

    Scenario: Downloading a link without path information (issue 1243)
        When I set downloads.location.suggestion to filename
        And I set downloads.location.prompt to true
        And I open data/downloads/issue1243.html
        And I hint with args "links download" and follow a
        And I wait for "Asking question <qutebrowser.utils.usertypes.Question default='qutebrowser-download' mode=<PromptMode.download: 5> option=None text=* title='Save file to:'>, *" in the log
        Then the error "Download error: No handler found for qute://" should be shown
        And "NotFoundError while handling qute://* URL" should be logged

    Scenario: Downloading a data: link (issue 1214)
        When I set downloads.location.suggestion to filename
        And I set downloads.location.prompt to true
        And I open data/data_link.html
        And I hint with args "links download" and follow s
        And I wait for "Asking question <qutebrowser.utils.usertypes.Question default='download.pdf' mode=<PromptMode.download: 5> option=None text=* title='Save file to:'>, *" in the log
        And I run :mode-leave
        Then no crash should happen

    Scenario: Aborting a download in a different window (issue 3378)
        When I set downloads.location.suggestion to filename
        And I set downloads.location.prompt to true
        And I open data/downloads/download.bin in a new window without waiting
        And I wait for "Asking question <qutebrowser.utils.usertypes.Question default='*' mode=<PromptMode.download: 5> *" in the log
        And I run :window-only
        And I run :mode-leave
        Then no crash should happen

    Scenario: Closing window with downloads.remove_finished timeout (issue 1242)
        When I set downloads.remove_finished to 500
        And I open data/downloads/download.bin in a new window without waiting
        And I wait until the download is finished
        And I run :close
        And I wait 0.5s
        Then no crash should happen

    Scenario: Quitting with finished downloads and confirm_quit=downloads (issue 846)
        Given I have a fresh instance
        When I set downloads.location.prompt to false
        And I set confirm_quit to [downloads]
        And I open data/downloads/download.bin without waiting
        And I wait until the download is finished
        And I run :close
        Then qutebrowser should quit

    # https://github.com/qutebrowser/qutebrowser/issues/2134
    @qtwebengine_skip
    Scenario: Downloading, then closing a tab
        When I set downloads.location.prompt to false
        And I open about:blank
        And I open data/downloads/issue2134.html in a new tab
        # This needs to be a download connected to the tabs QNAM
        And I hint with args "links normal" and follow a
        And I wait for "fetch: * -> drip" in the log
        And I run :tab-close
        And I wait for "Download drip finished" in the log
        Then the downloaded file drip should be 128 bytes big

    Scenario: Downloading a file with spaces
        When I open data/downloads/download with spaces.bin without waiting
        And I wait until the download is finished
        Then the downloaded file download with spaces.bin should exist

    @qtwebkit_skip @qt>=5.13
    Scenario: Downloading a file with evil content-disposition header (Qt 5.13 and newer)
        # Content-Disposition: download; filename=..%2Ffoo
        When I open response-headers?Content-Disposition=download;%20filename%3D..%252Ffoo without waiting
        And I wait until the download is finished
        Then the downloaded file ../foo should not exist
        And the downloaded file foo should exist

    @qtwebkit_skip @qt<5.13
    Scenario: Downloading a file with evil content-disposition header (Qt 5.12)
        # Content-Disposition: download; filename=..%2Ffoo
        When I open response-headers?Content-Disposition=download;%20filename%3D..%252Ffoo without waiting
        And I wait until the download is finished
        Then the downloaded file ../foo should not exist
        And the downloaded file ..%2Ffoo should exist

    @qtwebkit_skip @qt>=5.13
    Scenario: Downloading a file with evil content-disposition header (Qt 5.13 or newer)
        # Content-Disposition: download; filename=..%252Ffoo
        When I open response-headers?Content-Disposition=download;%20filename%3D..%25252Ffoo without waiting
        And I wait until the download is finished
        Then the downloaded file ../foo should not exist
        And the downloaded file ..%2Ffoo should exist

    @windows
    Scenario: Downloading a file to a reserved path
        When I set downloads.location.prompt to true
        And I open data/downloads/download.bin without waiting
        And I wait for "Asking question <qutebrowser.utils.usertypes.Question default='*' mode=<PromptMode.download: 5> option=None text='Please enter a location for <b>http://localhost:*/data/downloads/download.bin</b>' title='Save file to:'>, *" in the log
        And I run :prompt-accept COM1
        And I run :mode-leave
        Then the error "Invalid filename" should be shown

    @windows
    Scenario: Downloading a file to a drive-relative working directory
        When I set downloads.location.prompt to true
        And I open data/downloads/download.bin without waiting
        And I wait for "Asking question <qutebrowser.utils.usertypes.Question default='*' mode=<PromptMode.download: 5> option=None text='Please enter a location for <b>http://localhost:*/data/downloads/download.bin</b>' title='Save file to:'>, *" in the log
        And I run :prompt-accept C:foobar
        And I run :mode-leave
        Then the error "Invalid filename" should be shown

    @windows
    Scenario: Downloading a file to a reserved path with :download
        When I run :download data/downloads/download.bin --dest=COM1
        Then the error "Invalid target filename" should be shown

    @windows
    Scenario: Download a file to a drive-relative working directory with :download
        When I run :download data/downloads/download.bin --dest=C:foobar
        Then the error "Invalid target filename" should be shown

    ## :download-retry

    Scenario: Retrying a failed download
        When I run :download http://localhost:(port)/does-not-exist
        And I wait for the error "Download error: * - server replied: NOT FOUND"
        And I run :download-retry
        And I wait for the error "Download error: * - server replied: NOT FOUND"
        Then the requests should be:
            does-not-exist
            does-not-exist

    @flaky
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

    Scenario: :download --mhtml with a URL given
        When I run :download --mhtml http://foobar/
        Then the error "Can only download the current page as mhtml." should be shown

    Scenario: :download with a filename and directory which doesn't exist
        When I run :download --dest (tmpdir)(dirsep)downloads(dirsep)somedir(dirsep)file http://localhost:(port)/data/downloads/download.bin
        And I wait for "Asking question <qutebrowser.utils.usertypes.Question default=None mode=<PromptMode.yesno: 1> option=None text='<b>*</b> does not exist. Create it?' title='Create directory?'>, *" in the log
        And I run :prompt-accept yes
        And I wait until the download is finished
        Then the downloaded file somedir/file should exist

    Scenario: :download with a directory which doesn't exist
        When I run :download --dest (tmpdir)(dirsep)downloads(dirsep)somedir(dirsep) http://localhost:(port)/data/downloads/download.bin
        And I wait for "Asking question <qutebrowser.utils.usertypes.Question default=None mode=<PromptMode.yesno: 1> option=None text='<b>*</b> does not exist. Create it?' title='Create directory?'>, *" in the log
        And I run :prompt-accept yes
        And I wait until the download is finished
        Then the downloaded file somedir/download.bin should exist

    ## mhtml downloads

    Scenario: Downloading as mhtml is available
        When I open data/title.html
        And I run :download --mhtml
        And I wait for "File successfully written." in the log
        Then the downloaded file Test title.mhtml should exist

    @qtwebengine_skip: QtWebEngine refuses to load this
    Scenario: Downloading as mhtml with non-ASCII headers
        When I open response-headers?Content-Type=text%2Fpl%C3%A4in
        And I run :download --mhtml --dest mhtml-response-headers.mhtml
        And I wait for "File successfully written." in the log
        Then the downloaded file mhtml-response-headers.mhtml should exist

    @qtwebengine_skip: https://github.com/qutebrowser/qutebrowser/issues/2288
    Scenario: Overwriting existing mhtml file
        When I set downloads.location.prompt to true
        And I open data/title.html
        And I run :download --mhtml
        And I wait for "Asking question <qutebrowser.utils.usertypes.Question default='*' mode=<PromptMode.download: 5> option=None text='Please enter a location for <b>http://localhost:*/data/title.html</b>' title='Save file to:'>, *" in the log
        And I run :prompt-accept
        And I wait for "File successfully written." in the log
        And I run :download --mhtml
        And I wait for "Asking question <qutebrowser.utils.usertypes.Question default='*' mode=<PromptMode.download: 5> option=None text='Please enter a location for <b>http://localhost:*/data/title.html</b>' title='Save file to:'>, *" in the log
        And I run :prompt-accept
        And I wait for "Asking question <qutebrowser.utils.usertypes.Question default=None mode=<PromptMode.yesno: 1> option=None text='<b>*</b> already exists. Overwrite?' title='Overwrite existing file?'>, *" in the log
        And I run :prompt-accept yes
        And I wait for "File successfully written." in the log
        Then the downloaded file Test title.mhtml should exist

    @not_flatpak
    Scenario: Opening a mhtml download directly
        When I set downloads.location.prompt to true
        And I open /
        And I run :download --mhtml
        And I wait for the download prompt for "*"
        And I directly open the download
        Then "Opening *.mhtml* with [*python*]" should be logged

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
        When I open data/downloads/download.bin without waiting
        And I wait until the download is finished
        And I run :download-cancel
        Then the error "Download 1 is already done!" should be shown

    Scenario: Cancelling a download which is already done (with count)
        When I open data/downloads/download.bin without waiting
        And I wait until the download is finished
        And I run :download-cancel with count 1
        Then the error "Download 1 is already done!" should be shown

    Scenario: Cancelling all downloads
        When I run :download http://localhost:(port)/drip?numbytes=128&duration=5
        And I run :download http://localhost:(port)/drip?numbytes=128&duration=5
        And I run :download-cancel --all
        Then "cancelled" should be logged
        And "cancelled" should be logged

    # https://github.com/qutebrowser/qutebrowser/issues/1535
    @qtwebengine_todo: :download --mhtml is not implemented yet
    Scenario: Cancelling an MHTML download (issue 1535)
        When I open data/downloads/issue1535.html
        And I run :download --mhtml
        And I wait for "fetch: PyQt5.QtCore.QUrl('http://localhost:*/drip?numbytes=128&duration=2') -> drip" in the log
        And I run :download-cancel
        Then no crash should happen

    ## :download-remove / :download-clear

    Scenario: Removing a download
        When I open data/downloads/download.bin without waiting
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
        When I open data/downloads/download.bin without waiting
        And I wait until the download is finished
        And I open data/downloads/download2.bin without waiting
        And I wait until the download is finished
        And I run :download-remove --all
        Then "Removed download *" should be logged

    Scenario: Removing all downloads via :download-clear
        When I open data/downloads/download.bin without waiting
        And I wait until the download is finished
        And I open data/downloads/download2.bin without waiting
        And I wait until the download is finished
        And I run :download-clear
        Then "Removed download *" should be logged

    ## :download-delete

    Scenario: Deleting a download
        When I open data/downloads/download.bin without waiting
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

    @not_flatpak
    Scenario: Opening a download
        When I open data/downloads/download.bin without waiting
        And I wait until the download is finished
        And I open the download
        Then "Opening *download.bin* with [*python*]" should be logged

    @not_flatpak
    Scenario: Opening a download with a placeholder
        When I open data/downloads/download.bin without waiting
        And I wait until the download is finished
        And I open the download with a placeholder
        Then "Opening *download.bin* with [*python*]" should be logged

    @not_flatpak
    Scenario: Opening a download with open_dispatcher set
        When I set a test python open_dispatcher
        And I open data/downloads/download.bin without waiting
        And I wait until the download is finished
        And I run :download-open
        Then "Opening *download.bin* with [*python*]" should be logged

    @not_flatpak
    Scenario: Opening a download with open_dispatcher set and override
        When I set downloads.open_dispatcher to cat
        And I open data/downloads/download.bin without waiting
        And I wait until the download is finished
        And I open the download
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

    @not_flatpak
    Scenario: Opening a download directly
        When I set downloads.location.prompt to true
        And I open data/downloads/download.bin without waiting
        And I wait for the download prompt for "*"
        And I directly open the download
        And I wait until the download is finished
        Then "Opening *download.bin* with [*python*]" should be logged

    # https://github.com/qutebrowser/qutebrowser/issues/1728

    Scenario: Cancelling a download that should be opened
        When I set downloads.location.prompt to true
        And I run :download http://localhost:(port)/drip?numbytes=128&duration=5
        And I wait for the download prompt for "*"
        And I directly open the download
        And I run :download-cancel
        Then "* finished but not successful, not opening!" should be logged

    # https://github.com/qutebrowser/qutebrowser/issues/1725

    @not_flatpak
    Scenario: Directly open a download with a very long filename
        When I set downloads.location.prompt to true
        And I open data/downloads/issue1725.html
        And I run :click-element id long-link
        And I wait for the download prompt for "*"
        And I directly open the download
        And I wait until the download is finished
        Then "Opening * with [*python*]" should be logged

    ## downloads.location.suggestion

    Scenario: downloads.location.suggestion = path
        When I set downloads.location.prompt to true
        And I set downloads.location.suggestion to path
        And I open data/downloads/download.bin without waiting
        Then the download prompt should be shown with "(tmpdir)/downloads/"

    Scenario: downloads.location.suggestion = filename
        When I set downloads.location.prompt to true
        And I set downloads.location.suggestion to filename
        And I open data/downloads/download.bin without waiting
        Then the download prompt should be shown with "download.bin"

    Scenario: downloads.location.suggestion = both
        When I set downloads.location.prompt to true
        And I set downloads.location.suggestion to both
        And I open data/downloads/download.bin without waiting
        Then the download prompt should be shown with "(tmpdir)/downloads/download.bin"

    ## downloads.location.remember

    Scenario: Remembering the last download directory
        When I set downloads.location.prompt to true
        And I set downloads.location.suggestion to both
        And I set downloads.location.remember to true
        And I open data/downloads/download.bin without waiting
        And I wait for the download prompt for "*/download.bin"
        And I run :prompt-accept (tmpdir)(dirsep)downloads(dirsep)subdir
        And I open data/downloads/download2.bin without waiting
        Then the download prompt should be shown with "(tmpdir)/downloads/subdir/download2.bin"

    Scenario: Clearing the last download directory when changing download location
        When I set downloads.location.prompt to true
        And I set downloads.location.suggestion to both
        And I set downloads.location.remember to true
        And I open data/downloads/download.bin without waiting
        And I wait for the download prompt for "*/download.bin"
        And I run :prompt-accept (tmpdir)(dirsep)downloads(dirsep)subdir
        And I run :set downloads.location.directory (tmpdir)(dirsep)downloads
        And I open data/downloads/download2.bin without waiting
        Then the download prompt should be shown with "(tmpdir)/downloads/download2.bin"

    Scenario: Not remembering the last download directory
        When I set downloads.location.prompt to true
        And I set downloads.location.suggestion to both
        And I set downloads.location.remember to false
        And I open data/downloads/download.bin without waiting
        And I wait for the download prompt for "(tmpdir)/downloads/download.bin"
        And I run :prompt-accept (tmpdir)(dirsep)downloads(dirsep)subdir
        And I open data/downloads/download2.bin without waiting
        Then the download prompt should be shown with "(tmpdir)/downloads/download2.bin"

    # https://github.com/qutebrowser/qutebrowser/issues/2173

    @not_flatpak
    Scenario: Remembering the temporary download directory (issue 2173)
        When I set downloads.location.prompt to true
        And I set downloads.location.suggestion to both
        And I set downloads.location.remember to true
        And I open data/downloads/download.bin without waiting
        And I wait for the download prompt for "*"
        And I run :prompt-accept (tmpdir)(dirsep)downloads
        And I open data/downloads/download2.bin without waiting
        And I wait for the download prompt for "*"
        And I directly open the download
        And I open data/downloads/download.bin without waiting
        Then the download prompt should be shown with "(tmpdir)/downloads/download.bin"

    # Overwriting files

    Scenario: Not overwriting an existing file
        When I set downloads.location.prompt to false
        And I run :download http://localhost:(port)/data/downloads/download.bin
        And I wait until the download is finished
        And I run :download http://localhost:(port)/data/downloads/download2.bin --dest download.bin
        And I wait for "Entering mode KeyMode.yesno *" in the log
        And I run :prompt-accept no
        Then the downloaded file download.bin should be 1 bytes big

    Scenario: Overwriting an existing file
        When I set downloads.location.prompt to false
        And I run :download http://localhost:(port)/data/downloads/download.bin
        And I wait until the download is finished
        And I run :download http://localhost:(port)/data/downloads/download2.bin --dest download.bin
        And I wait for "Entering mode KeyMode.yesno *" in the log
        And I run :prompt-accept yes
        And I wait until the download is finished
        Then the downloaded file download.bin should be 2 bytes big

    @linux
    Scenario: Not overwriting a special file
        When I set downloads.location.prompt to false
        And I run :download http://localhost:(port)/data/downloads/download.bin --dest fifo
        And I wait for "Entering mode KeyMode.yesno *" in the log
        And I run :prompt-accept no
        Then the FIFO should still be a FIFO

    ## Redirects

    Scenario: Downloading with infinite redirect
        When I set downloads.location.prompt to false
        And I run :download http://localhost:(port)/redirect/12 --dest redirection
        Then the error "Download error: Maximum redirection count reached!" should be shown
        And "Deleted *redirection" should be logged
        And the downloaded file redirection should not exist

    Scenario: Downloading with redirect to itself
        When I set downloads.location.prompt to false
        And I run :download http://localhost:(port)/redirect-self
        And I wait until the download is finished
        Then the downloaded file redirect-self should exist

    Scenario: Downloading with absolute redirect
        When I set downloads.location.prompt to false
        And I run :download http://localhost:(port)/absolute-redirect
        And I wait until the download is finished
        Then the downloaded file absolute-redirect should exist

    Scenario: Downloading with relative redirect
        When I set downloads.location.prompt to false
        And I run :download http://localhost:(port)/relative-redirect
        And I wait until the download is finished
        Then the downloaded file relative-redirect should exist

    ## Other

    Scenario: Download without a content-size
        When I set downloads.location.prompt to false
        When I run :download http://localhost:(port)/content-size
        And I wait until the download is finished
        Then the downloaded file content-size should exist

    Scenario: Downloading to unwritable destination
        When the unwritable dir is unwritable
        And I set downloads.location.prompt to false
        And I run :download http://localhost:(port)/data/downloads/download.bin --dest (tmpdir)/downloads/unwritable
        Then the error "Download error: *" should be shown

    Scenario: Downloading 20MB file
        When I set downloads.location.prompt to false
        And I run :download http://localhost:(port)/twenty-mb
        And I wait until the download is finished
        Then the downloaded file twenty-mb should be 20971520 bytes big

    Scenario: Downloading 20MB file with late prompt confirmation
        When I set downloads.location.prompt to true
        And I run :download http://localhost:(port)/twenty-mb
        And I wait 1s
        And I run :prompt-accept
        And I wait until the download is finished
        Then the downloaded file twenty-mb should be 20971520 bytes big

    Scenario: Downloading invalid URL
        When I set downloads.location.prompt to false
        And I set url.auto_search to never
        And I run :download foo!
        Then the error "Invalid URL" should be shown

    Scenario: Downloading via pdfjs
        Given pdfjs is available
        When I set downloads.location.prompt to false
        And I set content.pdfjs to true
        And I open data/misc/test.pdf without waiting
        And I wait for the javascript message "PDF * [*] (PDF.js: *)"
        And I run :click-element id download
        And I wait until the download is finished
        # We get viewer.html as name on QtWebKit...
        # Then the downloaded file test.pdf should exist

    Scenario: Answering a question for a cancelled download (#415)
        When I set downloads.location.prompt to true
        And I run :download http://localhost:(port)/data/downloads/download.bin
        And I wait for "Asking question <qutebrowser.utils.usertypes.Question default='*' mode=<PromptMode.download: 5> option=None text=* title='Save file to:'>, *" in the log
        And I run :download http://localhost:(port)/data/downloads/download2.bin
        And I wait for "Asking question <qutebrowser.utils.usertypes.Question default='*' mode=<PromptMode.download: 5> option=None text=* title='Save file to:'>, *" in the log
        And I run :download-cancel with count 2
        And I run :prompt-accept
        And I wait until the download is finished
        Then the downloaded file download.bin should exist
        And the downloaded file download2.bin should not exist

    @qtwebengine_skip: We can't get the UA from the page there
    Scenario: user-agent when using :download
        When I open user-agent
        And I run :download --dest user-agent
        And I wait until the download is finished
        Then the downloaded file user-agent should contain Safari/

    @qtwebengine_skip: We can't get the UA from the page there
    Scenario: user-agent when using hints
        When I open /
        And I run :hint links download
        And I run :hint-follow a
        And I wait until the download is finished
        Then the downloaded file user-agent should contain Safari/

    @qtwebengine_skip: Handled by QtWebEngine, not by us
    Scenario: Downloading a "Internal server error" with disposition: inline (#2304)
        When I set downloads.location.prompt to false
        And I open 500-inline
        Then the error "Download error: *INTERNAL SERVER ERROR" should be shown
