Feature: Keyboard input

    Tests for :bind and :unbind, :clear-keychain and other keyboard input
    related things.

    # :bind

    Scenario: Binding a keychain
        When I run :bind test01 message-info test01
        And I press the keys "test01"
        Then the message "test01" should be shown

    Scenario: Binding an invalid command
        When I run :bind test02 abcd
        Then the error "Invalid command 'abcd'!" should be shown

    Scenario: Binding with invalid mode.
        When I run :bind --mode abcd test03 message-info test03
        Then the error "Invalid mode abcd!" should be shown

    Scenario: Double-binding a key
        When I run :bind test04 message-info test04
        And I run :bind test04 message-info test04-2
        And I press the keys "test04"
        Then the error "Duplicate keychain test04 - use --force to override!" should be shown
        And the message "test04" should be shown

    Scenario: Double-binding with --force
        When I run :bind test05 message-info test05
        And I run :bind --force test05 message-info test05-2
        And I press the keys "test05"
        Then the message "test05-2" should be shown

    Scenario: Printing an unbound key
        When I run :bind test06
        Then the message "test06 is unbound in normal mode" should be shown

    Scenario: Printing a bound key
        When I run :bind test07 message-info foo
        And I run :bind test07
        Then the message "test07 is bound to 'message-info foo' in normal mode" should be shown

    Scenario: Printing a bound key in a given mode
        When I run :bind --mode=caret test08 message-info bar
        And I run :bind --mode=caret test08
        Then the message "test08 is bound to 'message-info bar' in caret mode" should be shown

    Scenario: Binding special keys with differing case (issue 1544)
        When I run :bind <ctrl-test21> message-info test01
        And I run :bind <Ctrl-Test21> message-info test01
        Then the error "Duplicate keychain <ctrl-test21> - use --force to override!" should be shown

    Scenario: Print a special binding with differing case (issue 1544)
        When I run :bind <Ctrl-Test22> message-info foo
        And I run :bind <ctrl-test22>
        Then the message "<ctrl-test22> is bound to 'message-info foo' in normal mode" should be shown

    Scenario: Overriding a special binding with differing case (issue 816)
        When I run :bind <ctrl-test23> message-info foo
        And I run :bind --force <Ctrl-Test23> message-info bar
        And I run :bind <ctrl-test23>
        Then the message "<ctrl-test23> is bound to 'message-info bar' in normal mode" should be shown

    # :unbind

    Scenario: Binding and unbinding a keychain
        When I run :bind test09 message-error test09
        And I run :unbind test09
        And I press the keys "test09"
        Then "test09" should not be logged

    Scenario: Unbinding with invalid mode.
        When I run :unbind test10 abcd
        Then the error "Invalid mode abcd!" should be shown

    Scenario: Unbinding with invalid keychain.
        When I run :unbind test11
        Then the error "Can't find binding 'test11' in section 'normal'!" should be shown

    Scenario: Unbinding a built-in binding
        When I run :unbind o
        And I press the key "o"
        Then "Giving up with 'o', no matches" should be logged
        # maybe check it's unbound in the config?

    Scenario: Binding and unbinding a special keychain with differing case (issue 1544)
        When I run :bind <ctrl-test24> message-error test09
        And I run :unbind <Ctrl-Test24>
        When I run :bind <ctrl-test24>
        Then the message "<ctrl-test24> is unbound in normal mode" should be shown

    # :clear-keychain

    Scenario: Clearing the keychain
        When I run :bind foo message-error test12
        And I run :bind bar message-info test12-2
        And I press the keys "fo"
        And I run :clear-keychain
        And I press the keys "bar"
        Then the message "test12-2" should be shown

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
        And I wait for "Focus object changed: <qutebrowser.browser.webkit.webview.WebView *>" in the log
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
