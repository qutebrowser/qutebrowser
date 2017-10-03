# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Keyboard input

    Tests for :clear-keychain and other keyboard input related things.

    # :clear-keychain

    Scenario: Clearing the keychain
        When I run :bind ,foo message-error test12
        And I run :bind ,bar message-info test12-2
        And I press the keys ",fo"
        And I run :clear-keychain
        And I press the keys ",bar"
        And I run :unbind ,foo
        And I run :unbind ,bar
        Then the message "test12-2" should be shown

    # input.forward_unbound_keys

    Scenario: Forwarding all keys
        When I open data/keyinput/log.html
        And I set input.forward_unbound_keys to all
        And I press the key ","
        And I press the key "<F1>"
        # ,
        Then the javascript message "key press: 188" should be logged
        And the javascript message "key release: 188" should be logged
        # <F1>
        And the javascript message "key press: 112" should be logged
        And the javascript message "key release: 112" should be logged

    Scenario: Forwarding special keys
        When I open data/keyinput/log.html
        And I set input.forward_unbound_keys to auto
        And I press the key "x"
        And I press the key "<F1>"
        # <F1>
        Then the javascript message "key press: 112" should be logged
        And the javascript message "key release: 112" should be logged
        # x
        And the javascript message "key press: 88" should not be logged
        And the javascript message "key release: 88" should not be logged

    Scenario: Forwarding no keys
        When I open data/keyinput/log.html
        And I set input.forward_unbound_keys to none
        And I press the key "<F1>"
        # <F1>
        Then the javascript message "key press: 112" should not be logged
        And the javascript message "key release: 112" should not be logged

    # :fake-key

    Scenario: :fake-key with an unparsable key
        When I run :fake-key <blub>
        Then the error "Could not parse 'blub': Got unknown key." should be shown

    Scenario: :fake-key sending key to the website
        When I open data/keyinput/log.html
        And I run :fake-key x
        Then the javascript message "key press: 88" should be logged
        And the javascript message "key release: 88" should be logged

    @no_xvfb @posix @qtwebengine_skip
    Scenario: :fake-key sending key to the website with other window focused
        When I open data/keyinput/log.html
        And I set content.developer_extras to true
        And I run :inspector
        And I wait for "Focus object changed: <PyQt5.QtWebKitWidgets.QWebView object at *>" in the log
        And I run :fake-key x
        And I run :inspector
        And I wait for "Focus object changed: <qutebrowser.browser.webkit.webview.WebView *>" in the log
        Then the error "No focused webview!" should be shown

    Scenario: :fake-key sending special key to the website
        When I open data/keyinput/log.html
        And I run :fake-key <Escape>
        Then the javascript message "key press: 27" should be logged
        And the javascript message "key release: 27" should be logged

    Scenario: :fake-key sending keychain to the website
        When I open data/keyinput/log.html
        And I run :fake-key xy
        Then the javascript message "key press: 88" should be logged
        And the javascript message "key release: 88" should be logged
        And the javascript message "key press: 89" should be logged
        And the javascript message "key release: 89" should be logged

    Scenario: :fake-key sending keypress to qutebrowser
        When I run :fake-key -g x
        And I wait for "got keypress in mode KeyMode.normal - delegating to <qutebrowser.keyinput.modeparsers.NormalKeyParser>" in the log
        Then no crash should happen

    # Macros

    Scenario: Recording a simple macro
        When I run :record-macro
        And I press the key "a"
        And I run :message-info "foo 1"
        And I run :message-info "bar 1"
        And I run :record-macro
        And I run :run-macro with count 2
        And I press the key "a"
        Then the message "foo 1" should be shown
        And the message "bar 1" should be shown
        And the message "foo 1" should be shown
        And the message "bar 1" should be shown
        And the message "foo 1" should be shown
        And the message "bar 1" should be shown

    Scenario: Recording a named macro
        When I run :record-macro foo
        And I run :message-info "foo 2"
        And I run :message-info "bar 2"
        And I run :record-macro foo
        And I run :run-macro foo
        Then the message "foo 2" should be shown
        And the message "bar 2" should be shown
        And the message "foo 2" should be shown
        And the message "bar 2" should be shown

    Scenario: Running an invalid macro
        Given I open data/scroll/simple.html
        And I run :tab-only
        When I run :run-macro
        And I press the key "b"
        Then the error "No macro recorded in 'b'!" should be shown
        And no crash should happen

    Scenario: Running an invalid named macro
        Given I open data/scroll/simple.html
        And I run :tab-only
        When I run :run-macro bar
        Then the error "No macro recorded in 'bar'!" should be shown
        And no crash should happen

    Scenario: Running a macro with a mode-switching command
        When I open data/hints/html/simple.html
        And I run :record-macro a
        And I run :hint links normal
        And I wait for "hints: *" in the log
        And I run :leave-mode
        And I run :record-macro a
        And I run :run-macro
        And I press the key "a"
        And I wait for "hints: *" in the log
        Then no crash should happen

    Scenario: Cancelling key input
        When I run :record-macro
        And I press the key "<Escape>"
        Then "Leaving mode KeyMode.record_macro (reason: leave current)" should be logged

    Scenario: Ignoring non-register keys
        When I run :record-macro
        And I press the key "<Menu>"
        And I press the key "c"
        And I run :message-info "foo 3"
        And I run :record-macro
        And I run :run-macro
        And I press the key "c"
        Then the message "foo 3" should be shown
        And the message "foo 3" should be shown
