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

    ## :message-*

    Scenario: :message-error
        When I run :message-error "Hello World"
        Then the error "Hello World" should be shown

    Scenario: :message-info
        When I run :message-info "Hello World"
        Then the message "Hello World" should be shown

    Scenario: :message-warning
        When I run :message-warning "Hello World"
        Then the warning "Hello World" should be shown

    ## :jseval

    Scenario: :jseval
        When I set general -> log-javascript-console to info
        And I run :jseval console.log("Hello from JS!");
        And I wait for the javascript message "Hello from JS!"
        Then the message "No output or error" should be shown

    Scenario: :jseval without logging
        When I set general -> log-javascript-console to none
        And I run :jseval console.log("Hello from JS!");
        Then the message "No output or error" should be shown
        And "[:*] Hello from JS!" should not be logged

    Scenario: :jseval with --quiet
        When I set general -> log-javascript-console to info
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
        When I set general -> log-javascript-console to info
        And I run :jseval --world=1 console.log("Hello from JS!");
        And I wait for the javascript message "Hello from JS!"
        Then "Ignoring world ID 1" should be logged

    @qtwebkit_skip @pyqt>=5.7.0
    Scenario: :jseval uses separate world without --world
        When I set general -> log-javascript-console to info
        And I open data/misc/jseval.html
        And I run :jseval do_log()
        Then the javascript message "Hello from the page!" should not be logged
        And the javascript message "Uncaught ReferenceError: do_log is not defined" should be logged

    @qtwebkit_skip @pyqt>=5.7.0
    Scenario: :jseval using the main world
        When I set general -> log-javascript-console to info
        And I open data/misc/jseval.html
        And I run :jseval --world 0 do_log()
        Then the javascript message "Hello from the page!" should be logged

    @qtwebkit_skip @pyqt>=5.7.0
    Scenario: :jseval using the main world as name
        When I set general -> log-javascript-console to info
        And I open data/misc/jseval.html
        And I run :jseval --world main do_log()
        Then the javascript message "Hello from the page!" should be logged

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

    Scenario: Inspector without developer extras
        When I set general -> developer-extras to false
        And I run :inspector
        Then the error "Please enable developer-extras before using the webinspector!" should be shown

    @no_xvfb @posix @qtwebengine_skip
    Scenario: Inspector smoke test
        When I set general -> developer-extras to true
        And I run :inspector
        And I wait for "Focus object changed: <PyQt5.QtWebKitWidgets.QWebView object at *>" in the log
        And I run :inspector
        And I wait for "Focus object changed: *" in the log
        Then no crash should happen

    # Different code path as an inspector got created now
    Scenario: Inspector without developer extras (after smoke)
        When I set general -> developer-extras to false
        And I run :inspector
        Then the error "Please enable developer-extras before using the webinspector!" should be shown

    # Different code path as an inspector got created now
    @no_xvfb @posix @qtwebengine_skip
    Scenario: Inspector smoke test 2
        When I set general -> developer-extras to true
        And I run :inspector
        And I wait for "Focus object changed: <PyQt5.QtWebKitWidgets.QWebView object at *>" in the log
        And I run :inspector
        And I wait for "Focus object changed: *" in the log
        Then no crash should happen

    # :stop/:reload

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

    # :debug-console

    @no_xvfb
    Scenario: :debug-console smoke test
        When I run :debug-console
        And I wait for "Focus object changed: <qutebrowser.misc.consolewidget.ConsoleLineEdit *>" in the log
        And I run :debug-console
        And I wait for "Focus object changed: *" in the log
        Then no crash should happen

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

    # :home

    Scenario: :home with single page
        When I set general -> startpage to http://localhost:(port)/data/hello2.txt
        And I run :home
        Then data/hello2.txt should be loaded

    Scenario: :home with multiple pages
        When I set general -> startpage to http://localhost:(port)/data/numbers/1.txt,http://localhost:(port)/data/numbers/2.txt
        And I run :home
        Then data/numbers/1.txt should be loaded

    # pdfjs support

    @qtwebengine_todo: pdfjs is not implemented yet
    Scenario: pdfjs is used for pdf files
        Given pdfjs is available
        When I set content -> enable-pdfjs to true
        And I open data/misc/test.pdf
        Then the javascript message "PDF * [*] (PDF.js: *)" should be logged

    @qtwebengine_todo: pdfjs is not implemented yet
    Scenario: pdfjs is not used when disabled
        When I set content -> enable-pdfjs to false
        And I set storage -> prompt-download-directory to false
        And I open data/misc/test.pdf
        Then "Download test.pdf finished" should be logged

    @qtwebengine_todo: pdfjs is not implemented yet
    Scenario: Downloading a pdf via pdf.js button (issue 1214)
        Given pdfjs is available
        # WORKAROUND to prevent the "Painter ended with 2 saved states" warning
        # Might be related to https://bugreports.qt.io/browse/QTBUG-13524 and
        # a weird interaction with the previous test.
        And I have a fresh instance
        When I set content -> enable-pdfjs to true
        And I set completion -> download-path-suggestion to filename
        And I set storage -> prompt-download-directory to true
        And I open data/misc/test.pdf
        And I wait for "[qute://pdfjs/*] PDF * (PDF.js: *)" in the log
        And I run :jseval document.getElementById("download").click()
        And I wait for "Asking question <qutebrowser.utils.usertypes.Question default='test.pdf' mode=<PromptMode.download: 5> text='Save file to:'>, *" in the log
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
        And I wait until qute:pyeval is loaded
        Then the page should contain the plaintext "2"

    Scenario: Causing exception in :pyeval
        When I run :debug-pyeval 1/0
        And I wait until qute:pyeval is loaded
        Then the page should contain the plaintext "ZeroDivisionError"

    Scenario: Running :pyeval with --quiet
        When I run :debug-pyeval --quiet 1+1
        Then "pyeval output: 2" should be logged

    ## https://github.com/The-Compiler/qutebrowser/issues/504

    Scenario: Focusing download widget via Tab
        When I open about:blank
        And I press the key "<Tab>"
        And I press the key "<Ctrl-C>"
        Then no crash should happen

    @pyqt>=5.3.1 @qtwebengine_skip: JS prompt is not implemented yet
    Scenario: Focusing download widget via Tab (original issue)
        When I open data/prompt/jsprompt.html
        And I run :click-element id button
        And I wait for "Entering mode KeyMode.prompt *" in the log
        And I press the key "<Tab>"
        And I press the key "<Ctrl-C>"
        Then no crash should happen

    ## Custom headers

    Scenario: Setting a custom header
        When I set network -> custom-headers to {"X-Qute-Test": "testvalue"}
        And I open headers
        Then the header X-Qute-Test should be set to testvalue

    Scenario: DNT header
        When I set network -> do-not-track to true
        And I open headers
        Then the header Dnt should be set to 1
        And the header X-Do-Not-Track should be set to 1

    Scenario: DNT header (off)
        When I set network -> do-not-track to false
        And I open headers
        Then the header Dnt should be set to 0
        And the header X-Do-Not-Track should be set to 0

    Scenario: Accept-Language header
        When I set network -> accept-language to en,de
        And I open headers
        Then the header Accept-Language should be set to en,de

    ## :messages

    Scenario: Showing error messages
        When I run :message-error the-error-message
        And I run :message-warning the-warning-message
        And I run :message-info the-info-message
        And I run :messages
        Then qute://log?level=error should be loaded
        And the error "the-error-message" should be shown
        And the warning "the-warning-message" should be shown
        And the page should contain the plaintext "the-error-message"
        And the page should not contain the plaintext "the-warning-message"
        And the page should not contain the plaintext "the-info-message"

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

    Scenario: Using qute:log directly
        When I open qute:log
        Then no crash should happen

    Scenario: Using qute:plainlog directly
        When I open qute:plainlog
        Then no crash should happen

    Scenario: Using :messages without messages
        Given I have a fresh instance
        When I run :messages
        Then qute://log?level=error should be loaded
        And the page should contain the plaintext "No messages to show."

    Scenario: Using :debug-log-capacity
        When I run :debug-log-capacity 100
        And I run :message-info oldstuff
        And I run :repeat 20 :message-info otherstuff
        And I run :message-info newstuff
        And I open qute:log
        Then the page should contain the plaintext "newstuff"
        And the page should not contain the plaintext "oldstuff"

   Scenario: Using :debug-log-capacity with negative capacity
       When I run :debug-log-capacity -1
       Then the error "Can't set a negative log capacity!" should be shown

    # :debug-log-level / :debug-log-filter
    # Other :debug-log-{level,filter} features are tested in
    # unit/utils/test_log.py as using them would break end2end tests.

    Scenario: Using debug-log-level with invalid level
        When I run :debug-log-level hello
        Then the error "level: Invalid value hello - expected one of: vdebug, debug, info, warning, error, critical" should be shown

    Scenario: Using debug-log-filter with invalid filter
        When I run :debug-log-filter blah
        Then the error "filters: Invalid value blah - expected one of: statusbar, *" should be shown

    ## https://github.com/The-Compiler/qutebrowser/issues/1523

    Scenario: Completing a single option argument
        When I run :set-cmd-text -s :--
        Then no crash should happen

    ## https://github.com/The-Compiler/qutebrowser/issues/1386

    Scenario: Partial commandline matching with startup command
        When I run :message-i "Hello World" (invalid command)
        Then the error "message-i: no such command" should be shown

    # We can't run :message-i as startup command, so we use
    # :set-cmd-text

    Scenario: Partial commandline matching
        When I run :set-cmd-text :message-i "Hello World"
        And I run :command-accept
        Then the message "Hello World" should be shown

    ## https://github.com/The-Compiler/qutebrowser/issues/1219

    @qtwebengine_todo: private browsing is not implemented yet
    Scenario: Sharing cookies with private browsing
        When I set general -> private-browsing to true
        And I open cookies/set?qute-test=42 without waiting
        And I wait until cookies is loaded
        And I open cookies in a new tab
        Then the cookie qute-test should be set to 42

    ## https://github.com/The-Compiler/qutebrowser/issues/1742

    @qtwebengine_todo: private browsing is not implemented yet
    Scenario: Private browsing is activated in QtWebKit without restart
        When I set general -> private-browsing to true
        And I open data/javascript/localstorage.html
        Then the page should contain the plaintext "Local storage status: not working"

    Scenario: :repeat-command
        Given I open data/scroll/simple.html
        And I run :tab-only
        When I run :scroll down
        And I run :repeat-command
        And I run :scroll up
        Then the page should be scrolled vertically

    Scenario: :repeat-command with count
        Given I open data/scroll/simple.html
        And I run :tab-only
        When I run :scroll down with count 3
        And I wait until the scroll position changed
        And I run :scroll up
        And I wait until the scroll position changed
        And I run :repeat-command with count 2
        And I wait until the scroll position changed to 0/0
        Then the page should not be scrolled

    Scenario: :repeat-command with not-normal command inbetween
        Given I open data/scroll/simple.html
        And I run :tab-only
        When I run :scroll down with count 3
        And I wait until the scroll position changed
        And I run :scroll up
        And I wait until the scroll position changed
        And I run :prompt-accept
        And I run :repeat-command with count 2
        And I wait until the scroll position changed to 0/0
        Then the page should not be scrolled
        And the error "prompt-accept: This command is only allowed in prompt/yesno mode, not normal." should be shown

    @qtwebengine_createWindow
    Scenario: :repeat-command with mode-switching command
        Given I open data/hints/link_blank.html
        And I run :tab-only
        When I hint with args "all"
        And I run :leave-mode
        And I run :repeat-command
        And I run :follow-hint a
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - data/hints/link_blank.html
            - data/hello.txt (active)

    Scenario: Using 0 as count
        When I run :scroll down with count 0
        Then the error "scroll: A zero count is not allowed for this command!" should be shown

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
        Then the error "No element found!" should be shown

    Scenario: Clicking an element by ID
        When I open data/click_element.html
        And I run :click-element id qute-input
        Then "Clicked editable element!" should be logged

    Scenario: Clicking an element with tab target
        When I open data/click_element.html
        And I run :tab-only
        And I run :click-element id link --target=tab
        Then data/hello.txt should be loaded
        And the following tabs should be open:
            - data/click_element.html
            - data/hello.txt (active)

    @qtwebengine_flaky
    Scenario: Clicking an element which is out of view
        When I open data/scroll/simple.html
        And I run :scroll-page 0 1
        And I wait until the scroll position changed
        And I run :click-element id link
        Then the error "Element position is out of view!" should be shown
