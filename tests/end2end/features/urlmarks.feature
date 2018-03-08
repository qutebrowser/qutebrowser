# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Bookmarks

    Scenario: Saving a bookmark
        When I open data/title.html
        And I run :bookmark-add
        Then the message "Bookmarked http://localhost:*/data/title.html" should be shown
        And the bookmark file should contain '{"url": "http://localhost:*/data/title.html", "title": "Test title", "tags": []}'

    Scenario: Saving a bookmark with a provided url and title
        When I run :bookmark-add http://example.com "some example title"
        Then the message "Bookmarked http://example.com" should be shown
        And the bookmark file should contain '{"url": "http://example.com", "title": "some example title", "tags": []}'

    Scenario: Saving a bookmark with a url but no title
        When I run :bookmark-add http://example.com
        Then the error "Title must be provided if url has been provided" should be shown

    Scenario: Saving a bookmark with an invalid url
        When I set url.auto_search to never
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
        Then the error "Only one of -t/-b/-w/-p can be given!" should be shown

    Scenario: Deleting a bookmark which does not exist
        When I run :bookmark-del doesnotexist
        Then the error "Bookmark 'doesnotexist' not found!" should be shown

    Scenario: Deleting a bookmark
        When I open data/numbers/5.txt
        And I run :bookmark-add
        And I run :bookmark-del http://localhost:(port)/data/numbers/5.txt
        Then the bookmark file should not contain "http://localhost:*/data/numbers/5.txt "

    Scenario: Deleting the current page's bookmark if it doesn't exist
        When I open data/hello.txt
        And I run :bookmark-del
        Then the error "Bookmark 'http://localhost:(port)/data/hello.txt' not found!" should be shown

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

    Scenario: Listing bookmarks
        Given I have a fresh instance
        When I open data/title.html in a new tab
        And I run :bookmark-add
        And I open qute://bookmarks
        Then the page should contain the plaintext "Test title"
