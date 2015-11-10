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
