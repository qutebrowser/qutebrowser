Feature: Keyboard input

    Tests for :bind and :unbind, :clear-keychain and other keyboard input
    related things.

    # :bind

    Scenario: Binding a keychain
        When I run :bind test1 message-info test1
        And I press the keys "test1"
        Then the message "test1" should be shown

    Scenario: Binding an invalid command
        When I run :bind test2 abcd
        Then the error "Invalid command 'abcd'!" should be shown

    Scenario: Binding with invalid mode.
        When I run :bind --mode abcd test3 message-info test3
        Then the error "Invalid mode abcd!" should be shown

    Scenario: Double-binding a key
        When I run :bind test4 message-info test4
        And I run :bind test4 message-info test4-2
        And I press the keys "test4"
        Then the error "Duplicate keychain test4 - use --force to override!" should be shown
        And the message "test4" should be shown

    Scenario: Double-binding with --force
        When I run :bind test5 message-info test5
        And I run :bind --force test5 message-info test5-2
        And I press the keys "test5"
        Then the message "test5-2" should be shown

    # :unbind

    Scenario: Binding and unbinding a keychain
        When I run :bind test6 message-error test6
        And I run :unbind test6
        And I press the keys "test6"
        Then "test6" should not be logged

    Scenario: Unbinding with invalid mode.
        When I run :unbind test7 abcd
        Then the error "Invalid mode abcd!" should be shown

    Scenario: Unbinding with invalid keychain.
        When I run :unbind test8
        Then the error "Can't find binding 'test8' in section 'normal'!" should be shown

    Scenario: Unbinding a built-in binding
        When I run :unbind o
        And I press the key "o"
        Then "No binding found for o." should be logged
        # maybe check it's unbound in the config?

    # :clear-keychain

    Scenario: Clearing the keychain
        When I run :bind foo message-error test9
        And I run :bind bar message-info test9-2
        And I press the keys "fo"
        And I run :clear-keychain
        And I press the keys "bar"
        Then the message "test9-2" should be shown

    # input -> forward-unbound-keys

    Scenario: Forwarding all keys
        When I open data/keyinput/log.html
        And I set general -> log-javascript-console to info
        And I set input -> forward-unbound-keys to all
        And I press the key "q"
        And I press the key "<F1>"
        # q
        Then the javascript message "key press: 81" should be logged
        And the javascript message "key release: 81" should be logged
        # <F1>
        And the javascript message "key press: 112" should be logged
        And the javascript message "key release: 112" should be logged

    Scenario: Forwarding special keys
        When I open data/keyinput/log.html
        And I set general -> log-javascript-console to info
        And I set input -> forward-unbound-keys to auto
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
        And I set general -> log-javascript-console to info
        And I set input -> forward-unbound-keys to none
        And I press the key "<F1>"
        # <F1>
        Then the javascript message "key press: 112" should not be logged
        And the javascript message "key release: 112" should not be logged

    # :fake-key

    Scenario: :fake-key with an unparsable key
        When I run :fake-key <blub>
        Then the error "Could not parse 'blub': Got unknown key." should be shown

    Scenario: :fake-key sending key to the website
        When I set general -> log-javascript-console to info
        And I open data/keyinput/log.html
        And I run :fake-key x
        Then the javascript message "key press: 88" should be logged
        And the javascript message "key release: 88" should be logged

    @no_xvfb @posix
    Scenario: :fake-key sending key to the website with other window focused
        When I open data/keyinput/log.html
        And I set general -> developer-extras to true
        And I run :inspector
        And I wait for "Focus object changed: <PyQt5.QtWebKitWidgets.QWebView object at *>" in the log
        And I run :fake-key x
        And I run :inspector
        And I wait for "Focus object changed: <qutebrowser.browser.webview.WebView *>" in the log
        Then the error "No focused webview!" should be shown

    Scenario: :fake-key sending special key to the website
        When I set general -> log-javascript-console to info
        And I open data/keyinput/log.html
        And I run :fake-key <Escape>
        Then the javascript message "key press: 27" should be logged
        And the javascript message "key release: 27" should be logged

    Scenario: :fake-key sending keychain to the website
        When I set general -> log-javascript-console to info
        And I open data/keyinput/log.html
        And I run :fake-key xy
        Then the javascript message "key press: 88" should be logged
        And the javascript message "key release: 88" should be logged
        And the javascript message "key press: 89" should be logged
        And the javascript message "key release: 89" should be logged

    Scenario: :fake-key sending keypress to qutebrowser
        When I run :fake-key -g x
        And I wait for "got keypress in mode KeyMode.normal - delegating to <qutebrowser.keyinput.modeparsers.NormalKeyParser>" in the log
        Then no crash should happen
