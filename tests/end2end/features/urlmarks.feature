Feature: quickmarks and bookmarks

    ## bookmarks

    Scenario: Saving a bookmark
        When I open data/title.html
        And I run :bookmark-add
        Then the message "Bookmarked http://localhost:*/data/title.html!" should be shown
        And the bookmark file should contain "http://localhost:*/data/title.html Test title"

    Scenario: Saving a bookmark with a provided url and title
        When I run :bookmark-add http://example.com "some example title"
        Then the message "Bookmarked http://example.com!" should be shown
        And the bookmark file should contain "http://example.com some example title"

    Scenario: Saving a bookmark with a url but no title
        When I run :bookmark-add http://example.com
        Then the error "Title must be provided if url has been provided" should be shown

    Scenario: Saving a bookmark with an invalid url
        When I set general -> auto-search to false
        And I run :bookmark-add foo! "some example title"
        Then the error "Invalid URL" should be shown

    Scenario: Saving a duplicate bookmark
        Given I have a fresh instance
        When I open data/title.html
        And I run :bookmark-add
        And I run :bookmark-add
        Then the error "Bookmark already exists!" should be shown

    Scenario: Loading a bookmark
        When I run :tab-only
        And I run :bookmark-load http://localhost:(port)/data/numbers/1.txt
        Then data/numbers/1.txt should be loaded
        And the following tabs should be open:
            - data/numbers/1.txt (active)

    Scenario: Loading a bookmark in a new tab
        Given I open about:blank
        When I run :tab-only
        And I run :bookmark-load -t http://localhost:(port)/data/numbers/2.txt
        Then data/numbers/2.txt should be loaded
        And the following tabs should be open:
            - about:blank
            - data/numbers/2.txt (active)

    Scenario: Loading a bookmark in a background tab
        Given I open about:blank
        When I run :tab-only
        And I run :bookmark-load -b http://localhost:(port)/data/numbers/3.txt
        Then data/numbers/3.txt should be loaded
        And the following tabs should be open:
            - about:blank (active)
            - data/numbers/3.txt

    Scenario: Loading a bookmark in a new window
        Given I open about:blank
        When I run :tab-only
        And I run :bookmark-load -w http://localhost:(port)/data/numbers/4.txt
        And I wait until data/numbers/4.txt is loaded
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
                  url: http://localhost:*/data/numbers/4.txt

    Scenario: Loading a bookmark with -t and -b
        When I run :bookmark-load -t -b about:blank
        Then the error "Only one of -t/-b/-w can be given!" should be shown

    Scenario: Deleting a bookmark which does not exist
        When I run :bookmark-del doesnotexist
        Then the error "Bookmark 'doesnotexist' not found!" should be shown

    Scenario: Deleting a bookmark
        When I open data/numbers/5.txt
        And I run :bookmark-add
        And I run :bookmark-del http://localhost:(port)/data/numbers/5.txt
        Then the bookmark file should not contain "http://localhost:*/data/numbers/5.txt "

    ## quickmarks

    Scenario: Saving a quickmark (:quickmark-add)
        When I run :quickmark-add http://localhost:(port)/data/numbers/6.txt six
        Then the quickmark file should contain "six http://localhost:*/data/numbers/6.txt"

    Scenario: Saving a quickmark (:quickmark-save)
        When I open data/numbers/7.txt
        And I run :quickmark-save
        And I wait for "Entering mode KeyMode.prompt (reason: question asked)" in the log
        And I press the keys "seven"
        And I press the keys "<Enter>"
        Then the quickmark file should contain "seven http://localhost:*/data/numbers/7.txt"

    Scenario: Saving a duplicate quickmark (without override)
        When I run :quickmark-add http://localhost:(port)/data/numbers/8.txt eight
        And I run :quickmark-add http://localhost:(port)/data/numbers/8_2.txt eight
        And I wait for "Entering mode KeyMode.yesno (reason: question asked)" in the log
        And I run :prompt-no
        Then the quickmark file should contain "eight http://localhost:*/data/numbers/8.txt"

    Scenario: Saving a duplicate quickmark (with override)
        When I run :quickmark-add http://localhost:(port)/data/numbers/9.txt nine
        And I run :quickmark-add http://localhost:(port)/data/numbers/9_2.txt nine
        And I wait for "Entering mode KeyMode.yesno (reason: question asked)" in the log
        And I run :prompt-yes
        Then the quickmark file should contain "nine http://localhost:*/data/numbers/9_2.txt"

    Scenario: Adding a quickmark with an empty name
        When I run :quickmark-add about:blank ""
        Then the error "Can't set mark with empty name!" should be shown

    Scenario: Adding a quickmark with an empty URL
        When I run :quickmark-add "" foo
        Then the error "Can't set mark with empty URL!" should be shown

    Scenario: Loading a quickmark
        Given I have a fresh instance
        When I run :quickmark-add http://localhost:(port)/data/numbers/10.txt ten
        And I run :quickmark-load ten
        Then data/numbers/10.txt should be loaded
        And the following tabs should be open:
            - data/numbers/10.txt (active)

    Scenario: Loading a quickmark in a new tab
        Given I open about:blank
        When I run :tab-only
        And I run :quickmark-add http://localhost:(port)/data/numbers/11.txt eleven
        And I run :quickmark-load -t eleven
        Then data/numbers/11.txt should be loaded
        And the following tabs should be open:
            - about:blank
            - data/numbers/11.txt (active)

    Scenario: Loading a quickmark in a background tab
        Given I open about:blank
        When I run :tab-only
        And I run :quickmark-add http://localhost:(port)/data/numbers/12.txt twelve
        And I run :quickmark-load -b twelve
        Then data/numbers/12.txt should be loaded
        And the following tabs should be open:
            - about:blank (active)
            - data/numbers/12.txt

    Scenario: Loading a quickmark in a new window
        Given I open about:blank
        When I run :tab-only
        And I run :quickmark-add http://localhost:(port)/data/numbers/13.txt thirteen
        And I run :quickmark-load -w thirteen
        And I wait until data/numbers/13.txt is loaded
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
                  url: http://localhost:*/data/numbers/13.txt

    Scenario: Loading a quickmark which does not exist
        When I run :quickmark-load -b doesnotexist
        Then the error "Quickmark 'doesnotexist' does not exist!" should be shown

    Scenario: Loading a quickmark with -t and -b
        When I run :quickmark-add http://localhost:(port)/data/numbers/14.txt fourteen
        When I run :quickmark-load -t -b fourteen
        Then the error "Only one of -t/-b/-w can be given!" should be shown

    Scenario: Deleting a quickmark which does not exist
        When I run :quickmark-del doesnotexist
        Then the error "Quickmark 'doesnotexist' not found!" should be shown

    Scenario: Deleting a quickmark
        When I run :quickmark-add http://localhost:(port)/data/numbers/15.txt fifteen
        And I run :quickmark-del fifteen
        Then the quickmark file should not contain "fourteen http://localhost:*/data/numbers/15.txt "
