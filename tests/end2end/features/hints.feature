# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Using hints

    # https://bugreports.qt.io/browse/QTBUG-58381
    Background:
        Given I clean up open tabs

    Scenario: Using :hint-follow outside of hint mode (issue 1105)
        When I run :hint-follow
        Then the error "hint-follow: This command is only allowed in hint mode, not normal." should be shown

    Scenario: Using :hint-follow with an invalid index.
        When I open data/hints/html/simple.html
        And I hint with args "links normal" and follow xyz
        Then the error "No hint xyz!" should be shown

    Scenario: Using :hint with invalid mode.
        When I run :hint --mode=foobar
        Then the error "Invalid mode: Invalid value 'foobar' - valid values: number, letter, word" should be shown

    Scenario: Switching tab between :hint and start_cb (issue 3892)
        When I open data/hints/html/simple.html
        And I open data/hints/html/simple.html in a new tab
        And I run :hint ;; tab-prev
        And I wait for regex "hints: .*|Current tab changed \(\d* -> \d*\) before _start_cb is run\." in the log
        # 'hints: .*' is logged when _start_cb is called before tab-prev (on
        # qtwebkit, _start_cb is called synchronously)
        And I run :hint-follow a
        Then the error "hint-follow: This command is only allowed in hint mode, not normal." should be shown

    ### Opening in current or new tab

    Scenario: Following a hint and force to open in current tab.
        When I open data/hints/link_blank.html
        And I hint with args "links current" and follow a
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - data/hello.txt (active)

    Scenario: Following a hint and allow to open in new tab.
        When I open data/hints/link_blank.html
        And I hint with args "links normal" and follow a
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - data/hints/link_blank.html
            - data/hello.txt

    Scenario: Following a hint to link with sub-element and force to open in current tab.
        When I open data/hints/link_span.html
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
        And I hint with args "-- all spawn -v (python-executable) -c ''" and follow a
        Then the message "Command exited successfully." should be shown

    Scenario: Using :hint spawn with flags (issue 797)
        When I open data/hints/html/simple.html
        And I hint with args "all spawn -v (python-executable) -c ''" and follow a
        Then the message "Command exited successfully." should be shown

    Scenario: Using :hint spawn with flags and --rapid (issue 797)
        When I open data/hints/html/simple.html
        And I hint with args "--rapid all spawn -v (python-executable) -c ''" and follow a
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

    Scenario: Using :hint userscript with a script which doesn't exist
        When I open data/hints/html/simple.html
        And I hint with args "all userscript (testdata)/does_not_exist" and follow a
        Then the error "Userscript '*' not found" should be shown

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

    Scenario: Yanking email address to clipboard
        When I run :debug-set-fake-clipboard
        And I open data/email_address.html
        And I hint with args "links yank" and follow a
        Then the clipboard should contain "nobody"

    Scenario: Yanking javascript link to clipboard
        When I run :debug-set-fake-clipboard
        And I open data/hints/html/javascript.html
        And I hint with args "links yank" and follow a
        Then the clipboard should contain "javascript:window.location.href='/data/hello.txt'"

    Scenario: Rapid yanking
        When I run :debug-set-fake-clipboard
        And I open data/hints/rapid.html
        And I hint with args "links yank --rapid"
        And I run :hint-follow a
        And I run :hint-follow s
        And I run :mode-leave
        Then the clipboard should contain "http://localhost:(port)/data/hello.txt(linesep)http://localhost:(port)/data/hello2.txt"

    Scenario: Rapid hinting
        When I open data/hints/rapid.html in a new tab
        And I run :tab-only
        And I hint with args "all tab-bg --rapid"
        And I run :hint-follow a
        And I run :hint-follow s
        And I run :mode-leave
        And I wait until data/hello.txt is loaded
        And I wait until data/hello2.txt is loaded
        # We should check what the active tab is, but for some reason that makes
        # the test flaky
        Then the session should look like:
          windows:
          - tabs:
            - history:
              - url: http://localhost:*/data/hints/rapid.html
            - history:
              - url: http://localhost:*/data/hello.txt
            - history:
              - url: http://localhost:*/data/hello2.txt

    Scenario: Using hint --rapid to hit multiple buttons
        When I open data/hints/buttons.html
        And I hint with args "--rapid"
        And I run :hint-follow s
        And I run :hint-follow d
        And I run :hint-follow f
        Then the javascript message "beep!" should be logged
        And the javascript message "bop!" should be logged
        And the javascript message "boop!" should be logged

    Scenario: Using :hint run with a URL containing spaces
        When I open data/hints/html/with_spaces.html
        And I hint with args "all run message-info {hint-url}" and follow a
        Then the message "http://localhost:(port)/data/hello.txt" should be shown

    Scenario: Hinting inputs without type
        When I open data/hints/input.html
        And I hint with args "inputs" and follow a
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :mode-leave
        # The actual check is already done above
        Then no crash should happen

    Scenario: Error with invalid hint group
        When I open data/hints/buttons.html
        And I run :hint INVALID_GROUP
        Then the error "Undefined hinting group 'INVALID_GROUP'" should be shown

    Scenario: Custom hint group
        When I open data/hints/custom_group.html
        And I set hints.selectors to {"custom":[".clickable"]}
        And I hint with args "custom" and follow a
        Then the javascript message "beep!" should be logged

    Scenario: Custom hint group with URL pattern
        When I open data/hints/custom_group.html
        And I run :set -tu *://*/data/hints/custom_group.html hints.selectors '{"custom": [".clickable"]}'
        And I hint with args "custom" and follow a
        Then the javascript message "beep!" should be logged

    Scenario: Fallback to global value with URL pattern set
        When I open data/hints/custom_group.html
        And I set hints.selectors to {"custom":[".clickable"]}
        And I run :set -tu *://*/data/hints/custom_group.html hints.selectors '{"other": [".other"]}'
        And I hint with args "custom" and follow a
        Then the javascript message "beep!" should be logged

    @qtwebkit_skip
    Scenario: Invalid custom selector
        When I open data/hints/custom_group.html
        And I set hints.selectors to {"custom":["@"]}
        And I run :hint custom
        Then the error "SyntaxError: Failed to execute 'querySelectorAll' on 'Document': '@' is not a valid selector." should be shown

    # https://github.com/qutebrowser/qutebrowser/issues/1613
    Scenario: Hinting inputs with padding
        When I open data/hints/input.html
        And I hint with args "inputs" and follow s
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :mode-leave
        # The actual check is already done above
        Then no crash should happen

    Scenario: Hinting with ACE editor
        When I open data/hints/ace/ace.html
        And I hint with args "inputs" and follow a
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :mode-leave
        # The actual check is already done above
        Then no crash should happen

    Scenario: Hinting Twitter bootstrap checkbox
        When I open data/hints/bootstrap/checkbox.html
        And I hint with args "all" and follow a
        # The actual check is already done above
        Then "No elements found." should not be logged

    Scenario: Clicking input with existing text
        When I open data/hints/input.html
        And I run :click-element id qute-input-existing
        And I wait for "Entering mode KeyMode.insert *" in the log
        And I run :fake-key new
        Then the javascript message "contents: existingnew" should be logged

    ### iframes
    Scenario: Using :hint-follow inside an iframe
        When I open data/hints/iframe.html
        And I hint with args "links normal" and follow a
        Then "navigation request: url http://localhost:*/data/hello.txt, type Type.link_clicked, *" should be logged

    Scenario: Using :hint-follow inside an iframe button
        When I open data/hints/iframe_button.html
        And I hint with args "all normal" and follow s
        Then "navigation request: url http://localhost:*/data/hello.txt, *" should be logged

    Scenario: Hinting inputs in an iframe without type
        When I open data/hints/iframe_input.html
        And I hint with args "inputs" and follow a
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :mode-leave
        # The actual check is already done above
        Then no crash should happen

    @flaky  # FIXME https://github.com/qutebrowser/qutebrowser/issues/1525
    Scenario: Using :hint-follow inside a scrolled iframe
        When I open data/hints/iframe_scroll.html
        And I hint with args "all normal" and follow a
        And I run :scroll bottom
        And I hint with args "links normal" and follow a
        Then "navigation request: url http://localhost:*/data/hello2.txt, type Type.link_clicked, *" should be logged

    Scenario: Opening a link inside a specific iframe
        When I open data/hints/iframe_target.html
        And I hint with args "links normal" and follow a
        Then "navigation request: url http://localhost:*/data/hello.txt, type Type.link_clicked, *" should be logged

    Scenario: Opening a link with specific target frame in a new tab
        When I open data/hints/iframe_target.html
        And I run :tab-only
        And I hint with args "links tab" and follow s
        And I wait until data/hello2.txt is loaded
        Then the following tabs should be open:
            - data/hints/iframe_target.html (active)
            - data/hello2.txt

    Scenario: Clicking on iframe with :hint all current
        When I open data/hints/iframe.html
        And I hint with args "all current" and follow a
        Then no crash should happen

    Scenario: No error when hinting ranged input in frames
        When I open data/hints/issue3711_frame.html
        And I hint with args "all current" and follow a
        Then no crash should happen

    ### hints.auto_follow.timeout

    @not_mac @flaky
    Scenario: Ignoring key presses after auto-following hints
        When I set hints.auto_follow_timeout to 1000
        And I set hints.mode to number
        And I run :bind , message-error "This error message was triggered via a keybinding which should have been inhibited"
        And I open data/hints/html/simple.html
        And I hint with args "all"
        And I press the key "f"
        And I wait until data/hello.txt is loaded
        And I press the key ","
        # Waiting here so we don't affect the next test
        And I wait for "NormalKeyParser for mode normal: Releasing inhibition state of normal mode." in the log
        Then "NormalKeyParser for mode normal: Ignoring key ',', because the normal mode is currently inhibited." should be logged

    Scenario: Turning off auto_follow_timeout
        When I set hints.auto_follow_timeout to 0
        And I set hints.mode to number
        And I run :bind , message-info "Keypress worked!"
        And I open data/hints/html/simple.html
        And I hint with args "all"
        And I press the key "f"
        And I wait until data/hello.txt is loaded
        And I press the key ","
        Then the message "Keypress worked!" should be shown

    ### Word hints

    Scenario: Hinting with a too short dictionary
        When I open data/hints/short_dict.html
        And I set hints.mode to word
        # Test letter fallback
        And I hint with args "all" and follow d
        Then the error "Not enough words in the dictionary." should be shown
        And data/numbers/5.txt should be loaded

    Scenario: Dictionary file does not exist
        When I open data/hints/html/simple.html
        And I set hints.dictionary to no_words
        And I set hints.mode to word
        And I run :hint
        And I wait for "hints: *" in the log
        And I press the key "a"
        Then the error "Word hints requires reading the file at *" should be shown
        And data/hello.txt should be loaded

    ### Number hint mode

    # https://github.com/qutebrowser/qutebrowser/issues/308
    Scenario: Renumbering hints when filtering
        When I open data/hints/number.html
        And I set hints.mode to number
        And I hint with args "all"
        And I press the key "s"
        And I wait for "Filtering hints on 's'" in the log
        And I run :hint-follow 1
        Then data/numbers/7.txt should be loaded

    # https://github.com/qutebrowser/qutebrowser/issues/576
    @qtwebengine_flaky
    Scenario: Keeping hint filter in rapid mode
        When I open data/hints/number.html
        And I set hints.mode to number
        And I hint with args "all tab-bg --rapid"
        And I press the key "t"
        And I run :hint-follow 0
        And I run :hint-follow 1
        Then data/numbers/2.txt should be loaded
        And data/numbers/3.txt should be loaded

    # https://github.com/qutebrowser/qutebrowser/issues/1186
    Scenario: Keeping hints filter when using backspace
        When I open data/hints/issue1186.html
        And I set hints.mode to number
        And I hint with args "all"
        And I press the key "x"
        And I press the key "0"
        And I press the key "<Backspace>"
        And I run :hint-follow 11
        Then the error "No hint 11!" should be shown

    # https://github.com/qutebrowser/qutebrowser/issues/674#issuecomment-165096744
    Scenario: Multi-word matching
        When I open data/hints/number.html
        And I set hints.mode to number
        And I set hints.auto_follow to unique-match
        And I set hints.auto_follow_timeout to 0
        And I hint with args "all"
        And I press the keys "ten p"
        Then data/numbers/11.txt should be loaded

    Scenario: Scattering is ignored with number hints
        When I open data/hints/number.html
        And I set hints.mode to number
        And I set hints.scatter to true
        And I hint with args "all" and follow 00
        Then data/numbers/1.txt should be loaded

    # https://github.com/qutebrowser/qutebrowser/issues/1559
    Scenario: Filtering all hints in number mode
        When I open data/hints/number.html
        And I set hints.mode to number
        And I hint with args "all"
        And I press the key "2"
        And I wait for "Leaving mode KeyMode.hint (reason: all filtered)" in the log
        Then no crash should happen

    # https://github.com/qutebrowser/qutebrowser/issues/1657
    Scenario: Using rapid number hinting twice
        When I open data/hints/number.html
        And I set hints.mode to number
        And I hint with args "--rapid"
        And I run :mode-leave
        And I hint with args "--rapid" and follow 00
        Then data/numbers/1.txt should be loaded

    Scenario: Changing rapid hint filter after selecting hint
        When I open data/hints/number.html
        And I set hints.mode to number
        And I hint with args "all tab-bg --rapid "
        And I press the key "e"
        And I press the key "2"
        And I press the key "<Backspace>"
        And I press the key "o"
        And I press the key "0"
        Then data/numbers/1.txt should be loaded

    Scenario: Using a specific hints mode
        When I open data/hints/number.html
        And I set hints.mode to letter
        And I hint with args "--mode number all"
        And I press the key "s"
        And I wait for "Filtering hints on 's'" in the log
        And I run :hint-follow 1
        Then data/numbers/7.txt should be loaded

    ### hints.leave_on_load
    Scenario: Leaving hint mode on reload
        When I set hints.leave_on_load to true
        And I open data/hints/html/wrapped.html
        And I hint with args "all"
        And I run :reload
        Then "Leaving mode KeyMode.hint (reason: load started)" should be logged

    Scenario: Leaving hint mode on reload without leave_on_load
        When I set hints.leave_on_load to false
        And I open data/hints/html/simple.html
        And I hint with args "all"
        And I run :reload
        Then "Leaving mode KeyMode.hint (reason: load started)" should not be logged


    ### hints.auto_follow option

    Scenario: Using hints.auto_follow = 'always' in letter mode
        When I open data/hints/html/simple.html
        And I set hints.mode to letter
        And I set hints.auto_follow to always
        And I hint with args "all"
        Then data/hello.txt should be loaded

    # unique-match is actually the same as full-match in letter mode
    Scenario: Using hints.auto_follow = 'unique-match' in letter mode
        When I open data/hints/html/simple.html
        And I set hints.mode to letter
        And I set hints.auto_follow to unique-match
        And I hint with args "all"
        And I press the key "a"
        Then data/hello.txt should be loaded

    Scenario: Using hints.auto_follow = 'full-match' in letter mode
        When I open data/hints/html/simple.html
        And I set hints.mode to letter
        And I set hints.auto_follow to full-match
        And I hint with args "all"
        And I press the key "a"
        Then data/hello.txt should be loaded

    Scenario: Using hints.auto_follow = 'never' without Enter in letter mode
        When I open data/hints/html/simple.html
        And I set hints.mode to letter
        And I set hints.auto_follow to never
        And I hint with args "all"
        And I press the key "a"
        Then "Leaving mode KeyMode.hint (reason: followed)" should not be logged

    Scenario: Using hints.auto_follow = 'never' in letter mode
        When I open data/hints/html/simple.html
        And I set hints.mode to letter
        And I set hints.auto_follow to never
        And I hint with args "all"
        And I press the key "a"
        And I press the key "<Enter>"
        Then data/hello.txt should be loaded

    Scenario: Using hints.auto_follow = 'always' in number mode
        When I open data/hints/html/simple.html
        And I set hints.mode to number
        And I set hints.auto_follow to always
        And I hint with args "all"
        Then data/hello.txt should be loaded

    Scenario: Using hints.auto_follow = 'unique-match' in number mode
        When I open data/hints/html/simple.html
        And I set hints.mode to number
        And I set hints.auto_follow to unique-match
        And I hint with args "all"
        And I press the key "f"
        Then data/hello.txt should be loaded

    Scenario: Using hints.auto_follow = 'full-match' in number mode
        When I open data/hints/html/simple.html
        And I set hints.mode to number
        And I set hints.auto_follow to full-match
        And I hint with args "all"
        # this actually presses the keys one by one
        And I press the key "follow me!"
        Then data/hello.txt should be loaded

    Scenario: Using hints.auto_follow = 'never' without Enter in number mode
        When I open data/hints/html/simple.html
        And I set hints.mode to number
        And I set hints.auto_follow to never
        And I hint with args "all"
        # this actually presses the keys one by one
        And I press the key "follow me!"
        Then "Leaving mode KeyMode.hint (reason: followed)" should not be logged

    Scenario: Using hints.auto_follow = 'never' in number mode
        When I open data/hints/html/simple.html
        And I set hints.mode to number
        And I set hints.auto_follow to never
        And I hint with args "all"
        # this actually presses the keys one by one
        And I press the key "follow me!"
        And I press the key "<Enter>"
        Then data/hello.txt should be loaded

    Scenario: Using hints.auto_follow = 'always' in word mode
        When I open data/hints/html/simple.html
        And I set hints.mode to word
        And I set hints.auto_follow to always
        And I hint with args "all"
        Then data/hello.txt should be loaded

    Scenario: Using hints.auto_follow = 'unique-match' in word mode
        When I open data/hints/html/simple.html
        And I set hints.mode to word
        And I set hints.auto_follow to unique-match
        And I hint with args "all"
        # the link gets "hello" as the hint
        And I press the key "h"
        Then data/hello.txt should be loaded

    Scenario: Using hints.auto_follow = 'full-match' in word mode
        When I open data/hints/html/simple.html
        And I set hints.mode to word
        And I set hints.auto_follow to full-match
        And I hint with args "all"
        # this actually presses the keys one by one
        And I press the key "hello"
        Then data/hello.txt should be loaded

    Scenario: Using hints.auto_follow = 'never' without Enter in word mode
        When I open data/hints/html/simple.html
        And I set hints.mode to word
        And I set hints.auto_follow to never
        And I hint with args "all"
        # this actually presses the keys one by one
        And I press the key "hello"
        Then "Leaving mode KeyMode.hint (reason: followed)" should not be logged

    Scenario: Using hints.auto_follow = 'never' in word mode
        When I open data/hints/html/simple.html
        And I set hints.mode to word
        And I set hints.auto_follow to never
        And I hint with args "all"
        # this actually presses the keys one by one
        And I press the key "hello"
        And I press the key "<Enter>"
        Then data/hello.txt should be loaded

    ## Other

    Scenario: Using --first with normal links
        When I open data/hints/html/simple.html
        And I hint with args "all --first"
        Then data/hello.txt should be loaded

    Scenario: Using --first with inputs
        When I open data/hints/input.html
        And I hint with args "inputs --first"
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        # ensure we clicked the first element
        And I run :jseval console.log(document.activeElement.id == "qute-input");
        And I run :mode-leave
        Then the javascript message "true" should be logged

    Scenario: Hinting contenteditable inputs
        When I open data/hints/input.html
        And I hint with args "inputs" and follow f
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :mode-leave
        # The actual check is already done above
        Then no crash should happen

    Scenario: Deleting a simple target
        When I open data/hints/html/simple.html
        And I hint with args "all delete" and follow a
        And I run :hint
        Then the error "No elements found." should be shown

    Scenario: Statusbar text when entering hint mode from other mode
        When I open data/hints/html/simple.html
        And I run :mode-enter insert
        And I hint with args "all"
        And I run :debug-pyeval objreg.get('main-window', window='current', scope='window').status.txt.text()
        # Changing tabs will leave hint mode
        And I wait until qute://pyeval/ is loaded
        Then the page should contain the plaintext "'Follow hint...'"
