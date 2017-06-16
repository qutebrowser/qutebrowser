# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Various utility commands.

    ## :set-cmd-text

    Scenario: :set-cmd-text and :command-accept
        When I run :set-cmd-text :message-info "Hello World"
        And I run :command-accept
        Then the message "Hello World" should be shown

    Scenario: :set-cmd-text with two commands
        When I run :set-cmd-text :message-info test ;; message-error error
        And I run :command-accept
        Then the message "test" should be shown
        And the error "error" should be shown

    Scenario: :set-cmd-text with URL replacement
        When I open data/hello.txt
        And I run :set-cmd-text :message-info {url}
        And I run :command-accept
        Then the message "http://localhost:*/hello.txt" should be shown

    Scenario: :set-cmd-text with URL replacement with encoded spaces
        When I open data/title with spaces.html
        And I run :set-cmd-text :message-info {url}
        And I run :command-accept
        Then the message "http://localhost:*/title%20with%20spaces.html" should be shown

    Scenario: :set-cmd-text with URL replacement with decoded spaces
        When I open data/title with spaces.html
        And I run :set-cmd-text :message-info "> {url:pretty} <"
        And I run :command-accept
        Then the message "> http://localhost:*/title with spaces.html <" should be shown

    Scenario: :set-cmd-text with -s and -a
        When I run :set-cmd-text -s :message-info "foo
        And I run :set-cmd-text -a bar"
        And I run :command-accept
        Then the message "foo bar" should be shown

    Scenario: :set-cmd-text with -a but without text
        When I run :set-cmd-text -a foo
        Then the error "No current text!" should be shown

    Scenario: :set-cmd-text with invalid command
        When I run :set-cmd-text foo
        Then the error "Invalid command text 'foo'." should be shown

    ## :jseval

    Scenario: :jseval
        When I set content.javascript.log to info
        And I run :jseval console.log("Hello from JS!");
        And I wait for the javascript message "Hello from JS!"
        Then the message "No output or error" should be shown

    Scenario: :jseval without logging
        When I set content.javascript.log to none
        And I run :jseval console.log("Hello from JS!");
        Then the message "No output or error" should be shown
        And "[:*] Hello from JS!" should not be logged

    Scenario: :jseval with --quiet
        When I set content.javascript.log to info
        And I run :jseval --quiet console.log("Hello from JS!");
        And I wait for the javascript message "Hello from JS!"
        Then "No output or error" should not be logged

    Scenario: :jseval with a value
        When I run :jseval "foo"
        Then the message "foo" should be shown

    Scenario: :jseval with a long, truncated value
        When I run :jseval Array(5002).join("x")
        Then the message "x* [...trimmed...]" should be shown

    @qtwebengine_skip
    Scenario: :jseval with --world on QtWebKit
        When I set content.javascript.log to info
        And I run :jseval --world=1 console.log("Hello from JS!");
        And I wait for the javascript message "Hello from JS!"
        Then "Ignoring world ID 1" should be logged
        And "No output or error" should be logged

    @qtwebkit_skip
    Scenario: :jseval uses separate world without --world
        When I set content.javascript.log to info
        And I open data/misc/jseval.html
        And I run :jseval do_log()
        Then the javascript message "Hello from the page!" should not be logged
        And the javascript message "Uncaught ReferenceError: do_log is not defined" should be logged
        And "No output or error" should be logged

    @qtwebkit_skip
    Scenario: :jseval using the main world
        When I set content.javascript.log to info
        And I open data/misc/jseval.html
        And I run :jseval --world 0 do_log()
        Then the javascript message "Hello from the page!" should be logged
        And "No output or error" should be logged

    @qtwebkit_skip
    Scenario: :jseval using the main world as name
        When I set content.javascript.log to info
        And I open data/misc/jseval.html
        And I run :jseval --world main do_log()
        Then the javascript message "Hello from the page!" should be logged
        And "No output or error" should be logged

    Scenario: :jseval --file using a file that exists as js-code
        When I set content.javascript.log to info
        And I run :jseval --file (testdata)/misc/jseval_file.js
        Then the javascript message "Hello from JS!" should be logged
        And the javascript message "Hello again from JS!" should be logged
        And "No output or error" should be logged

    Scenario: :jseval --file using a file that doesn't exist as js-code
        When I run :jseval --file nonexistentfile
        Then the error "[Errno 2] No such file or directory: 'nonexistentfile'" should be shown
        And "No output or error" should not be logged

    # :debug-webaction

    Scenario: :debug-webaction with valid value
        Given I open data/backforward/1.txt
        When I open data/backforward/2.txt
        And I run :tab-only
        And I run :debug-webaction Back
        And I wait until data/backforward/1.txt is loaded
        Then the session should look like:
            windows:
            - tabs:
              - history:
                - active: true
                  url: http://localhost:*/data/backforward/1.txt
                - url: http://localhost:*/data/backforward/2.txt

    Scenario: :debug-webaction with invalid value
        When I open data/hello.txt
        And I run :debug-webaction blah
        Then the error "blah is not a valid web action!" should be shown

    Scenario: :debug-webaction with non-webaction member
        When I open data/hello.txt
        And I run :debug-webaction PermissionUnknown
        Then the error "PermissionUnknown is not a valid web action!" should be shown

    # :inspect

    @qtwebengine_skip
    Scenario: Inspector without developer extras
        When I set content.developer_extras to false
        And I run :inspector
        Then the error "Please enable developer-extras before using the webinspector!" should be shown

    @qtwebkit_skip
    Scenario: Inspector without --enable-webengine-inspector
        When I run :inspector
        Then the error "Debugging is not enabled. See 'qutebrowser --help' for details." should be shown

    @no_xvfb @posix @qtwebengine_skip
    Scenario: Inspector smoke test
        When I set content.developer_extras to true
        And I run :inspector
        And I wait for "Focus object changed: <PyQt5.QtWebKitWidgets.QWebView object at *>" in the log
        And I run :inspector
        And I wait for "Focus object changed: *" in the log
        Then no crash should happen

    # Different code path as an inspector got created now
    @qtwebengine_skip
    Scenario: Inspector without developer extras (after smoke)
        When I set content.developer_extras to false
        And I run :inspector
        Then the error "Please enable developer-extras before using the webinspector!" should be shown

    # Different code path as an inspector got created now
    @no_xvfb @posix @qtwebengine_skip
    Scenario: Inspector smoke test 2
        When I set content.developer_extras to true
        And I run :inspector
        And I wait for "Focus object changed: <PyQt5.QtWebKitWidgets.QWebView object at *>" in the log
        And I run :inspector
        And I wait for "Focus object changed: *" in the log
        Then no crash should happen

    # :stop/:reload

    @flaky
    Scenario: :stop
        Given I have a fresh instance
        # We can't use "When I open" because we don't want to wait for load
        # finished
        When I run :open http://localhost:(port)/custom/redirect-later?delay=-1
        And I wait for "emitting: cur_load_status_changed('loading') (tab *)" in the log
        And I wait 1s
        And I run :stop
        And I open custom/redirect-later-continue in a new tab
        And I wait 1s
        Then the unordered requests should be:
            custom/redirect-later-continue
            custom/redirect-later?delay=-1
        # no request on / because we stopped the redirect

    Scenario: :stop with wrong count
        When I open data/hello.txt
        And I run :tab-only
        And I run :stop with count 2
        Then no crash should happen

    Scenario: :reload
        When I open data/reload.txt
        And I run :reload
        And I wait until data/reload.txt is loaded
        Then the requests should be:
            data/reload.txt
            data/reload.txt

    Scenario: :reload with force
        When I open headers
        And I run :reload --force
        And I wait until headers is loaded
        Then the header Cache-Control should be set to no-cache

    Scenario: :reload with wrong count
        When I open data/hello.txt
        And I run :tab-only
        And I run :reload with count 2
        Then no crash should happen

    # :view-source

    # Flaky due to :view-source being async?
    @qtwebengine_flaky
    Scenario: :view-source
        Given I open data/hello.txt
        When I run :tab-only
        And I run :view-source
        Then the session should look like:
            windows:
            - tabs:
              - history:
                - active: true
                  url: http://localhost:*/data/hello.txt
              - active: true
                history: []
        And the page should contain the html "/* Literal.Number.Integer */"

    # Flaky due to :view-source being async?
    @qtwebengine_flaky
    Scenario: :view-source on source page.
        When I open data/hello.txt
        And I run :view-source
        And I run :view-source
        Then the error "Already viewing source!" should be shown

    # :help

    Scenario: :help without topic
        When I run :tab-only
        And I run :help
        And I wait until qute://help/index.html is loaded
        Then the following tabs should be open:
            - qute://help/index.html (active)

    Scenario: :help with invalid topic
        When I run :help foo
        Then the error "Invalid help topic foo!" should be shown

    Scenario: :help with command
        When the documentation is up to date
        And I run :tab-only
        And I run :help :back
        And I wait until qute://help/commands.html#back is loaded
        Then the following tabs should be open:
            - qute://help/commands.html#back (active)

    Scenario: :help with invalid command
        When I run :help :foo
        Then the error "Invalid command foo!" should be shown

    Scenario: :help with setting
        When the documentation is up to date
        And I run :tab-only
        And I run :help general->editor
        And I wait until qute://help/settings.html#general-editor is loaded
        Then the following tabs should be open:
            - qute://help/settings.html#general-editor (active)

    Scenario: :help with invalid setting (2 arrows)
        When I run :help general->editor->foo
        Then the error "Invalid help topic general->editor->foo!" should be shown

    Scenario: :help with invalid setting (unknown section)
        When I run :help foo->bar
        Then the error "Invalid section foo!" should be shown

    Scenario: :help with invalid setting (unknown option)
        When I run :help general->bar
        Then the error "Invalid option bar!" should be shown

    Scenario: :help with -t
        When I open about:blank
        And I run :tab-only
        And I run :help -t
        And I wait until qute://help/index.html is loaded
        Then the following tabs should be open:
            - about:blank
            - qute://help/index.html (active)

    # https://github.com/qutebrowser/qutebrowser/issues/2513
    Scenario: Opening link with qute:help
        When the documentation is up to date
        And I run :tab-only
        And I open qute:help without waiting
        And I wait for "Changing title for idx 0 to 'qutebrowser help'" in the log
        And I hint with args "links normal" and follow a
        Then qute://help/quickstart.html should be loaded

    # :history

    Scenario: :history without arguments
        When I run :tab-only
        And I run :history
        And I wait until qute://history/ is loaded
        Then the following tabs should be open:
            - qute://history/ (active)

    Scenario: :history with -t
        When I open about:blank
        And I run :tab-only
        And I run :history -t
        And I wait until qute://history/ is loaded
        Then the following tabs should be open:
            - about:blank
            - qute://history/ (active)

    # :home

    Scenario: :home with single page
        When I set start_page to http://localhost:(port)/data/hello2.txt
        And I run :home
        Then data/hello2.txt should be loaded

    Scenario: :home with multiple pages
        When I set start_page to http://localhost:(port)/data/numbers/1.txt,http://localhost:(port)/data/numbers/2.txt
        And I run :home
        Then data/numbers/1.txt should be loaded

    # pdfjs support

    @qtwebengine_skip: pdfjs is not implemented yet
    Scenario: pdfjs is used for pdf files
        Given pdfjs is available
        When I set content.enable_pdfjs to true
        And I open data/misc/test.pdf
        Then the javascript message "PDF * [*] (PDF.js: *)" should be logged

    @qtwebengine_todo: pdfjs is not implemented yet
    Scenario: pdfjs is not used when disabled
        When I set content.enable_pdfjs to false
        And I set downloads.location.prompt to false
        And I open data/misc/test.pdf
        Then "Download test.pdf finished" should be logged

    @qtwebengine_skip: pdfjs is not implemented yet
    Scenario: Downloading a pdf via pdf.js button (issue 1214)
        Given pdfjs is available
        # WORKAROUND to prevent the "Painter ended with 2 saved states" warning
        # Might be related to https://bugreports.qt.io/browse/QTBUG-13524 and
        # a weird interaction with the previous test.
        And I have a fresh instance
        When I set content.enable_pdfjs to true
        And I set downloads.location.suggestion to filename
        And I set downloads.location.prompt to true
        And I open data/misc/test.pdf
        And I wait for "[qute://pdfjs/*] PDF * (PDF.js: *)" in the log
        And I run :jseval document.getElementById("download").click()
        And I wait for "Asking question <qutebrowser.utils.usertypes.Question default='test.pdf' mode=<PromptMode.download: 5> text=* title='Save file to:'>, *" in the log
        And I run :leave-mode
        Then no crash should happen

    # :print

    # Disabled because it causes weird segfaults and QPainter warnings in Qt...
    @xfail_norun
    Scenario: print preview
        When I open data/hello.txt
        And I run :print --preview
        And I wait for "Focus object changed: *" in the log
        And I run :debug-pyeval QApplication.instance().activeModalWidget().close()
        Then no crash should happen

    # On Windows/OS X, we get a "QPrintDialog: Cannot be used on non-native
    # printers" qWarning.
    #
    # Disabled because it causes weird segfaults and QPainter warnings in Qt...
    @xfail_norun
    Scenario: print
        When I open data/hello.txt
        And I run :print
        And I wait for "Focus object changed: *" in the log or skip the test
        And I run :debug-pyeval QApplication.instance().activeModalWidget().close()
        Then no crash should happen

    # FIXME:qtwebengine use a finer skipping here
    @qtwebengine_skip: printing to pdf is not implemented with older Qt versions
    Scenario: print --pdf
        When I open data/hello.txt
        And I run :print --pdf (tmpdir)/hello.pdf
        And I wait for "Print to file: *" in the log or skip the test
        Then the PDF hello.pdf should exist in the tmpdir

    # :pyeval
    Scenario: Running :pyeval
        When I run :debug-pyeval 1+1
        And I wait until qute://pyeval is loaded
        Then the page should contain the plaintext "2"

    Scenario: Causing exception in :pyeval
        When I run :debug-pyeval 1/0
        And I wait until qute://pyeval is loaded
        Then the page should contain the plaintext "ZeroDivisionError"

    Scenario: Running :pyeval with --quiet
        When I run :debug-pyeval --quiet 1+1
        Then "pyeval output: 2" should be logged

    ## https://github.com/qutebrowser/qutebrowser/issues/504

    Scenario: Focusing download widget via Tab
        When I open about:blank
        And I press the key "<Tab>"
        And I press the key "<Ctrl-C>"
        Then no crash should happen

    @js_prompt
    Scenario: Focusing download widget via Tab (original issue)
        When I open data/prompt/jsprompt.html
        And I run :click-element id button
        And I wait for "Entering mode KeyMode.prompt *" in the log
        And I press the key "<Tab>"
        And I press the key "<Ctrl-C>"
        And I run :leave-mode
        Then no crash should happen

    ## Custom headers

    Scenario: Setting a custom header
        When I set content.custom_headers to {"X-Qute-Test": "testvalue"}
        And I open headers
        Then the header X-Qute-Test should be set to testvalue

    Scenario: DNT header
        When I set content.do_not_track to true
        And I open headers
        Then the header Dnt should be set to 1
        And the header X-Do-Not-Track should be set to 1

    Scenario: DNT header (off)
        When I set content.do_not_track to false
        And I open headers
        Then the header Dnt should be set to 0
        And the header X-Do-Not-Track should be set to 0

    Scenario: Accept-Language header
        When I set content.accept_language to en,de
        And I open headers
        Then the header Accept-Language should be set to en,de

    Scenario: Setting a custom user-agent header
        When I set content.user_agent to toaster
        And I open headers
        And I run :jseval console.log(window.navigator.userAgent)
        Then the header User-Agent should be set to toaster
        And the javascript message "toaster" should be logged

    Scenario: Setting the default user-agent header
        When I set content.user_agent to <empty>
        And I open headers
        And I run :jseval console.log(window.navigator.userAgent)
        Then the header User-Agent should be set to Mozilla/5.0 *
        And the javascript message "Mozilla/5.0 *" should be logged

    ## :messages

    Scenario: :messages without level
        When I run :message-error the-error-message
        And I run :message-warning the-warning-message
        And I run :message-info the-info-message
        And I run :messages
        Then qute://log?level=info should be loaded
        And the error "the-error-message" should be shown
        And the warning "the-warning-message" should be shown
        And the page should contain the plaintext "the-error-message"
        And the page should contain the plaintext "the-warning-message"
        And the page should contain the plaintext "the-info-message"

    Scenario: Showing messages of type 'warning' or greater
        When I run :message-error the-error-message
        And I run :message-warning the-warning-message
        And I run :message-info the-info-message
        And I run :messages warning
        Then qute://log?level=warning should be loaded
        And the error "the-error-message" should be shown
        And the warning "the-warning-message" should be shown
        And the page should contain the plaintext "the-error-message"
        And the page should contain the plaintext "the-warning-message"
        And the page should not contain the plaintext "the-info-message"

    Scenario: Showing messages of type 'info' or greater
        When I run :message-error the-error-message
        And I run :message-warning the-warning-message
        And I run :message-info the-info-message
        And I run :messages info
        Then qute://log?level=info should be loaded
        And the error "the-error-message" should be shown
        And the warning "the-warning-message" should be shown
        And the page should contain the plaintext "the-error-message"
        And the page should contain the plaintext "the-warning-message"
        And the page should contain the plaintext "the-info-message"

    @qtwebengine_flaky
    Scenario: Showing messages of an invalid level
        When I run :messages cataclysmic
        Then the error "Invalid log level cataclysmic!" should be shown

    Scenario: Using qute://log directly
        When I open qute://log without waiting
        # With Qt 5.9, we don't get a loaded message?
        And I wait for "Changing title for idx * to 'log'" in the log
        Then no crash should happen

    Scenario: Using qute://plainlog directly
        When I open qute://plainlog without waiting
        # With Qt 5.9, we don't get a loaded message?
        And I wait for "Changing title for idx * to 'log'" in the log
        Then no crash should happen

    ## https://github.com/qutebrowser/qutebrowser/issues/1523

    Scenario: Completing a single option argument
        When I run :set-cmd-text -s :--
        Then no crash should happen

    ## https://github.com/qutebrowser/qutebrowser/issues/1386

    Scenario: Partial commandline matching with startup command
        When I run :message-i "Hello World" (invalid command)
        Then the error "message-i: no such command" should be shown

     Scenario: Multiple leading : in command
        When I run :::::set-cmd-text ::::message-i "Hello World"
        And I run :command-accept
        Then the message "Hello World" should be shown

    Scenario: Whitespace in command
        When I run :   :  set-cmd-text :  :  message-i "Hello World"
        And I run :command-accept
        Then the message "Hello World" should be shown

    # We can't run :message-i as startup command, so we use
    # :set-cmd-text

    Scenario: Partial commandline matching
        When I run :set-cmd-text :message-i "Hello World"
        And I run :command-accept
        Then the message "Hello World" should be shown

    @no_xvfb
    Scenario: :window-only
        Given I run :tab-only
        And I open data/hello.txt
        When I open data/hello2.txt in a new tab
        And I open data/hello3.txt in a new window
        And I run :window-only
        Then the session should look like:
            windows:
            - tabs:
              - active: true
                history:
                - url: http://localhost:*/data/hello3.txt

    ## Variables

    Scenario: {url} as part of an argument
        When I open data/hello.txt
        And I run :message-info foo{url}
        Then the message "foohttp://localhost:*/hello.txt" should be shown

    Scenario: Multiple variables in an argument
        When I open data/hello.txt
        And I put "foo" into the clipboard
        And I run :message-info {clipboard}bar{url}
        Then the message "foobarhttp://localhost:*/hello.txt" should be shown

    @xfail_norun
    Scenario: {url} in clipboard should not be expanded
        When I open data/hello.txt
        # FIXME: {url} should be escaped, otherwise it is replaced before it enters clipboard
        And I put "{url}" into the clipboard
        And I run :message-info {clipboard}bar{url}
        Then the message "{url}barhttp://localhost:*/hello.txt" should be shown

    ## :click-element

    Scenario: Clicking an element with unknown ID
        When I open data/click_element.html
        And I run :click-element id blah
        Then the error "No element found with id blah!" should be shown

    Scenario: Clicking an element by ID
        When I open data/click_element.html
        And I run :click-element id qute-input
        Then "Entering mode KeyMode.insert (reason: clicking input)" should be logged

    Scenario: Clicking an element with tab target
        When I open data/click_element.html
        And I run :tab-only
        And I run :click-element id link --target=tab
        Then data/hello.txt should be loaded
        And the following tabs should be open:
            - data/click_element.html
            - data/hello.txt (active)

    ## :command-history-{prev,next}

    Scenario: Calling previous command
        When I run :set-cmd-text :message-info blah
        And I run :command-accept
        And I wait for "blah" in the log
        And I run :set-cmd-text :
        And I run :command-history-prev
        And I run :command-accept
        Then the message "blah" should be shown

    Scenario: Browsing through commands 
        When I run :set-cmd-text :message-info blarg
        And I run :command-accept
        And I wait for "blarg" in the log
        And I run :set-cmd-text :
        And I run :command-history-prev
        And I run :command-history-prev
        And I run :command-history-next
        And I run :command-history-next
        And I run :command-accept
        Then the message "blarg" should be shown

    Scenario: Calling previous command when history is empty
        Given I have a fresh instance
        When I run :set-cmd-text :
        And I run :command-history-prev
        And I run :command-accept
        Then the error "No command given" should be shown

    Scenario: Calling next command when there's no next command
        When I run :set-cmd-text :
        And I run :command-history-next
        And I run :command-accept
        Then the error "No command given" should be shown

    ## Modes blacklisted for :enter-mode

    Scenario: Trying to enter command mode with :enter-mode
        When I run :enter-mode command
        Then the error "Mode command can't be entered manually!" should be shown

    ## Renderer crashes

    # Skipped on Windows as "... has stopped working" hangs.
    @qtwebkit_skip @no_invalid_lines @posix @qt<5.9
    Scenario: Renderer crash
        When I run :open -t chrome://crash
        Then the error "Renderer process crashed" should be shown

    @qtwebkit_skip @no_invalid_lines @qt<5.9
    Scenario: Renderer kill
        When I run :open -t chrome://kill
        Then the error "Renderer process was killed" should be shown

    # Skipped on Windows as "... has stopped working" hangs.
    @qtwebkit_skip @no_invalid_lines @posix @qt>=5.9
    Scenario: Renderer crash (5.9)
        When I run :open -t chrome://crash
        Then "Renderer process crashed" should be logged
        And "* 'Error loading chrome://crash/'" should be logged

    @qtwebkit_skip @no_invalid_lines @qt>=5.9
    Scenario: Renderer kill (5.9)
        When I run :open -t chrome://kill
        Then "Renderer process was killed" should be logged
        And "* 'Error loading chrome://kill/'" should be logged

    # https://github.com/qutebrowser/qutebrowser/issues/2290
    @qtwebkit_skip @no_invalid_lines
    Scenario: Navigating to URL after renderer process is gone
        When I run :tab-only
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I run :open chrome://kill
        And I wait for "Renderer process was killed" in the log
        And I open data/numbers/3.txt
        Then no crash should happen
