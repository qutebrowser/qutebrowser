Feature: quickmarks and bookmarks

    Scenario: Saving a bookmark
        When I open data/title.html
        And I run :bookmark-add
        Then the message "Bookmarked http://localhost:*/data/title.html!" should be shown
        And the bookmark file should contain "http://localhost:*/data/title.html Test title"
