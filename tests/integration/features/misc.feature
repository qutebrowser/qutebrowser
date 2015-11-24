Feature: Various utility commands.

    ## :set-cmd-text

    Scenario: :set-cmd-text and :command-accept
        When I run :set-cmd-text :message-info "Hello World"
        And I run :command-accept
        Then the message "Hello World" should be shown.

    Scenario: :set-cmd-text with two commands
        When I run :set-cmd-text :message-info test ;; message-error error
        And I run :command-accept
        Then the message "test" should be shown.
        And the error "error" should be shown.

    Scenario: :set-cmd-text with URL replacement
        When I open data/hello.txt
        When I run :set-cmd-text :message-info >{url}<
        And I run :command-accept
        Then the message ">http://localhost:*/hello.txt<" should be shown.

    Scenario: :set-cmd-text with -s and -a
        When I run :set-cmd-text -s :message-info "foo
        And I run :set-cmd-text -a bar"
        And I run :command-accept
        Then the message "foo bar" should be shown.

    Scenario: :set-cmd-text with -a but without text
        When I run :set-cmd-text -a foo
        Then the error "No current text!" should be shown.

    Scenario: :set-cmd-text with invalid command
        When I run :set-cmd-text foo
        Then the error "Invalid command text 'foo'." should be shown.

    ## :message-*

    Scenario: :message-error
        When I run :message-error "Hello World"
        Then the error "Hello World" should be shown.

    Scenario: :message-info
        When I run :message-info "Hello World"
        Then the message "Hello World" should be shown.

    Scenario: :message-warning
        When I run :message-warning "Hello World"
        Then the warning "Hello World" should be shown.

    ## :jseval

    Scenario: :jseval
        When I set general -> log-javascript-console to true
        And I run :jseval console.log("Hello from JS!");
        And I wait for "[:0] Hello from JS!" in the log
        Then the message "No output or error" should be shown.

    Scenario: :jseval without logging
        When I set general -> log-javascript-console to false
        And I run :jseval console.log("Hello from JS!");
        Then the message "No output or error" should be shown.
        And "[:0] Hello from JS!" should not be logged

    Scenario: :jseval with --quiet
        When I set general -> log-javascript-console to true
        And I run :jseval --quiet console.log("Hello from JS!");
        And I wait for "[:0] Hello from JS!" in the log
        Then "No output or error" should not be logged

    Scenario: :jseval with a value
        When I run :jseval "foo"
        Then the message "foo" should be shown.

    Scenario: :jseval with a long, truncated value
        When I run :jseval Array(5002).join("x")
        Then the message "x* [...trimmed...]" should be shown.

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
        Then the error "blah is not a valid web action!" should be shown.

    Scenario: :debug-webaction with non-webaction member
        When I open data/hello.txt
        And I run :debug-webaction PermissionUnknown
        Then the error "PermissionUnknown is not a valid web action!" should be shown.

    # :inspect

    Scenario: Inspector without developer extras
        When I set general -> developer-extras to false
        And I run :inspector
        Then the error "Please enable developer-extras before using the webinspector!" should be shown.

    @not_xvfb @posix
    Scenario: Inspector smoke test
        When I set general -> developer-extras to true
        And I run :inspector
        And I wait for "Focus object changed: <PyQt5.QtWebKitWidgets.QWebView object at *>" in the log
        And I run :inspector
        And I wait for "Focus object changed: *" in the log
        Then no crash should happen

    # :fake-key

    Scenario: :fake-key with an unparsable key
        When I run :fake-key <blub>
        Then the error "Could not parse 'blub': Got unknown key." should be shown.

    Scenario: :fake-key sending key to the website
        When I set general -> log-javascript-console to true
        And I open data/misc/fakekey.html
        And I run :fake-key x
        Then the javascript message "key press: 88" should be logged
        And the javascript message "key release: 88" should be logged

    @not_xvfb @posix
    Scenario: :fake-key sending key to the website with other window focused
        When I open data/misc/fakekey.html
        And I set general -> developer-extras to true
        And I run :inspector
        And I wait for "Focus object changed: <PyQt5.QtWebKitWidgets.QWebView object at *>" in the log
        And I run :fake-key x
        And I run :inspector
        And I wait for "Focus object changed: *" in the log
        Then the error "No focused webview!" should be shown.

    Scenario: :fake-key sending special key to the website
        When I set general -> log-javascript-console to true
        And I open data/misc/fakekey.html
        And I run :fake-key <Escape>
        Then the javascript message "key press: 27" should be logged
        And the javascript message "key release: 27" should be logged

    Scenario: :fake-key sending keychain to the website
        When I set general -> log-javascript-console to true
        And I open data/misc/fakekey.html
        And I run :fake-key xy
        Then the javascript message "key press: 88" should be logged
        And the javascript message "key release: 88" should be logged
        And the javascript message "key press: 89" should be logged
        And the javascript message "key release: 89" should be logged

    Scenario: :fake-key sending keypress to qutebrowser
        When I run :fake-key -g x
        And I wait for "got keypress in mode KeyMode.normal - delegating to <qutebrowser.keyinput.modeparsers.NormalKeyParser>" in the log
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

    Scenario: :reload
        When I open data/hello.txt
        And I run :reload
        And I wait until data/hello.txt is loaded
        Then the requests should be:
            data/hello.txt
            data/hello.txt

    Scenario: :reload with force
        When I open headers
        And I run :reload --force
        And I wait until headers is loaded
        Then the header Cache-Control should be set to no-cache

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
        Then the error "Already viewing source!" should be shown.

    # :debug-console
    @not_xvfb
    Scenario: :debug-console smoke test
        When I run :debug-console
        And I wait for "Focus object changed: <qutebrowser.misc.consolewidget.ConsoleLineEdit *>" in the log
        And I run :debug-console
        And I wait for "Focus object changed: *" in the log
        Then no crash should happen
