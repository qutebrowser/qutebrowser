Feature: Using hints

    Scenario: Using :follow-hint outside of hint mode (issue 1105)
        When I run :follow-hint
        Then the error "follow-hint: This command is only allowed in hint mode, not normal." should be shown

    Scenario: Using :follow-hint with an invalid index.
        When I open data/hints/html/simple.html
        And I hint with args "links normal" and follow xyz
        Then the error "No hint xyz!" should be shown

    # https://travis-ci.org/The-Compiler/qutebrowser/jobs/159412291
    @qtwebengine_flaky
    Scenario: Following a link after scrolling down
        When I open data/scroll/simple.html
        And I run :hint links normal
        And I wait for "hints: *" in the log
        And I run :scroll-page 0 1
        And I wait until the scroll position changed
        And I run :follow-hint a
        Then the error "Element position is out of view!" should be shown

    ### Opening in current or new tab

    @qtwebengine_createWindow
    Scenario: Following a hint and force to open in current tab.
        When I open data/hints/link_blank.html
        And I hint with args "links current" and follow a
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - data/hello.txt (active)

    @qtwebengine_createWindow
    Scenario: Following a hint and allow to open in new tab.
        When I open data/hints/link_blank.html
        And I hint with args "links normal" and follow a
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - data/hints/link_blank.html
            - data/hello.txt (active)

    @qtwebengine_createWindow
    Scenario: Following a hint to link with sub-element and force to open in current tab.
        When I open data/hints/link_span.html
        And I run :tab-close
        And I hint with args "links current" and follow a
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - data/hello.txt (active)

    Scenario: Entering and leaving hinting mode (issue 1464)
        When I open data/hints/html/simple.html
        And I hint with args "all"
        And I run :fake-key -g <Esc>
        Then no crash should happen

    Scenario: Using :hint spawn with flags and -- (issue 797)
        When I open data/hints/html/simple.html
        And I hint with args "-- all spawn -v echo" and follow a
        Then the message "Command exited successfully." should be shown

    Scenario: Using :hint spawn with flags (issue 797)
        When I open data/hints/html/simple.html
        And I hint with args "all spawn -v echo" and follow a
        Then the message "Command exited successfully." should be shown

    Scenario: Using :hint spawn with flags and --rapid (issue 797)
        When I open data/hints/html/simple.html
        And I hint with args "--rapid all spawn -v echo" and follow a
        Then the message "Command exited successfully." should be shown

    @posix
    Scenario: Using :hint spawn with flags passed to the command (issue 797)
        When I open data/hints/html/simple.html
        And I hint with args "--rapid all spawn -v echo -e foo" and follow a
        Then the message "Command exited successfully." should be shown

    Scenario: Using :hint run
        When I open data/hints/html/simple.html
        And I hint with args "all run message-info {hint-url}" and follow a
        Then the message "http://localhost:(port)/data/hello.txt" should be shown

    Scenario: Using :hint fill
        When I open data/hints/html/simple.html
        And I hint with args "all fill :message-info {hint-url}" and follow a
        And I press the key "<Enter>"
        Then the message "http://localhost:(port)/data/hello.txt" should be shown

    @posix
    Scenario: Using :hint userscript
        When I open data/hints/html/simple.html
        And I hint with args "all userscript (testdata)/userscripts/echo_hint_text" and follow a
        Then the message "Follow me!" should be shown

    Scenario: Yanking to clipboard
        When I run :debug-set-fake-clipboard
        And I open data/hints/html/simple.html
        And I hint with args "links yank" and follow a
        Then the clipboard should contain "http://localhost:(port)/data/hello.txt"

    Scenario: Yanking to primary selection
        When selection is supported
        And I run :debug-set-fake-clipboard
        And I open data/hints/html/simple.html
        And I hint with args "links yank-primary" and follow a
        Then the primary selection should contain "http://localhost:(port)/data/hello.txt"

    Scenario: Yanking to primary selection without it being supported (#1336)
        When selection is not supported
        And I run :debug-set-fake-clipboard
        And I open data/hints/html/simple.html
        And I hint with args "links yank-primary" and follow a
        Then the clipboard should contain "http://localhost:(port)/data/hello.txt"

    Scenario: Using hint --rapid to hit multiple buttons
        When I open data/hints/buttons.html
        And I hint with args "--rapid"
        And I run :follow-hint s
        And I run :follow-hint d
        And I run :follow-hint f
        Then the javascript message "beep!" should be logged
        And the javascript message "bop!" should be logged
        And the javascript message "boop!" should be logged

    Scenario: Using :hint run with a URL containing spaces
        When I open data/hints/html/with_spaces.html
        And I hint with args "all run message-info {hint-url}" and follow a
        Then the message "http://localhost:(port)/data/hello.txt" should be shown

    Scenario: Clicking an invalid link
        When I open data/invalid_link.html
        And I hint with args "all" and follow a
        Then the error "Invalid link clicked - *" should be shown

    Scenario: Hinting inputs without type
        When I open data/hints/input.html
        And I hint with args "inputs" and follow a
        And I wait for "Entering mode KeyMode.insert (reason: click)" in the log
        And I run :leave-mode
        # The actual check is already done above
        Then no crash should happen

    Scenario: Hinting with ACE editor
        When I open data/hints/ace/ace.html
        And I hint with args "inputs" and follow a
        And I wait for "Entering mode KeyMode.insert (reason: click)" in the log
        And I run :leave-mode
        # The actual check is already done above
        Then no crash should happen

    ### iframes

    @qtwebengine_todo: Hinting in iframes is not implemented yet
    Scenario: Using :follow-hint inside an iframe
        When I open data/hints/iframe.html
        And I hint with args "links normal" and follow a
        Then "navigation request: url http://localhost:*/data/hello.txt, type NavigationTypeLinkClicked, *" should be logged

    ### FIXME currenly skipped, see https://github.com/The-Compiler/qutebrowser/issues/1525
    @xfail_norun
    Scenario: Using :follow-hint inside a scrolled iframe
        When I open data/hints/iframe_scroll.html
        And I hint with args "all normal" and follow a
        And I run :scroll bottom
        And I hint wht args "links normal" and follow a
        Then "navigation request: url http://localhost:*/data/hello2.txt, type NavigationTypeLinkClicked, *" should be logged

    @qtwebengine_createWindow
    Scenario: Opening a link inside a specific iframe
        When I open data/hints/iframe_target.html
        And I hint with args "links normal" and follow a
        Then "navigation request: url http://localhost:*/data/hello.txt, type NavigationTypeLinkClicked, *" should be logged

    @qtwebengine_createWindow
    Scenario: Opening a link with specific target frame in a new tab
        When I open data/hints/iframe_target.html
        And I hint with args "links tab" and follow a
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - data/hints/iframe_target.html
            - data/hello.txt (active)

    ### hints -> auto-follow-timeout

    @not_osx
    Scenario: Ignoring key presses after auto-following hints
        When I set hints -> auto-follow-timeout to 1000
        And I set hints -> mode to number
        And I run :bind --force , message-error "This error message was triggered via a keybinding which should have been inhibited"
        And I open data/hints/html/simple.html
        And I hint with args "all"
        And I press the key "f"
        And I wait until data/hello.txt is loaded
        And I press the key ","
        # Waiting here so we don't affect the next test
        And I wait for "Releasing inhibition state of normal mode." in the log
        Then "Ignoring key ',', because the normal mode is currently inhibited." should be logged

    Scenario: Turning off auto-follow-timeout
        When I set hints -> auto-follow-timeout to 0
        And I set hints -> mode to number
        And I run :bind --force , message-info "Keypress worked!"
        And I open data/hints/html/simple.html
        And I hint with args "all"
        And I press the key "f"
        And I wait until data/hello.txt is loaded
        And I press the key ","
        Then the message "Keypress worked!" should be shown

    ### Word hints

    Scenario: Hinting with a too short dictionary
        When I open data/hints/short_dict.html
        And I set hints -> mode to word
        # Test letter fallback
        And I hint with args "all" and follow d
        Then the error "Not enough words in the dictionary." should be shown
        And data/numbers/5.txt should be loaded

    Scenario: Dictionary file does not exist
        When I open data/hints/html/simple.html
        And I set hints -> dictionary to no_words
        And I set hints -> mode to word
        And I run :hint
        And I wait for "hints: *" in the log
        And I press the key "a"
        Then the error "Word hints requires reading the file at *" should be shown
        And data/hello.txt should be loaded

    ### Number hint mode

    # https://github.com/The-Compiler/qutebrowser/issues/308
    Scenario: Renumbering hints when filtering
        When I open data/hints/number.html
        And I set hints -> mode to number
        And I hint with args "all"
        And I press the key "s"
        And I run :follow-hint 1
        Then data/numbers/7.txt should be loaded

    # https://github.com/The-Compiler/qutebrowser/issues/576
    @qtwebengine_flaky
    Scenario: Keeping hint filter in rapid mode
        When I open data/hints/number.html
        And I set hints -> mode to number
        And I hint with args "all tab-bg --rapid"
        And I press the key "t"
        And I run :follow-hint 0
        And I run :follow-hint 1
        Then data/numbers/2.txt should be loaded
        And data/numbers/3.txt should be loaded

    # https://github.com/The-Compiler/qutebrowser/issues/1186
    Scenario: Keeping hints filter when using backspace
        When I open data/hints/issue1186.html
        And I set hints -> mode to number
        And I hint with args "all"
        And I press the key "x"
        And I press the key "0"
        And I press the key "<Backspace>"
        And I run :follow-hint 11
        Then the error "No hint 11!" should be shown

    # https://github.com/The-Compiler/qutebrowser/issues/674#issuecomment-165096744
    Scenario: Multi-word matching
        When I open data/hints/number.html
        And I set hints -> mode to number
        And I set hints -> auto-follow to unique-match
        And I set hints -> auto-follow-timeout to 0
        And I hint with args "all"
        And I press the keys "ten pos"
        Then data/numbers/11.txt should be loaded

    Scenario: Scattering is ignored with number hints
        When I open data/hints/number.html
        And I set hints -> mode to number
        And I set hints -> scatter to true
        And I hint with args "all" and follow 00
        Then data/numbers/1.txt should be loaded

    # https://github.com/The-Compiler/qutebrowser/issues/1559
    Scenario: Filtering all hints in number mode
        When I open data/hints/number.html
        And I set hints -> mode to number
        And I hint with args "all"
        And I press the key "2"
        And I wait for "Leaving mode KeyMode.hint (reason: all filtered)" in the log
        Then no crash should happen

    # https://github.com/The-Compiler/qutebrowser/issues/1657
    Scenario: Using rapid number hinting twice
        When I open data/hints/number.html
        And I set hints -> mode to number
        And I hint with args "--rapid"
        And I run :leave-mode
        And I hint with args "--rapid" and follow 00
        Then data/numbers/1.txt should be loaded

    Scenario: Using a specific hints mode
        When I open data/hints/number.html
        And I set hints -> mode to letter
        And I hint with args "--mode number all"
        And I press the key "s"
        And I run :follow-hint 1
        Then data/numbers/7.txt should be loaded

    ### auto-follow option

    Scenario: Using hints -> auto-follow == 'always' in letter mode
        When I open data/hints/html/simple.html
        And I set hints -> mode to letter
        And I set hints -> auto-follow to always
        And I hint with args "all"
        Then data/hello.txt should be loaded

    # unique-match is actually the same as full-match in letter mode
    Scenario: Using hints -> auto-follow == 'unique-match' in letter mode
        When I open data/hints/html/simple.html
        And I set hints -> mode to letter
        And I set hints -> auto-follow to unique-match
        And I hint with args "all"
        And I press the key "a"
        Then data/hello.txt should be loaded

    Scenario: Using hints -> auto-follow == 'full-match' in letter mode
        When I open data/hints/html/simple.html
        And I set hints -> mode to letter
        And I set hints -> auto-follow to full-match
        And I hint with args "all"
        And I press the key "a"
        Then data/hello.txt should be loaded

    Scenario: Using hints -> auto-follow == 'never' without Enter in letter mode
        When I open data/hints/html/simple.html
        And I set hints -> mode to letter
        And I set hints -> auto-follow to never
        And I hint with args "all"
        And I press the key "a"
        Then "Leaving mode KeyMode.hint (reason: followed)" should not be logged

    Scenario: Using hints -> auto-follow == 'never' in letter mode
        When I open data/hints/html/simple.html
        And I set hints -> mode to letter
        And I set hints -> auto-follow to never
        And I hint with args "all"
        And I press the key "a"
        And I press the key "<Enter>"
        Then data/hello.txt should be loaded

    Scenario: Using hints -> auto-follow == 'always' in number mode
        When I open data/hints/html/simple.html
        And I set hints -> mode to number
        And I set hints -> auto-follow to always
        And I hint with args "all"
        Then data/hello.txt should be loaded

    Scenario: Using hints -> auto-follow == 'unique-match' in number mode
        When I open data/hints/html/simple.html
        And I set hints -> mode to number
        And I set hints -> auto-follow to unique-match
        And I hint with args "all"
        And I press the key "f"
        Then data/hello.txt should be loaded

    Scenario: Using hints -> auto-follow == 'full-match' in number mode
        When I open data/hints/html/simple.html
        And I set hints -> mode to number
        And I set hints -> auto-follow to full-match
        And I hint with args "all"
        # this actually presses the keys one by one
        And I press the key "follow me!"
        Then data/hello.txt should be loaded

    Scenario: Using hints -> auto-follow == 'never' without Enter in number mode
        When I open data/hints/html/simple.html
        And I set hints -> mode to number
        And I set hints -> auto-follow to never
        And I hint with args "all"
        # this actually presses the keys one by one
        And I press the key "follow me!"
        Then "Leaving mode KeyMode.hint (reason: followed)" should not be logged

    Scenario: Using hints -> auto-follow == 'never' in number mode
        When I open data/hints/html/simple.html
        And I set hints -> mode to number
        And I set hints -> auto-follow to never
        And I hint with args "all"
        # this actually presses the keys one by one
        And I press the key "follow me!"
        And I press the key "<Enter>"
        Then data/hello.txt should be loaded

    Scenario: Using hints -> auto-follow == 'always' in word mode
        When I open data/hints/html/simple.html
        And I set hints -> mode to word
        And I set hints -> auto-follow to always
        And I hint with args "all"
        Then data/hello.txt should be loaded

    Scenario: Using hints -> auto-follow == 'unique-match' in word mode
        When I open data/hints/html/simple.html
        And I set hints -> mode to word
        And I set hints -> auto-follow to unique-match
        And I hint with args "all"
        # the link gets "hello" as the hint
        And I press the key "h"
        Then data/hello.txt should be loaded

    Scenario: Using hints -> auto-follow == 'full-match' in word mode
        When I open data/hints/html/simple.html
        And I set hints -> mode to word
        And I set hints -> auto-follow to full-match
        And I hint with args "all"
        # this actually presses the keys one by one
        And I press the key "hello"
        Then data/hello.txt should be loaded

    Scenario: Using hints -> auto-follow == 'never' without Enter in word mode
        When I open data/hints/html/simple.html
        And I set hints -> mode to word
        And I set hints -> auto-follow to never
        And I hint with args "all"
        # this actually presses the keys one by one
        And I press the key "hello"
        Then "Leaving mode KeyMode.hint (reason: followed)" should not be logged

    Scenario: Using hints -> auto-follow == 'never' in word mode
        When I open data/hints/html/simple.html
        And I set hints -> mode to word
        And I set hints -> auto-follow to never
        And I hint with args "all"
        # this actually presses the keys one by one
        And I press the key "hello"
        And I press the key "<Enter>"
        Then data/hello.txt should be loaded
