Feature: Searching on a page
    Searching text on the page (like /foo) with different options.

    Background:
        Given I open data/search.html
        And I run :tab-only

    ## searching

    Scenario: Searching text
        When I run :search foo
        And I run :yank-selected
        Then the clipboard should contain "foo"

    Scenario: Searching twice
        When I run :search foo
        And I run :search bar
        And I run :yank-selected
        Then the clipboard should contain "Bar"

    Scenario: Searching with --reverse
        When I set general -> ignore-case to true
        And I run :search -r foo
        And I run :yank-selected
        Then the clipboard should contain "Foo"

    Scenario: Searching without matches
        When I run :search doesnotmatch
        Then the warning "Text 'doesnotmatch' not found on page!" should be shown

    @xfail_norun
    Scenario: Searching with / and spaces at the end (issue 874)
        When I run :set-cmd-text -s /space
        And I run :command-accept
        And I run :yank-selected
        Then the clipboard should contain "space "

    Scenario: Searching with / and slash in search term (issue 507)
        When I run :set-cmd-text -s //slash
        And I run :command-accept
        And I run :yank-selected
        Then the clipboard should contain "/slash"

    # This doesn't work because this is QtWebKit behavior.
    @xfail_norun
    Scenario: Searching text with umlauts
        When I run :search blub
        Then the warning "Text 'blub' not found on page!" should be shown

    ## ignore-case

    Scenario: Searching text with ignore-case = true
        When I set general -> ignore-case to true
        And I run :search bar
        And I run :yank-selected
        Then the clipboard should contain "Bar"

    Scenario: Searching text with ignore-case = false
        When I set general -> ignore-case to false
        And I run :search bar
        And I run :yank-selected
        Then the clipboard should contain "bar"

    Scenario: Searching text with ignore-case = smart (lower-case)
        When I set general -> ignore-case to smart
        And I run :search bar
        And I run :yank-selected
        Then the clipboard should contain "Bar"

    Scenario: Searching text with ignore-case = smart (upper-case)
        When I set general -> ignore-case to smart
        And I run :search Foo
        And I run :yank-selected
        Then the clipboard should contain "Foo"  # even though foo was first

    ## :search-next

    Scenario: Jumping to next match
        When I set general -> ignore-case to true
        And I run :search foo
        And I run :search-next
        And I run :yank-selected
        Then the clipboard should contain "Foo"

    Scenario: Jumping to next match with count
        When I set general -> ignore-case to true
        And I run :search baz
        And I run :search-next with count 2
        And I run :yank-selected
        Then the clipboard should contain "BAZ"

    Scenario: Jumping to next match with --reverse
        When I set general -> ignore-case to true
        And I run :search --reverse foo
        And I run :search-next
        And I run :yank-selected
        Then the clipboard should contain "foo"

    Scenario: Jumping to next match without search
        # Make sure there was no search in the same window before
        When I open data/search.html in a new window
        And I run :search-next
        Then the error "No search done yet." should be shown

    Scenario: Repeating search in a second tab (issue #940)
        When I open data/search.html in a new tab
        And I run :search foo
        And I run :tab-prev
        And I run :search-next
        And I run :yank-selected
        Then the clipboard should contain "foo"

    ## :search-prev

    Scenario: Jumping to previous match
        When I set general -> ignore-case to true
        And I run :search foo
        And I run :search-next
        And I run :search-prev
        And I run :yank-selected
        Then the clipboard should contain "foo"

    Scenario: Jumping to previous match with count
        When I set general -> ignore-case to true
        And I run :search baz
        And I run :search-next
        And I run :search-next
        And I run :search-prev with count 2
        And I run :yank-selected
        Then the clipboard should contain "baz"

    Scenario: Jumping to previous match with --reverse
        When I set general -> ignore-case to true
        And I run :search --reverse foo
        And I run :search-next
        And I run :search-prev
        And I run :yank-selected
        Then the clipboard should contain "Foo"

    Scenario: Jumping to previous match without search
        # Make sure there was no search in the same window before
        When I open data/search.html in a new window
        And I run :search-prev
        Then the error "No search done yet." should be shown

    ## wrapping

    Scenario: Wrapping around page
        When I run :search foo
        And I run :search-next
        And I run :search-next
        And I run :yank-selected
        Then the clipboard should contain "foo"

    Scenario: Wrapping around page with --reverse
        When I run :search --reverse foo
        And I run :search-next
        And I run :search-next
        And I run :yank-selected
        Then the clipboard should contain "Foo"

    # TODO: wrapping message with scrolling
    # TODO: wrapping message without scrolling
