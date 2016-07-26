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
        And I wait for "[:0] Hello from JS!" in the log
        Then the message "No output or error" should be shown

    Scenario: :jseval without logging
        When I set general -> log-javascript-console to none
        And I run :jseval console.log("Hello from JS!");
        Then the message "No output or error" should be shown
        And "[:0] Hello from JS!" should not be logged

    Scenario: :jseval with --quiet
        When I set general -> log-javascript-console to info
        And I run :jseval --quiet console.log("Hello from JS!");
        And I wait for "[:0] Hello from JS!" in the log
        Then "No output or error" should not be logged

    Scenario: :jseval with a value
        When I run :jseval "foo"
        Then the message "foo" should be shown

    Scenario: :jseval with a long, truncated value
        When I run :jseval Array(5002).join("x")
        Then the message "x* [...trimmed...]" should be shown

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

    @no_xvfb @posix
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
    @no_xvfb @posix
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
        And the page source should look like misc/hello.txt.html

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

    Scenario: pdfjs is used for pdf files
        Given pdfjs is available
        When I set content -> enable-pdfjs to true
        And I open data/misc/test.pdf
        Then the javascript message "PDF * [*] (PDF.js: *)" should be logged

    Scenario: pdfjs is not used when disabled
        When I set content -> enable-pdfjs to false
        And I set storage -> prompt-download-directory to false
        And I open data/misc/test.pdf
        Then "Download finished" should be logged

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

    @pyqt>=5.3.1
    Scenario: Focusing download widget via Tab (original issue)
        When I open data/prompt/jsprompt.html
        And I run :hint
        And I run :follow-hint a
        And I wait for "Entering mode KeyMode.prompt *" in the log
        And I press the key "<Tab>"
        And I press the key "<Ctrl-C>"
        Then no crash should happen

    ## Custom headers

    Scenario: Setting a custom header
        When I set network -> custom-headers to {"X-Qute-Test": "testvalue"}
        And I open headers
        Then the header X-Qute-Test should be set to testvalue

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

    Scenario: Sharing cookies with private browsing
        When I set general -> private-browsing to true
        And I open cookies/set?qute-test=42 without waiting
        And I wait until cookies is loaded
        And I open cookies in a new tab
        Then the cookie qute-test should be set to 42

    Scenario: :repeat-command
        Given I open data/scroll.html
        And I run :tab-only
        When I run :scroll down
        And I run :repeat-command
        And I run :scroll up
        Then the page should be scrolled vertically

    Scenario: :repeat-command with count
        Given I open data/scroll.html
        And I run :tab-only
        When I run :scroll down with count 3
        And I run :scroll up
        And I run :repeat-command with count 2
        Then the page should not be scrolled

    Scenario: :repeat-command with not-normal command inbetween
        Given I open data/scroll.html
        And I run :tab-only
        When I run :scroll down with count 3
        And I run :scroll up
        And I run :prompt-accept
        And I run :repeat-command with count 2
        Then the page should not be scrolled
        And the error "prompt-accept: This command is only allowed in prompt/yesno mode." should be shown

    Scenario: :repeat-command with mode-switching command
        Given I open data/hints/link_blank.html
        And I run :tab-only
        When I run :hint
        And I run :leave-mode
        And I run :repeat-command
        And I run :follow-hint a
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - data/hints/link_blank.html
            - data/hello.txt (active)
