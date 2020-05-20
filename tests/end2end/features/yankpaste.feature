# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Yanking and pasting.
    :yank, {clipboard} and {primary} can be used to copy/paste the URL or title
    from/to the clipboard and primary selection.

    Background:
        Given I clean up open tabs

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

    Scenario: Yanking URLs with ref and UTM parameters
        When I open data/title.html?utm_source=kikolani&utm_medium=320banner&utm_campaign=bpp&ref=facebook
        And I run :yank
        Then the message "Yanked URL to clipboard: http://localhost:(port)/data/title.html" should be shown
        And the clipboard should contain "http://localhost:(port)/data/title.html"

    Scenario: Yanking URLs with ref and UTM parameters and some other parameters
        When I open data/title.html?stype=models&utm_source=kikolani&utm_medium=320banner&utm_campaign=bpp&ref=facebook
        And I run :yank
        Then the message "Yanked URL to clipboard: http://localhost:(port)/data/title.html?stype=models" should be shown
        And the clipboard should contain "http://localhost:(port)/data/title.html?stype=models"

    Scenario: Yanking title to clipboard
        When I open data/title.html
        And I wait for regex "Changing title for idx \d to 'Test title'" in the log
        And I run :yank title
        Then the message "Yanked title to clipboard: Test title" should be shown
        And the clipboard should contain "Test title"

    Scenario: Yanking inline to clipboard
        When I open data/title.html
        And I run :yank inline '[[{url}][qutebrowser</3org]]'
        Then the message "Yanked inline block to clipboard: [[http://localhost:(port)/data/title.html][qutebrowser</3org]]" should be shown
        And the clipboard should contain "[[http://localhost:(port)/data/title.html][qutebrowser</3org]]"

    Scenario: Yanking domain to clipboard
        When I open data/title.html
        And I run :yank domain
        Then the message "Yanked domain to clipboard: http://localhost:(port)" should be shown
        And the clipboard should contain "http://localhost:(port)"

    Scenario: Yanking fully encoded URL
        When I open data/title with spaces.html
        And I run :yank
        Then the message "Yanked URL to clipboard: http://localhost:(port)/data/title%20with%20spaces.html" should be shown
        And the clipboard should contain "http://localhost:(port)/data/title%20with%20spaces.html"

    Scenario: Yanking pretty decoded URL
        When I open data/title with spaces.html
        And I run :yank pretty-url
        Then the message "Yanked URL to clipboard: http://localhost:(port)/data/title with spaces.html" should be shown
        And the clipboard should contain "http://localhost:(port)/data/title with spaces.html"

	Scenario: Yanking URL that has = and & in its query string
		When I open data/title.html?a=b&c=d
		And I run :yank
		Then the message "Yanked URL to clipboard: http://localhost:(port)/data/title.html?a=b&c=d" should be shown
		And the clipboard should contain "http://localhost:(port)/data/title.html?a=b&c=d"

	Scenario: Yanking URL that has = and ; in its query string
		When I open data/title.html?a=b;c=d
		And I run :yank
		Then the message "Yanked URL to clipboard: http://localhost:(port)/data/title.html?a=b;c=d" should be shown
		And the clipboard should contain "http://localhost:(port)/data/title.html?a=b;c=d"

	Scenario: Yanking URL with both & and ; in its query string
		When I open data/title.html?a;b&c=d
		And I run :yank
		Then the message "Yanked URL to clipboard: http://localhost:(port)/data/title.html?a;b&c=d" should be shown
		And the clipboard should contain "http://localhost:(port)/data/title.html?a;b&c=d"

    Scenario: Yanking with --quiet
        When I open data/title.html
        And I run :yank --quiet
        Then "Yanked URL to clipboard: *" should not be logged

    #### {clipboard} and {primary}

    Scenario: Pasting a URL
        When I put "http://localhost:(port)/data/hello.txt" into the clipboard
        And I run :open {clipboard}
        Then data/hello.txt should be loaded

    Scenario: Pasting a URL from primary selection
        When selection is supported
        And I put "http://localhost:(port)/data/hello2.txt" into the primary selection
        And I run :open {primary}
        Then data/hello2.txt should be loaded

    Scenario: Pasting with empty clipboard
        When I put "" into the clipboard
        And I run :open {clipboard} (invalid command)
        Then the error "Clipboard is empty." should be shown

    Scenario: Pasting with empty selection
        When selection is supported
        And I put "" into the primary selection
        And I run :open {primary} (invalid command)
        Then the error "Primary selection is empty." should be shown

    Scenario: Pasting without primary selection being supported
        When selection is not supported
        And I run :open {primary} (invalid command)
        Then the error "Primary selection is not supported on this platform!" should be shown

    Scenario: Pasting with a space in clipboard
        When I put " " into the clipboard
        And I run :open {clipboard} (invalid command)
        Then the error "Clipboard is empty." should be shown

    Scenario: Pasting in a new tab
        When I put "http://localhost:(port)/data/hello.txt" into the clipboard
        And I run :open -t {clipboard}
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - about:blank
            - data/hello.txt (active)

    Scenario: Pasting in a background tab
        When I put "http://localhost:(port)/data/hello.txt" into the clipboard
        And I run :open -b {clipboard}
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - about:blank (active)
            - data/hello.txt

    Scenario: Pasting in a new window
        When I put "http://localhost:(port)/data/hello.txt" into the clipboard
        And I run :open -w {clipboard}
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
        When I set url.auto_search to never
        And I put "foo bar" into the clipboard
        And I run :open {clipboard}
        Then the error "Invalid URL" should be shown

    # https://travis-ci.org/qutebrowser/qutebrowser/jobs/157941726
    @qtwebengine_flaky
    Scenario: Pasting multiple urls in a new tab
        When I put the following lines into the clipboard:
            http://localhost:(port)/data/hello.txt
            http://localhost:(port)/data/hello2.txt
            http://localhost:(port)/data/hello3.txt
        And I run :open -t {clipboard}
        And I wait until data/hello.txt is loaded
        And I wait until data/hello2.txt is loaded
        And I wait until data/hello3.txt is loaded
        Then the following tabs should be open:
            - about:blank
            - data/hello.txt (active)
            - data/hello2.txt
            - data/hello3.txt

    Scenario: Pasting multiline text
        When I set url.auto_search to naive
        And I set url.searchengines to {"DEFAULT": "http://localhost:(port)/data/hello.txt?q={}"}
        And I put the following lines into the clipboard:
            this url:
            http://qutebrowser.org
            should not open
        And I run :open -t {clipboard}
        And I wait until data/hello.txt?q=this%20url%3A%0Ahttp%3A//qutebrowser.org%0Ashould%20not%20open is loaded
        Then the following tabs should be open:
            - about:blank
            - data/hello.txt?q=this%20url%3A%0Ahttp%3A//qutebrowser.org%0Ashould%20not%20open (active)

    Scenario: Pasting multiline whose first line looks like a URI
        When I set url.auto_search to naive
        And I set url.searchengines to {"DEFAULT": "http://localhost:(port)/data/hello.txt?q={}"}
        And I put the following lines into the clipboard:
            text:
            should open
            as search
        And I run :open -t {clipboard}
        And I wait until data/hello.txt?q=text%3A%0Ashould%20open%0Aas%20search is loaded
        Then the following tabs should be open:
            - about:blank
            - data/hello.txt?q=text%3A%0Ashould%20open%0Aas%20search (active)

    # https://travis-ci.org/qutebrowser/qutebrowser/jobs/157941726
    @qtwebengine_flaky
    Scenario: Pasting multiple urls in a background tab
        When I put the following lines into the clipboard:
            http://localhost:(port)/data/hello.txt
            http://localhost:(port)/data/hello2.txt
            http://localhost:(port)/data/hello3.txt
        And I run :open -b {clipboard}
        And I wait until data/hello.txt is loaded
        And I wait until data/hello2.txt is loaded
        And I wait until data/hello3.txt is loaded
        Then the following tabs should be open:
            - about:blank (active)
            - data/hello.txt
            - data/hello2.txt
            - data/hello3.txt

    Scenario: Pasting multiple urls in new windows
        When I put the following lines into the clipboard:
            http://localhost:(port)/data/hello.txt
            http://localhost:(port)/data/hello2.txt
            http://localhost:(port)/data/hello3.txt
        And I run :open -w {clipboard}
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
        And I put "http://localhost:(port)/data/hello.txt\n\nhttp://localhost:(port)/data/hello2.txt" into the clipboard
        And I run :open -t {clipboard}
        Then no crash should happen

    Scenario: Pasting multiple urls with an almost empty one
        And I put "http://localhost:(port)/data/hello.txt\n \nhttp://localhost:(port)/data/hello2.txt" into the clipboard
        And I run :open -t {clipboard}
        Then no crash should happen

    #### :insert-text

    Scenario: Inserting text into an empty text field
        When I open data/paste_primary.html
        And I run :click-element id qute-textarea
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :insert-text Hello world
        # Compare
        Then the javascript message "textarea contents: Hello world" should be logged

    Scenario: Inserting text into an empty text field with javascript disabled
        When I set content.javascript.enabled to false
        And I open data/paste_primary.html
        And I run :click-element id qute-textarea
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        And I run :insert-text Hello world
        And I wait for "Inserting text into element *" in the log
        And I run :jseval console.log("textarea contents: " + document.getElementById('qute-textarea').value);
        # Enable javascript again for the other tests
        And I set content.javascript.enabled to true
        # Compare
        Then the javascript message "textarea contents: Hello world" should be logged

    Scenario: Inserting text into a text field at specific position
        When I open data/paste_primary.html
        And I insert "one two three four" into the text field
        And I run :click-element id qute-textarea
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        # Move to the beginning and two characters to the right
        And I press the keys "<Home>"
        And I press the key "<Right>"
        And I press the key "<Right>"
        And I run :insert-text Hello world
        # Compare
        Then the javascript message "textarea contents: onHello worlde two three four" should be logged

    Scenario: Inserting text into a text field with undo
        When I open data/paste_primary.html
        And I run :click-element id qute-textarea
        And I wait for "Entering mode KeyMode.insert (reason: clicking input)" in the log
        # Paste and undo
        And I run :insert-text This text should be undone
        And I wait for the javascript message "textarea contents: This text should be undone"
        And I press the key "<Ctrl+z>"
        And I wait for the javascript message "textarea contents: "
        # Paste final text
        And I run :insert-text This text should stay
        # Compare
        Then the javascript message "textarea contents: This text should stay" should be logged

    Scenario: Inserting text without a focused field
        When I open data/paste_primary.html
        And I run :enter-mode insert
        And I run :insert-text test
        Then the error "No element focused!" should be shown

    Scenario: Inserting text with a read-only field
        When I open data/paste_primary.html
        And I run :click-element id qute-textarea-noedit
        And I wait for "Clicked non-editable element!" in the log
        And I run :enter-mode insert
        And I run :insert-text test
        Then the error "Element is not editable!" should be shown
