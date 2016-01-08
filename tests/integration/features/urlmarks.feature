Feature: quickmarks and bookmarks

    # bookmarks

    Scenario: Saving a bookmark
        When I open data/title.html
        And I run :bookmark-add
        Then the message "Bookmarked http://localhost:*/data/title.html!" should be shown
        And the bookmark file should contain "http://localhost:*/data/title.html Test title"

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
