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

    Scenario: Saving a bookmark with tags
        When I run :bookmark-tag data/numbers/14.txt one two
        Then the message "Bookmarked data/numbers/14.txt" should be shown
        And the bookmark file should contain '{"url": "data/numbers/14.txt", "title": "", "tags": ["one", "two"]}'

    Scenario: Saving a bookmark with a non-unique tag and --unique
        When I run :bookmark-tag data/numbers/15.txt one
        And I run :bookmark-tag data/numbers/16.txt --unique one
        Then the error "['one'] are not unique" should be shown

    Scenario: Saving a bookmark with a url but no title
        When I run :bookmark-add http://example.com
        Then the error "Title must be provided if url has been provided" should be shown

    Scenario: Saving a bookmark with an invalid url
        When I run :bookmark-add "ht tp://example.com" "some example title"
        Then the error "Invalid URL *" should be shown

    Scenario: Saving a duplicate bookmark
        When I run :bookmark-add data/numbers/10.txt Ten
        And I run :bookmark-add data/numbers/10.txt Ten
        Then the error "Bookmark already exists!" should be shown

    Scenario: Tagging a bookmark
        When I run :bookmark-add data/numbers/11.txt Eleven
        And I run :bookmark-tag data/numbers/11.txt foo bar
        Then the bookmark file should contain '{"url": "data/numbers/11.txt", "title": "Eleven", "tags": ["foo", "bar"]}'

    Scenario: Removing tags from a bookmark
        When I run :bookmark-add data/numbers/12.txt Twelve
        And I run :bookmark-tag data/numbers/12.txt foo bar baz
        And I run :bookmark-tag data/numbers/12.txt -r foo baz
        Then the bookmark file should contain '{"url": "data/numbers/12.txt", "title": "Twelve", "tags": ["bar"]}'

    Scenario: Loading a bookmark
        When I run :tab-only
        And I run :bookmark-add http://localhost:(port)/data/numbers/1.txt Example
        And I run :bookmark-tag http://localhost:(port)/data/numbers/1.txt one
        And I run :bookmark-load one
        Then data/numbers/1.txt should be loaded
        And the following tabs should be open:
            - data/numbers/1.txt (active)

    Scenario: Loading a bookmark in a new tab
        Given I open about:blank
        When I run :tab-only
        And I run :bookmark-add http://localhost:(port)/data/numbers/2.txt Example
        And I run :bookmark-tag http://localhost:(port)/data/numbers/2.txt two
        And I run :bookmark-load -t two
        Then data/numbers/2.txt should be loaded
        And the following tabs should be open:
            - about:blank
            - data/numbers/2.txt (active)

    Scenario: Loading a bookmark in a background tab
        Given I open about:blank
        When I run :tab-only
        And I run :bookmark-add http://localhost:(port)/data/numbers/3.txt Example
        And I run :bookmark-tag http://localhost:(port)/data/numbers/3.txt three
        And I run :bookmark-load -b three
        Then data/numbers/3.txt should be loaded
        And the following tabs should be open:
            - about:blank (active)
            - data/numbers/3.txt

    Scenario: Loading multiple bookmarks in tabs
        Given I open about:blank
        When I run :tab-only
        And I run :bookmark-tag http://localhost:(port)/data/numbers/17.txt multi
        And I run :bookmark-tag http://localhost:(port)/data/numbers/18.txt multi
        And I run :bookmark-load -at multi
        Then data/numbers/17.txt should be loaded
        And data/numbers/18.txt should be loaded
        And the following tabs should be open:
            - about:blank
            - data/numbers/18.txt
            - data/numbers/17.txt (active)

    Scenario: Loading a bookmark in a new window
        Given I open about:blank
        When I run :tab-only
        And I run :bookmark-add http://localhost:(port)/data/numbers/4.txt Example
        And I run :bookmark-tag http://localhost:(port)/data/numbers/4.txt four
        And I run :bookmark-load -w four
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
        Given I open about:blank
        When I run :tab-only
        And I run :bookmark-add http://localhost:(port)/data/numbers/5.txt Example
        And I run :bookmark-tag http://localhost:(port)/data/numbers/5.txt five
        And I run :bookmark-load -t -b five
        Then the error "Only one of -t/-b/-w/-p can be given!" should be shown

    Scenario: Deleting a bookmark which does not exist
        When I run :bookmark-del doesnotexist
        Then the error "Bookmark 'doesnotexist' not found!" should be shown

    Scenario: Deleting a bookmark
        When I run :bookmark-add data/numbers/6.txt six
        And I run :bookmark-del data/numbers/6.txt
        Then the bookmark file should not contain "*data/numbers/6.txt*"

    Scenario: Purge a bookmark by tag removal
        When I run :bookmark-add data/numbers/13.txt title
        When I run :bookmark-tag data/numbers/13.txt thirteen
        And I run :bookmark-tag data/numbers/13.txt -R thirteen
        Then the bookmark file should not contain "*data/numbers/13.txt*"

    Scenario: Deleting the current page's bookmark if it doesn't exist
        When I open data/hello.txt
        And I run :bookmark-del
        Then the error "Bookmark 'http://localhost:(port)/data/hello.txt' not found!" should be shown

    Scenario: Deleting the current page's bookmark
        When I open data/numbers/7.txt
        And I run :bookmark-add
        And I run :bookmark-del
        Then the bookmark file should not contain "http://localhost:*/data/numbers/7.txt "

    Scenario: Toggling a bookmark
        When I open data/numbers/8.txt
        And I run :bookmark-add
        And I run :bookmark-add --toggle
        Then the bookmark file should not contain "http://localhost:*/data/numbers/8.txt "

    Scenario: Loading a bookmark with --delete
        When I run :bookmark-add http://localhost:(port)/data/numbers/9.txt "nine"
        And I run :bookmark-load -d http://localhost:(port)/data/numbers/9.txt
        Then the bookmark file should not contain "http://localhost:*/data/numbers/9.txt "

    Scenario: Listing bookmarks
        When I run :bookmark-add data/numbers/13.txt "Test title Thirteen"
        And I open qute://bookmarks
        Then the page should contain the plaintext "Test title Thirteen"
