Feature: Yanking and pasting.
    :yank and :paste can be used to copy/paste the URL or title from/to the
    clipboard and primary selection.

    Background:
        Given I run :tab-only

    #### :yank

    Scenario: Yanking URLs to clipboard
        When I open data/title.html
        And I run :yank
        Then the message "Yanked URL to clipboard: http://localhost:(port)/data/title.html" should be shown
        And the clipboard should contain "http://localhost:(port)/data/title.html"

    Scenario: Yanking URLs to primary selection
        When selection is supported
        And I open data/title.html
        And I run :yank --sel
        Then the message "Yanked URL to primary selection: http://localhost:(port)/data/title.html" should be shown
        And the primary selection should contain "http://localhost:(port)/data/title.html"

    Scenario: Yanking title to clipboard
        When I open data/title.html
        And I wait for regex "Changing title for idx \d to 'Test title'" in the log
        And I run :yank --title
        Then the message "Yanked title to clipboard: Test title" should be shown
        And the clipboard should contain "Test title"

    Scenario: Yanking domain to clipboard
        When I open data/title.html
        And I run :yank --domain
        Then the message "Yanked domain to clipboard: http://localhost:(port)" should be shown
        And the clipboard should contain "http://localhost:(port)"

    Scenario: Yanking fully encoded URL
        When I open data/title with spaces.html
        And I run :yank
        Then the message "Yanked URL to clipboard: http://localhost:(port)/data/title%20with%20spaces.html" should be shown
        And the clipboard should contain "http://localhost:(port)/data/title%20with%20spaces.html"

    Scenario: Yanking pretty decoded URL
        When I open data/title with spaces.html
        And I run :yank --pretty
        Then the message "Yanked URL to clipboard: http://localhost:(port)/data/title with spaces.html" should be shown
        And the clipboard should contain "http://localhost:(port)/data/title with spaces.html"

    #### :paste

    Scenario: Pasting a URL
        When I put "http://localhost:(port)/data/hello.txt" into the clipboard
        And I run :paste
        And I wait until data/hello.txt is loaded
        Then the requests should be:
            data/hello.txt

    Scenario: Pasting a URL from primary selection
        When selection is supported
        And I put "http://localhost:(port)/data/hello2.txt" into the primary selection
        And I run :paste --sel
        And I wait until data/hello2.txt is loaded
        Then the requests should be:
            data/hello2.txt

    Scenario: Pasting with empty clipboard
        When I put "" into the clipboard
        And I run :paste
        Then the error "Clipboard is empty." should be shown

    Scenario: Pasting with empty selection
        When selection is supported
        And I put "" into the primary selection
        And I run :paste --sel
        Then the error "Primary selection is empty." should be shown

    Scenario: Pasting with a space in clipboard
        When I put " " into the clipboard
        And I run :paste
        Then the error "Clipboard is empty." should be shown

    Scenario: Pasting in a new tab
        Given I open about:blank
        When I run :tab-only
        And I put "http://localhost:(port)/data/hello.txt" into the clipboard
        And I run :paste -t
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - about:blank
            - data/hello.txt (active)

    Scenario: Pasting in a background tab
        Given I open about:blank
        When I run :tab-only
        And I put "http://localhost:(port)/data/hello.txt" into the clipboard
        And I run :paste -b
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - about:blank (active)
            - data/hello.txt

    Scenario: Pasting in a new window
        Given I have a fresh instance
        When I put "http://localhost:(port)/data/hello.txt" into the clipboard
        And I run :paste -w
        And I wait until data/hello.txt is loaded
        Then the session should look like:
            windows:
            - tabs:
              - active: true
                history:
                - active: true
                  url: about:blank
            - tabs:
              - active: true
                history:
                - active: true
                  url: http://localhost:*/data/hello.txt

    Scenario: Pasting an invalid URL
        When I set general -> auto-search to false
        And I put "foo bar" into the clipboard
        And I run :paste
        Then the error "Invalid URL" should be shown

    Scenario: Pasting multiple urls in a new tab
        Given I have a fresh instance
        When I put the following lines into the clipboard:
            http://localhost:(port)/data/hello.txt
            http://localhost:(port)/data/hello2.txt
            http://localhost:(port)/data/hello3.txt
        And I run :paste -t
        And I wait until data/hello.txt is loaded
        And I wait until data/hello2.txt is loaded
        And I wait until data/hello3.txt is loaded
        Then the following tabs should be open:
            - about:blank
            - data/hello.txt (active)
            - data/hello2.txt
            - data/hello3.txt

    Scenario: Pasting multiline text
        Given I have a fresh instance
        When I set searchengines -> DEFAULT to http://localhost:(port)/data/hello.txt?q={}
        And I put the following lines into the clipboard:
            this url:
            http://qutebrowser.org
            should not open
        And I run :paste -t
        And I wait until data/hello.txt?q=this%20url%3A%0Ahttp%3A//qutebrowser.org%0Ashould%20not%20open is loaded
        Then the following tabs should be open:
            - about:blank
            - data/hello.txt?q=this%20url%3A%0Ahttp%3A//qutebrowser.org%0Ashould%20not%20open (active)

    Scenario: Pasting multiline whose first line looks like a URI
        Given I open about:blank
        When I run :tab-only
        When I set searchengines -> DEFAULT to http://localhost:(port)/data/hello.txt?q={}
        And I put the following lines into the clipboard:
            text:
            should open
            as search
        And I run :paste -t
        And I wait until data/hello.txt?q=text%3A%0Ashould%20open%0Aas%20search is loaded
        Then the following tabs should be open:
            - about:blank
            - data/hello.txt?q=text%3A%0Ashould%20open%0Aas%20search (active)

    Scenario: Pasting multiple urls in a background tab
        Given I open about:blank
        When I run :tab-only
        And I put the following lines into the clipboard:
            http://localhost:(port)/data/hello.txt
            http://localhost:(port)/data/hello2.txt
            http://localhost:(port)/data/hello3.txt
        And I run :paste -b
        And I wait until data/hello.txt is loaded
        And I wait until data/hello2.txt is loaded
        And I wait until data/hello3.txt is loaded
        Then the following tabs should be open:
            - about:blank (active)
            - data/hello.txt
            - data/hello2.txt
            - data/hello3.txt

    Scenario: Pasting multiple urls in new windows
        Given I have a fresh instance
        When I put the following lines into the clipboard:
            http://localhost:(port)/data/hello.txt
            http://localhost:(port)/data/hello2.txt
            http://localhost:(port)/data/hello3.txt
        And I run :paste -w
        And I wait until data/hello.txt is loaded
        And I wait until data/hello2.txt is loaded
        And I wait until data/hello3.txt is loaded
        Then the session should look like:
            windows:
            - tabs:
              - active: true
                history:
                - active: true
                  url: about:blank
            - tabs:
              - active: true
                history:
                - active: true
                  url: http://localhost:*/data/hello.txt
            - tabs:
              - active: true
                history:
                - active: true
                  url: http://localhost:*/data/hello2.txt
            - tabs:
              - active: true
                history:
                - active: true
                  url: http://localhost:*/data/hello3.txt

    Scenario: Pasting multiple urls with an empty one
        When I open about:blank
        And I put "http://localhost:(port)/data/hello.txt\n\nhttp://localhost:(port)/data/hello2.txt" into the clipboard
        And I run :paste -t
        Then no crash should happen

    Scenario: Pasting multiple urls with an almost empty one
        When I open about:blank
        And I put "http://localhost:(port)/data/hello.txt\n \nhttp://localhost:(port)/data/hello2.txt" into the clipboard
        And I run :paste -t
        Then no crash should happen

    #### :paste-primary

    Scenario: Pasting the primary selection into an empty text field
        When selection is supported
        And I open data/paste_primary.html
        And I put "Hello world" into the primary selection
        # Click the text field
        And I run :hint all
        And I run :follow-hint a
        And I wait for "Clicked editable element!" in the log
        And I run :paste-primary
        # Compare
        Then the text field should contain "Hello world"

    Scenario: Pasting the primary selection into a text field at specific position
        When selection is supported
        And I open data/paste_primary.html
        And I set the text field to "one two three four"
        And I put " Hello world" into the primary selection
        # Click the text field
        And I run :hint all
        And I run :follow-hint a
        And I wait for "Clicked editable element!" in the log
        # Move to the beginning and two words to the right
        And I press the keys "<Home>"
        And I press the key "<Ctrl+Right>"
        And I press the key "<Ctrl+Right>"
        And I run :paste-primary
        # Compare
        Then the text field should contain "one two Hello world three four"

    Scenario: Pasting the primary selection into a text field with undo
        When selection is supported
        And I open data/paste_primary.html
        # Click the text field
        And I run :hint all
        And I run :follow-hint a
        And I wait for "Clicked editable element!" in the log
        # Paste and undo
        And I put "This text should be undone" into the primary selection
        And I run :paste-primary
        And I press the key "<Ctrl+z>"
        # Paste final text
        And I put "This text should stay" into the primary selection
        And I run :paste-primary
        # Compare
        Then the text field should contain "This text should stay"

    Scenario: Pasting the primary selection without a focused field
        When selection is supported
        And I open data/paste_primary.html
        And I put "test" into the primary selection
        And I run :enter-mode insert
        And I run :paste-primary
        Then the error "No element focused!" should be shown

    Scenario: Pasting the primary selection with a read-only field
        When selection is supported
        And I open data/paste_primary.html
        # Click the text field
        And I run :hint all
        And I run :follow-hint s
        And I wait for "Clicked non-editable element!" in the log
        And I put "test" into the primary selection
        And I run :enter-mode insert
        And I run :paste-primary
        Then the error "Focused element is not editable!" should be shown

    Scenario: :paste-primary without primary selection supported
        When selection is not supported
        And I open data/paste_primary.html
        And I put "Hello world" into the clipboard
        # Click the text field
        And I run :hint all
        And I run :follow-hint a
        And I wait for "Clicked editable element!" in the log
        And I run :paste-primary
        # Compare
        Then the text field should contain "Hello world"
