# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Various utility commands.

    ## :set-cmd-text

    Scenario: :set-cmd-text and :command-accept
        When I run :set-cmd-text :message-info "Hello World"
        And I run :command-accept
        Then the message "Hello World" should be shown

    Scenario: :set-cmd-text and :command-accept --rapid
        When I run :set-cmd-text :message-info "Hello World"
        And I run :command-accept --rapid
        And I run :command-accept
        Then the message "Hello World" should be shown
        And the message "Hello World" should be shown

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

    Scenario: :set-cmd-text with run on count flag and no count
        When I run :set-cmd-text --run-on-count :message-info "Hello World"
        Then "message:info:86 Hello World" should not be logged

    Scenario: :set-cmd-text with run on count flag and a count
        When I run :set-cmd-text --run-on-count :message-info "Hello World" with count 1
        Then the message "Hello World" should be shown

    ## :jseval

    Scenario: :jseval
        When I run :jseval console.log("Hello from JS!");
        And I wait for the javascript message "Hello from JS!"
        Then the message "No output or error" should be shown

    Scenario: :jseval without logging
        When I set content.javascript.log to {"unknown": "none", "info": "none", "warning": "debug", "error": "debug"}
        And I run :jseval console.log("Hello from JS!");
        And I wait for "No output or error" in the log
        And I set content.javascript.log to {"unknown": "debug", "info": "debug", "warning": "debug", "error": "debug"}
        Then "[:*] Hello from JS!" should not be logged

    Scenario: :jseval with --quiet
        When I run :jseval --quiet console.log("Hello from JS!");
        And I wait for the javascript message "Hello from JS!"
        Then "No output or error" should not be logged

    Scenario: :jseval with a value
        When I run :jseval "foo"
        Then the message "foo" should be shown

    Scenario: :jseval with a long, truncated value
        When I run :jseval Array(5002).join("x")
        Then the message "x* [...trimmed...]" should be shown

    Scenario: :jseval --url
        When I run :jseval --url javascript:console.log("hello world?")
        Then the javascript message "hello world?" should be logged

    @qtwebengine_skip
    Scenario: :jseval with --world on QtWebKit
        When I run :jseval --world=1 console.log("Hello from JS!");
        And I wait for the javascript message "Hello from JS!"
        Then "Ignoring world ID 1" should be logged
        And "No output or error" should be logged

    @qtwebkit_skip
    Scenario: :jseval uses separate world without --world
        When I open data/misc/jseval.html
        And I run :jseval do_log()
        Then the javascript message "Hello from the page!" should not be logged
        And the javascript message "Uncaught ReferenceError: do_log is not defined" should be logged
        And "No output or error" should be logged

    @qtwebkit_skip
    Scenario: :jseval using the main world
        When I open data/misc/jseval.html
        And I run :jseval --world 0 do_log()
        Then the javascript message "Hello from the page!" should be logged
        And "No output or error" should be logged

    @qtwebkit_skip
    Scenario: :jseval using the main world as name
        When I open data/misc/jseval.html
        And I run :jseval --world main do_log()
        Then the javascript message "Hello from the page!" should be logged
        And "No output or error" should be logged

    @qtwebkit_skip
    Scenario: :jseval using too high of a world
        When I run :jseval --world=257 console.log("Hello from JS!");
        Then the error "World ID should be between 0 and *" should be shown

    @qtwebkit_skip
    Scenario: :jseval using a negative world id
        When I run :jseval --world=-1 console.log("Hello from JS!");
        Then the error "World ID should be between 0 and *" should be shown

    Scenario: :jseval --file using a file that exists as js-code
        When I run :jseval --file (testdata)/misc/jseval_file.js
        Then the javascript message "Hello from JS!" should be logged
        And the javascript message "Hello again from JS!" should be logged
        And "No output or error" should be logged

    Scenario: :jseval --file using a file that doesn't exist as js-code
        When I run :jseval --file /nonexistentfile
        Then the error "[Errno 2] *: '/nonexistentfile'" should be shown
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

    @no_xvfb @posix @qtwebengine_skip
    Scenario: Inspector smoke test
        When I run :devtools
        And I wait for "Focus object changed: <PyQt5.QtWebKitWidgets.QWebView object at *>" in the log
        And I run :devtools
        And I wait for "Focus object changed: *" in the log
        Then no crash should happen

    # Different code path as an inspector got created now
    @no_xvfb @posix @qtwebengine_skip
    Scenario: Inspector smoke test 2
        When I run :devtools
        And I wait for "Focus object changed: <PyQt5.QtWebKitWidgets.QWebView object at *>" in the log
        And I run :devtools
        And I wait for "Focus object changed: *" in the log
        Then no crash should happen

    # :stop/:reload

    @flaky
    Scenario: :stop
        Given I have a fresh instance
        # We can't use "When I open" because we don't want to wait for load
        # finished
        When I run :open http://localhost:(port)/redirect-later?delay=-1
        And I wait for "emitting: cur_load_status_changed(<LoadStatus.loading: *>) (tab *)" in the log
        And I wait 1s
        And I run :stop
        And I open redirect-later-continue in a new tab
        And I wait 1s
        Then the unordered requests should be:
            redirect-later-continue
            redirect-later?delay=-1
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

    # :home

    Scenario: :home with single page
        When I set url.start_pages to ["http://localhost:(port)/data/hello2.txt"]
        And I run :home
        Then data/hello2.txt should be loaded

    Scenario: :home with multiple pages
        When I set url.start_pages to ["http://localhost:(port)/data/numbers/1.txt", "http://localhost:(port)/data/numbers/2.txt"]
        And I run :home
        Then data/numbers/1.txt should be loaded

    # :print

    # Disabled because it causes weird segfaults and QPainter warnings in Qt...
    @xfail_norun
    Scenario: print preview
        When I open data/hello.txt
        And I run :print --preview
        And I wait for "Focus object changed: *" in the log
        And I run :debug-pyeval QApplication.instance().activeModalWidget().close()
        Then no crash should happen

    # On Windows/macOS, we get a "QPrintDialog: Cannot be used on non-native
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

    ## https://github.com/qutebrowser/qutebrowser/issues/504

    Scenario: Focusing download widget via Tab
        When I open about:blank
        And I press the key "<Tab>"
        And I press the key "<Ctrl-C>"
        Then no crash should happen

    Scenario: Focusing download widget via Tab (original issue)
        When I open data/prompt/jsprompt.html
        And I run :click-element id button
        And I wait for "Entering mode KeyMode.prompt *" in the log
        And I press the key "<Tab>"
        And I press the key "<Ctrl-C>"
        And I run :mode-leave
        Then no crash should happen

    ## Custom headers

    Scenario: Setting a custom header
        When I set content.headers.custom to {"X-Qute-Test": "testvalue"}
        And I open headers
        Then the header X-Qute-Test should be set to testvalue

    Scenario: Setting accept header
        When I set content.headers.custom to {"Accept": "testvalue"}
        And I open headers
        Then the header Accept should be set to testvalue

    Scenario: DNT header
        When I set content.headers.do_not_track to true
        And I open headers
        Then the header Dnt should be set to 1

    Scenario: DNT header (off)
        When I set content.headers.do_not_track to false
        And I open headers
        Then the header Dnt should be set to 0

    Scenario: DNT header (unset)
        When I set content.headers.do_not_track to <empty>
        And I open headers
        Then the header Dnt should be set to <unset>

    Scenario: Accept-Language header
        When I set content.headers.accept_language to en,de
        And I open headers
        Then the header Accept-Language should be set to en,de

    # This still doesn't set window.navigator.language
    # See https://bugreports.qt.io/browse/QTBUG-61949
    @qtwebkit_skip @js_headers
    Scenario: Accept-Language header (JS)
        When I set content.headers.accept_language to it,fr
        And I run :jseval console.log(window.navigator.languages)
        Then the javascript message "it,fr" should be logged

    Scenario: User-agent header
        When I set content.headers.user_agent to toaster
        And I open headers
        And I run :jseval console.log(window.navigator.userAgent)
        Then the header User-Agent should be set to toaster

    @js_headers
    Scenario: User-agent header (JS)
        When I set content.headers.user_agent to toaster
        And I open about:blank
        And I run :jseval console.log(window.navigator.userAgent)
        Then the javascript message "toaster" should be logged

    @qtwebkit_skip
    Scenario: Custom headers via XHR
        When I set content.headers.custom to {"Accept": "config-value", "X-Qute-Test": "config-value"}
        And I open data/misc/xhr_headers.html
        And I wait for the javascript message "Got headers via XHR"
        Then the header Accept should be set to '*/*'
        And the header X-Qute-Test should be set to config-value

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

    ## https://github.com/qutebrowser/qutebrowser/issues/4720
    Scenario: Chaining failing commands
        When I run :scroll x ;; message-info foo
        Then the error "Invalid value 'x' for direction - *" should be shown
        And the message "foo" should be shown

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
        And I wait for "Closing window *" in the log
        And I wait for "removed: main-window" in the log
        Then the session should look like:
            windows:
            - tabs:
              - active: true
                history:
                - url: http://localhost:*/data/hello3.txt

    ## :click-element

    Scenario: Clicking an element with unknown ID
        When I open data/click_element.html
        And I run :click-element id blah
        Then the error "No element found with id blah!" should be shown

    Scenario: Clicking an element by ID
        When I open data/click_element.html
        And I run :click-element id qute-input
        Then "Entering mode KeyMode.insert (reason: clicking input)" should be logged

    Scenario: Clicking an element by ID with dot
        When I open data/click_element.html
        And I run :click-element id foo.bar
        Then the javascript message "id with dot" should be logged

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

    Scenario: Command starting with space and calling previous command
        When I run :set-cmd-text :message-info first
        And I run :command-accept
        And I wait for "first" in the log
        When I run :set-cmd-text : message-info second
        And I run :command-accept
        And I wait for "second" in the log
        And I run :set-cmd-text :
        And I run :command-history-prev
        And I run :command-accept
        Then the message "first" should be shown

    Scenario: Calling previous command with :completion-item-focus
        When I run :set-cmd-text :message-info blah
        And I wait for "Entering mode KeyMode.command (reason: *)" in the log
        And I run :command-accept
        And I wait for "blah" in the log
        And I run :set-cmd-text :
        And I wait for "Entering mode KeyMode.command (reason: *)" in the log
        And I run :completion-item-focus prev --history
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

    ## Modes blacklisted for :mode-enter

    Scenario: Trying to enter command mode with :mode-enter
        When I run :mode-enter command
        Then the error "Mode command can't be entered manually!" should be shown

    ## Renderer crashes

    # Skipped on Windows as "... has stopped working" hangs.
    @qtwebkit_skip @no_invalid_lines @posix
    Scenario: Renderer crash
        When I run :open -t chrome://crash
        Then "Renderer process crashed (status *)" should be logged
        And "* 'Error loading chrome://crash/'" should be logged

    @qtwebkit_skip @no_invalid_lines @flaky
    Scenario: Renderer kill
        When I run :open -t chrome://kill
        Then "Renderer process was killed (status *)" should be logged
        And "* 'Error loading chrome://kill/'" should be logged

    # https://github.com/qutebrowser/qutebrowser/issues/2290
    @qtwebkit_skip @no_invalid_lines @flaky
    Scenario: Navigating to URL after renderer process is gone
        When I run :tab-only
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I run :open chrome://kill
        And I wait for "Renderer process was killed (status *)" in the log
        And I open data/numbers/3.txt
        Then no crash should happen

    # https://github.com/qutebrowser/qutebrowser/issues/5721
    @qtwebkit_skip @qt!=5.15.1
    Scenario: WebRTC renderer process crash
        When I open data/crashers/webrtc.html in a new tab
        And I run :reload
        And I wait until data/crashers/webrtc.html is loaded
        Then "Renderer process crashed (status *)" should not be logged

    Scenario: InstalledApps crash
        When I open data/crashers/installedapp.html in a new tab
        Then "Renderer process was killed (status *)" should not be logged

    ## Other

    Scenario: Resource with invalid URL
        When I open data/invalid_resource.html in a new tab
        Then "Ignoring invalid * URL: Invalid hostname (contains invalid characters); *" should be logged
        And no crash should happen
