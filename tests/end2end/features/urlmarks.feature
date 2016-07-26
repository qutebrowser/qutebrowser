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

    Scenario: Deleting the current page's bookmark if it doesn't exist
        When I open about:blank
        And I run :bookmark-del
        Then the error "Bookmark 'about:blank' not found!" should be shown

    Scenario: Deleting the current page's bookmark
        When I open data/numbers/6.txt
        And I run :bookmark-add
        And I run :bookmark-del
        Then the bookmark file should not contain "http://localhost:*/data/numbers/6.txt "

    Scenario: Toggling a bookmark
        When I open data/numbers/7.txt
        And I run :bookmark-add
        And I run :bookmark-add --toggle
        Then the bookmark file should not contain "http://localhost:*/data/numbers/7.txt "

    Scenario: Loading a bookmark with --delete
        When I run :bookmark-add http://localhost:(port)/data/numbers/8.txt "eight"
        And I run :bookmark-load -d http://localhost:(port)/data/numbers/8.txt
        Then the bookmark file should not contain "http://localhost:*/data/numbers/8.txt "

    ## quickmarks

    Scenario: Saving a quickmark (:quickmark-add)
        When I run :quickmark-add http://localhost:(port)/data/numbers/9.txt nine
        Then the quickmark file should contain "nine http://localhost:*/data/numbers/9.txt"

    Scenario: Saving a quickmark (:quickmark-save)
        When I open data/numbers/10.txt
        And I run :quickmark-save
        And I wait for "Entering mode KeyMode.prompt (reason: question asked)" in the log
        And I press the keys "ten"
        And I press the keys "<Enter>"
        Then the quickmark file should contain "ten http://localhost:*/data/numbers/10.txt"

    Scenario: Saving a duplicate quickmark (without override)
        When I run :quickmark-add http://localhost:(port)/data/numbers/11.txt eleven
        And I run :quickmark-add http://localhost:(port)/data/numbers/11_2.txt eleven
        And I wait for "Entering mode KeyMode.yesno (reason: question asked)" in the log
        And I run :prompt-no
        Then the quickmark file should contain "eleven http://localhost:*/data/numbers/11.txt"

    Scenario: Saving a duplicate quickmark (with override)
        When I run :quickmark-add http://localhost:(port)/data/numbers/12.txt twelve
        And I run :quickmark-add http://localhost:(port)/data/numbers/12_2.txt twelve
        And I wait for "Entering mode KeyMode.yesno (reason: question asked)" in the log
        And I run :prompt-yes
        Then the quickmark file should contain "twelve http://localhost:*/data/numbers/12_2.txt"

    Scenario: Adding a quickmark with an empty name
        When I run :quickmark-add about:blank ""
        Then the error "Can't set mark with empty name!" should be shown

    Scenario: Adding a quickmark with an empty URL
        When I run :quickmark-add "" foo
        Then the error "Can't set mark with empty URL!" should be shown

    Scenario: Loading a quickmark
        Given I have a fresh instance
        When I run :quickmark-add http://localhost:(port)/data/numbers/13.txt thirteen
        And I run :quickmark-load thirteen
        Then data/numbers/13.txt should be loaded
        And the following tabs should be open:
            - data/numbers/13.txt (active)

    Scenario: Loading a quickmark in a new tab
        Given I open about:blank
        When I run :tab-only
        And I run :quickmark-add http://localhost:(port)/data/numbers/14.txt fourteen
        And I run :quickmark-load -t fourteen
        Then data/numbers/14.txt should be loaded
        And the following tabs should be open:
            - about:blank
            - data/numbers/14.txt (active)

    Scenario: Loading a quickmark in a background tab
        Given I open about:blank
        When I run :tab-only
        And I run :quickmark-add http://localhost:(port)/data/numbers/15.txt fifteen
        And I run :quickmark-load -b fifteen
        Then data/numbers/15.txt should be loaded
        And the following tabs should be open:
            - about:blank (active)
            - data/numbers/15.txt

    Scenario: Loading a quickmark in a new window
        Given I open about:blank
        When I run :tab-only
        And I run :quickmark-add http://localhost:(port)/data/numbers/16.txt sixteen
        And I run :quickmark-load -w sixteen
        And I wait until data/numbers/16.txt is loaded
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
                  url: http://localhost:*/data/numbers/16.txt

    Scenario: Loading a quickmark which does not exist
        When I run :quickmark-load -b doesnotexist
        Then the error "Quickmark 'doesnotexist' does not exist!" should be shown

    Scenario: Loading a quickmark with -t and -b
        When I run :quickmark-add http://localhost:(port)/data/numbers/17.txt seventeen
        When I run :quickmark-load -t -b seventeen
        Then the error "Only one of -t/-b/-w can be given!" should be shown

    Scenario: Deleting a quickmark which does not exist
        When I run :quickmark-del doesnotexist
        Then the error "Quickmark 'doesnotexist' not found!" should be shown

    Scenario: Deleting a quickmark
        When I run :quickmark-add http://localhost:(port)/data/numbers/18.txt eighteen
        And I run :quickmark-del eighteen
        Then the quickmark file should not contain "eighteen http://localhost:*/data/numbers/18.txt "

    Scenario: Deleting the current page's quickmark if it has none
        When I open about:blank
        And I run :quickmark-del
        Then the error "Quickmark for 'about:blank' not found!" should be shown

    Scenario: Deleting the current page's quickmark
        When I open data/numbers/19.txt
        And I run :quickmark-add http://localhost:(port)/data/numbers/19.txt nineteen
        And I run :quickmark-del
        Then the quickmark file should not contain "nineteen http://localhost:*/data/numbers/19.txt"

    Scenario: Listing quickmarks
        When I run :quickmark-add http://localhost:(port)/data/numbers/20.txt twenty
        And I run :quickmark-add http://localhost:(port)/data/numbers/21.txt twentyone
        And I open qute:bookmarks
        Then the page should contain the plaintext "twenty"
        And the page should contain the plaintext "twentyone"

    Scenario: Listing bookmarks
        When I open data/title.html
        And I run :bookmark-add
        And I open qute:bookmarks
        Then the page should contain the plaintext "Test title"
