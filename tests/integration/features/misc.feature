Feature: Various utility commands.

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

    Scenario: :message-error
        When I run :message-error "Hello World"
        Then the error "Hello World" should be shown.

    Scenario: :message-info
        When I run :message-info "Hello World"
        Then the message "Hello World" should be shown.

    Scenario: :message-warning
        When I run :message-warning "Hello World"
        Then the warning "Hello World" should be shown.

    Scenario: :jseval
        When I set general -> log-javascript-console to true
        And I run :jseval console.log("Hello from JS!");
        And I wait for "[:0] Hello from JS!" in the log
        Then the message "No output or error" should be shown.
