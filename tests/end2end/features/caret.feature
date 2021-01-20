# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Caret mode
    In caret mode, the user can select and yank text using the keyboard.

    Background:
        Given I open data/caret.html
        And I run :tab-only
        And I also run :mode-enter caret

    # :yank selection

    Scenario: :yank selection without selection
        When I run :yank selection
        Then the message "Nothing to yank" should be shown.

    Scenario: :yank selection message
        When I run :selection-toggle
        And I run :move-to-end-of-word
        And I run :yank selection
        Then the message "3 chars yanked to clipboard" should be shown.

    Scenario: :yank selection message with one char
        When I run :selection-toggle
        And I run :move-to-next-char
        And I run :yank selection
        Then the message "1 char yanked to clipboard" should be shown.

    Scenario: :yank selection with primary selection
        When selection is supported
        And I run :selection-toggle
        And I run :move-to-end-of-word
        And I run :yank selection --sel
        Then the message "3 chars yanked to primary selection" should be shown.
        And the primary selection should contain "one"

    Scenario: :yank selection with --keep
        When I run :selection-toggle
        And I run :move-to-end-of-word
        And I run :yank selection --keep
        And I run :move-to-end-of-word
        And I run :yank selection --keep
        Then the message "3 chars yanked to clipboard" should be shown.
        And the message "7 chars yanked to clipboard" should be shown.
        And the clipboard should contain "one two"

    # :selection-follow

    Scenario: :selection-follow with --tab (with JS)
        When I set content.javascript.enabled to true
        And I run :tab-only
        And I run :mode-enter caret
        And I run :selection-toggle
        And I run :move-to-end-of-word
        And I run :selection-follow --tab
        Then data/hello.txt should be loaded
        And the following tabs should be open:
            - data/caret.html
            - data/hello.txt (active)

    Scenario: :selection-follow with --tab (without JS)
        When I set content.javascript.enabled to false
        And I run :tab-only
        And I run :mode-enter caret
        And I run :selection-toggle
        And I run :move-to-end-of-word
        And I run :selection-follow --tab
        Then data/hello.txt should be loaded
        And the following tabs should be open:
            - data/caret.html
            - data/hello.txt

    @flaky
    Scenario: :selection-follow with link tabbing (without JS)
        When I set content.javascript.enabled to false
        And I run :mode-leave
        And I run :jseval document.activeElement.blur();
        And I run :fake-key <tab>
        And I run :selection-follow
        Then data/hello.txt should be loaded

    @flaky
    Scenario: :selection-follow with link tabbing (with JS)
        When I set content.javascript.enabled to true
        And I run :mode-leave
        And I run :jseval document.activeElement.blur();
        And I run :fake-key <tab>
        And I run :selection-follow
        Then data/hello.txt should be loaded

    @flaky
    Scenario: :selection-follow with link tabbing in a tab (without JS)
        When I set content.javascript.enabled to false
        And I run :mode-leave
        And I run :jseval document.activeElement.blur();
        And I run :fake-key <tab>
        And I run :selection-follow --tab
        Then data/hello.txt should be loaded

    @flaky
    Scenario: :selection-follow with link tabbing in a tab (with JS)
        When I set content.javascript.enabled to true
        And I run :mode-leave
        And I run :jseval document.activeElement.blur();
        And I run :fake-key <tab>
        And I run :selection-follow --tab
        Then data/hello.txt should be loaded
