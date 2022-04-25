# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Miscellaneous utility commands exposed to the user.

    Background:
        Given I open data/scroll/simple.html
        And I run :tab-only

    ## :later

    Scenario: :later before
        When I run :later 500 scroll down
        Then the page should not be scrolled
        # wait for scroll to execture so we don't ruin our future
        And the page should be scrolled vertically

    Scenario: :later after
        When I run :later 500 scroll down
        And I wait 0.6s
        Then the page should be scrolled vertically

    # for some reason, argparser gives us the error instead, see #2046
    @xfail
    Scenario: :later with negative delay
        When I run :later -1 scroll down
        Then the error "I can't run something in the past!" should be shown

    Scenario: :later with humongous delay
        When I run :later 36893488147419103232 scroll down
        Then the error "Numeric argument is too large for internal int representation." should be shown

    ## :repeat

    Scenario: :repeat simple
        When I run :repeat 2 message-info repeat-test
        Then the message "repeat-test" should be shown
        And the message "repeat-test" should be shown

    Scenario: :repeat zero times
        When I run :repeat 0 message-error "repeat-test 2"
        # If we have an error, the test will fail
        Then no crash should happen

    Scenario: :repeat with count
        When I run :repeat 3 message-info "repeat-test 3" with count 2
        Then the message "repeat-test 3" should be shown
        And the message "repeat-test 3" should be shown
        And the message "repeat-test 3" should be shown
        And the message "repeat-test 3" should be shown
        And the message "repeat-test 3" should be shown
        And the message "repeat-test 3" should be shown

    ## :run-with-count

    Scenario: :run-with-count
        When I run :run-with-count 2 message-info "run-with-count test"
        Then the message "run-with-count test" should be shown
        And the message "run-with-count test" should be shown

    Scenario: :run-with-count with count
        When I run :run-with-count 2 message-info "run-with-count test 2" with count 2
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
    Scenario: :repeat negative times
        When I run :repeat -4 scroll-px 10 0
        Then the error "A negative count doesn't make sense." should be shown
        And the page should not be scrolled

    ## :debug-all-objects

    Scenario: :debug-all-objects
        When I run :debug-all-objects
        Then "*Qt widgets - *Qt objects - *" should be logged

    ## :debug-cache-stats

    @python>=3.9.0
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

    ## :repeat-command

    Scenario: :repeat-command
        When I run :message-info test1
        And I run :repeat-command
        Then the message "test1" should be shown
        And the message "test1" should be shown

    Scenario: :repeat-command with count
        When I run :message-info test2
        And I run :repeat-command with count 2
        Then the message "test2" should be shown
        And the message "test2" should be shown
        And the message "test2" should be shown

    Scenario: :repeat-command with not-normal command in between
        When I run :message-info test3
        And I run :prompt-accept
        And I run :repeat-command
        Then the message "test3" should be shown
        And the error "prompt-accept: This command is only allowed in prompt/yesno mode, not normal." should be shown
        And the error "prompt-accept: This command is only allowed in prompt/yesno mode, not normal." should be shown

    Scenario: :repeat-command with mode-switching command
        When I open data/hints/link_blank.html
        And I run :tab-only
        And I hint with args "all tab-fg"
        And I run :mode-leave
        And I run :repeat-command
        And I wait for "hints: *" in the log
        And I run :hint-follow a
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - data/hints/link_blank.html
            - data/hello.txt (active)

    ## :debug-log-capacity

    Scenario: Using :debug-log-capacity
        When I run :debug-log-capacity 100
        And I run :message-info oldstuff
        And I run :repeat 20 message-info otherstuff
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
