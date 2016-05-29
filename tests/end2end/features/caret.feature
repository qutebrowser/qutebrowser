Feature: Caret mode
    In caret mode, the user can select and yank text using the keyboard.

    Background:
        Given I open data/caret.html
        And I run :tab-only ;; :enter-mode caret

    # document

    Scenario: Selecting the entire document
        When I run :toggle-selection
        And I run :move-to-end-of-document
        And I run :yank-selected
        Then the clipboard should contain:
            one two three
            eins zwei drei

            four five six
            vier fünf sechs

    Scenario: Moving to end and to start of document
        When I run :move-to-end-of-document
        And I run :move-to-start-of-document
        And I run :toggle-selection
        And I run :move-to-end-of-word
        And I run :yank-selected
        Then the clipboard should contain "one"

    Scenario: Moving to end and to start of document (with selection)
        When I run :move-to-end-of-document
        And I run :toggle-selection
        And I run :move-to-start-of-document
        And I run :yank-selected
        Then the clipboard should contain:
            one two three
            eins zwei drei

            four five six
            vier fünf sechs

    # block

    Scenario: Selecting a block
        When I run :toggle-selection
        And I run :move-to-end-of-next-block
        And I run :yank-selected
        Then the clipboard should contain:
            one two three
            eins zwei drei

    Scenario: Moving back to the end of previous block (with selection)
        When I run :move-to-end-of-next-block with count 2
        And I run :toggle-selection
        And I run :move-to-end-of-prev-block
        And I run :move-to-prev-word
        And I run :yank-selected
        Then the clipboard should contain:
            drei

            four five six

    Scenario: Moving back to the end of previous block
        When I run :move-to-end-of-next-block with count 2
        And I run :move-to-end-of-prev-block
        And I run :toggle-selection
        And I run :move-to-prev-word
        And I run :yank-selected
        Then the clipboard should contain "drei"

    Scenario: Moving back to the start of previous block (with selection)
        When I run :move-to-end-of-next-block with count 2
        And I run :toggle-selection
        And I run :move-to-start-of-prev-block
        And I run :yank-selected
        Then the clipboard should contain:
            eins zwei drei

            four five six

    Scenario: Moving back to the start of previous block
        When I run :move-to-end-of-next-block with count 2
        And I run :move-to-start-of-prev-block
        And I run :toggle-selection
        And I run :move-to-next-word
        And I run :yank-selected
        Then the clipboard should contain "eins "

    Scenario: Moving to the start of next block (with selection)
        When I run :toggle-selection
        And I run :move-to-start-of-next-block
        And I run :yank-selected
        Then the clipboard should contain "one two three\n"

    Scenario: Moving to the start of next block
        When I run :move-to-start-of-next-block
        And I run :toggle-selection
        And I run :move-to-end-of-word
        And I run :yank-selected
        Then the clipboard should contain "eins"

    # line

    Scenario: Selecting a line
        When I run :toggle-selection
        And I run :move-to-end-of-line
        And I run :yank-selected
        Then the clipboard should contain "one two three"

    Scenario: Moving and selecting a line
        When I run :move-to-next-line
        And I run :toggle-selection
        And I run :move-to-end-of-line
        And I run :yank-selected
        Then the clipboard should contain "eins zwei drei"

    Scenario: Selecting next line
        When I run :toggle-selection
        And I run :move-to-next-line
        And I run :yank-selected
        Then the clipboard should contain "one two three\n"

    Scenario: Moving to end and to start of line
        When I run :move-to-end-of-line
        And I run :move-to-start-of-line
        And I run :toggle-selection
        And I run :move-to-end-of-word
        And I run :yank-selected
        Then the clipboard should contain "one"

    Scenario: Selecting a line (backwards)
        When I run :move-to-end-of-line
        And I run :toggle-selection
        When I run :move-to-start-of-line
        And I run :yank-selected
        Then the clipboard should contain "one two three"

    Scenario: Selecting previous line
        When I run :move-to-next-line
        And I run :toggle-selection
        When I run :move-to-prev-line
        And I run :yank-selected
        Then the clipboard should contain "one two three\n"

    Scenario: Moving to previous line
        When I run :move-to-next-line
        When I run :move-to-prev-line
        And I run :toggle-selection
        When I run :move-to-next-line
        And I run :yank-selected
        Then the clipboard should contain "one two three\n"

    # word

    Scenario: Selecting a word
        When I run :toggle-selection
        And I run :move-to-end-of-word
        And I run :yank-selected
        Then the clipboard should contain "one"

    Scenario: Moving to end and selecting a word
        When I run :move-to-end-of-word
        And I run :toggle-selection
        And I run :move-to-end-of-word
        And I run :yank-selected
        Then the clipboard should contain " two"

    Scenario: Moving to next word and selecting a word
        When I run :move-to-next-word
        And I run :toggle-selection
        And I run :move-to-end-of-word
        And I run :yank-selected
        Then the clipboard should contain "two"

    Scenario: Moving to next word and selecting until next word
        When I run :move-to-next-word
        And I run :toggle-selection
        And I run :move-to-next-word
        And I run :yank-selected
        Then the clipboard should contain "two "

    Scenario: Moving to previous word and selecting a word
        When I run :move-to-end-of-word
        And I run :toggle-selection
        And I run :move-to-prev-word
        And I run :yank-selected
        Then the clipboard should contain "one"

    Scenario: Moving to previous word
        When I run :move-to-end-of-word
        And I run :move-to-prev-word
        And I run :toggle-selection
        And I run :move-to-end-of-word
        And I run :yank-selected
        Then the clipboard should contain "one"

    # char

    Scenario: Selecting a char
        When I run :toggle-selection
        And I run :move-to-next-char
        And I run :yank-selected
        Then the clipboard should contain "o"

    Scenario: Moving and selecting a char
        When I run :move-to-next-char
        And I run :toggle-selection
        And I run :move-to-next-char
        And I run :yank-selected
        Then the clipboard should contain "n"

    Scenario: Selecting previous char
        When I run :move-to-end-of-word
        And I run :toggle-selection
        And I run :move-to-prev-char
        And I run :yank-selected
        Then the clipboard should contain "e"

    Scenario: Moving to previous char
        When I run :move-to-end-of-word
        And I run :move-to-prev-char
        And I run :toggle-selection
        And I run :move-to-end-of-word
        And I run :yank-selected
        Then the clipboard should contain "e"

    # :yank-selected

    Scenario: :yank-selected without selection
        When I run :yank-selected
        Then the message "Nothing to yank" should be shown.

    Scenario: :yank-selected message
        When I run :toggle-selection
        And I run :move-to-end-of-word
        And I run :yank-selected
        Then the message "3 chars yanked to clipboard" should be shown.

    Scenario: :yank-selected message with one char
        When I run :toggle-selection
        And I run :move-to-next-char
        And I run :yank-selected
        Then the message "1 char yanked to clipboard" should be shown.

    Scenario: :yank-selected with primary selection
        When selection is supported
        And I run :toggle-selection
        And I run :move-to-end-of-word
        And I run :yank-selected --sel
        Then the message "3 chars yanked to primary selection" should be shown.
        And the primary selection should contain "one"

    Scenario: :yank-selected with --keep
        When I run :toggle-selection
        And I run :move-to-end-of-word
        And I run :yank-selected --keep
        And I run :move-to-end-of-word
        And I run :yank-selected --keep
        Then the message "3 chars yanked to clipboard" should be shown.
        And the message "7 chars yanked to clipboard" should be shown.
        And the clipboard should contain "one two"

    # :drop-selection

    Scenario: :drop-selection
        When I run :toggle-selection
        And I run :move-to-end-of-word
        And I run :drop-selection
        And I run :yank-selected
        Then the message "Nothing to yank" should be shown.

    # :follow-selected

    Scenario: :follow-selected without a selection
        When I run :follow-selected
        Then no crash should happen

    Scenario: :follow-selected with text
        When I run :move-to-next-word
        And I run :toggle-selection
        And I run :move-to-end-of-word
        And I run :follow-selected
        Then no crash should happen

    Scenario: :follow-selected with link (with JS)
        When I set content -> allow-javascript to true
        And I run :toggle-selection
        And I run :move-to-end-of-word
        And I run :follow-selected
        Then data/hello.txt should be loaded

    Scenario: :follow-selected with link (without JS)
        When I set content -> allow-javascript to false
        And I run :toggle-selection
        And I run :move-to-end-of-word
        And I run :follow-selected
        Then data/hello.txt should be loaded

    Scenario: :follow-selected with --tab (with JS)
        When I set content -> allow-javascript to true
        And I run :tab-only
        And I run :enter-mode caret
        And I run :toggle-selection
        And I run :move-to-end-of-word
        And I run :follow-selected --tab
        Then data/hello.txt should be loaded
        And the following tabs should be open:
            - data/caret.html
            - data/hello.txt (active)

    Scenario: :follow-selected with --tab (without JS)
        When I set content -> allow-javascript to false
        And I run :tab-only
        And I run :enter-mode caret
        And I run :toggle-selection
        And I run :move-to-end-of-word
        And I run :follow-selected --tab
        Then data/hello.txt should be loaded
        And the following tabs should be open:
            - data/caret.html
            - data/hello.txt (active)
