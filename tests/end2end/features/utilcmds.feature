Feature: Miscellaneous utility commands exposed to the user.

    Background:
        Given I open data/scroll/simple.html
        And I run :tab-only
        And I run :window-only

    ## :cmd-later

    Scenario: :cmd-later before
        When I run :cmd-later 500 scroll down
        Then the page should not be scrolled
        # wait for scroll to execute so we don't ruin our future
        And the page should be scrolled vertically

    Scenario: :cmd-later after
        When I run :cmd-later 500 scroll down
        And I wait 0.6s
        Then the page should be scrolled vertically

    # for some reason, argparser gives us the error instead, see #2046
    @xfail
    Scenario: :cmd-later with negative delay
        When I run :cmd-later -1 scroll down
        Then the error "I can't run something in the past!" should be shown

    Scenario: :cmd-later with humongous delay
        When I run :cmd-later 36893488147419103232 scroll down
        Then the error "Numeric argument is too large for internal int representation." should be shown

    ## :cmd-repeat

    Scenario: :cmd-repeat simple
        When I run :cmd-repeat 2 message-info repeat-test
        Then the message "repeat-test" should be shown
        And the message "repeat-test" should be shown

    Scenario: :cmd-repeat zero times
        When I run :cmd-repeat 0 message-error "repeat-test 2"
        # If we have an error, the test will fail
        Then no crash should happen

    Scenario: :cmd-repeat with count
        When I run :cmd-repeat 3 message-info "repeat-test 3" with count 2
        Then the message "repeat-test 3" should be shown
        And the message "repeat-test 3" should be shown
        And the message "repeat-test 3" should be shown
        And the message "repeat-test 3" should be shown
        And the message "repeat-test 3" should be shown
        And the message "repeat-test 3" should be shown

    ## :cmd-run-with-count

    Scenario: :cmd-run-with-count
        When I run :cmd-run-with-count 2 message-info "run-with-count test"
        Then the message "run-with-count test" should be shown
        And the message "run-with-count test" should be shown

    Scenario: :cmd-run-with-count with count
        When I run :cmd-run-with-count 2 message-info "run-with-count test 2" with count 2
        Then the message "run-with-count test 2" should be shown
        And the message "run-with-count test 2" should be shown
        And the message "run-with-count test 2" should be shown
        And the message "run-with-count test 2" should be shown

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

    # argparser again
    @xfail
    Scenario: :cmd-repeat negative times
        When I run :cmd-repeat -4 scroll-px 10 0
        Then the error "A negative count doesn't make sense." should be shown
        And the page should not be scrolled

    ## :debug-all-objects

    Scenario: :debug-all-objects
        When I run :debug-all-objects
        Then "*Qt widgets - *Qt objects - *" should be logged

    ## :debug-cache-stats

    Scenario: :debug-cache-stats
        When I run :debug-cache-stats
        Then "is_valid_prefix: CacheInfo(*)" should be logged
        And "_render_stylesheet: CacheInfo(*)" should be logged

    ## :debug-console

    @no_xvfb
    Scenario: :debug-console smoke test
        When I run :debug-console
        And I wait for "Focus object changed: <qutebrowser.misc.consolewidget.ConsoleLineEdit *>" in the log
        And I run :debug-console
        And I wait for "Focus object changed: *" in the log
        Then "initializing debug console" should be logged
        And "showing debug console" should be logged
        And "hiding debug console" should be logged
        And no crash should happen

    ## :cmd-repeat-last

    Scenario: :cmd-repeat-last
        When I run :message-info test1
        And I run :cmd-repeat-last
        Then the message "test1" should be shown
        And the message "test1" should be shown

    Scenario: :cmd-repeat-last with count
        When I run :message-info test2
        And I run :cmd-repeat-last with count 2
        Then the message "test2" should be shown
        And the message "test2" should be shown
        And the message "test2" should be shown

    Scenario: :cmd-repeat-last with not-normal command in between
        When I run :message-info test3
        And I run :prompt-accept
        And I run :cmd-repeat-last
        Then the message "test3" should be shown
        And the error "prompt-accept: This command is only allowed in prompt/yesno mode, not normal." should be shown
        And the error "prompt-accept: This command is only allowed in prompt/yesno mode, not normal." should be shown

    Scenario: :cmd-repeat-last with mode-switching command
        When I open data/hints/link_blank.html
        And I run :tab-only
        And I hint with args "all tab-fg"
        And I run :mode-leave
        And I run :cmd-repeat-last
        And I wait for "hints: *" in the log
        And I run :hint-follow a
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            """
            - data/hints/link_blank.html
            - data/hello.txt (active)
            """

    ## :debug-log-capacity

    Scenario: Using :debug-log-capacity
        When I run :debug-log-capacity 100
        And I run :message-info oldstuff
        And I run :cmd-repeat 20 message-info otherstuff
        And I run :message-info newstuff
        And I open qute://log
        Then the page should contain the plaintext "newstuff"
        And the page should not contain the plaintext "oldstuff"

   Scenario: Using :debug-log-capacity with negative capacity
       When I run :debug-log-capacity -1
       Then the error "Can't set a negative log capacity!" should be shown

    ## :debug-log-level / :debug-log-filter
    # Other :debug-log-{level,filter} features are tested in
    # unit/utils/test_log.py as using them would break end2end tests.

    Scenario: Using debug-log-filter with invalid filter
        When I run :debug-log-filter blah
        Then the error "Invalid log category blah - valid categories: statusbar, *" should be shown

    Scenario: Using debug-log-filter
        When I run :debug-log-filter commands,ipc,webview
        And I run :mode-enter insert
        And I run :debug-log-filter none
        And I run :mode-leave
        Then "Entering mode KeyMode.insert *" should not be logged
