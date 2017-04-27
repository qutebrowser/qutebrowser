# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Searching on a page
    Searching text on the page (like /foo) with different options.

    Background:
        Given I open data/search.html
        And I run :tab-only

    ## searching

    Scenario: Searching text
        When I run :search foo
        Then "foo" should be found

    Scenario: Searching twice
        When I run :search foo
        And I run :search bar
        Then "Bar" should be found

    Scenario: Searching with --reverse
        When I set general -> ignore-case to true
        And I run :search -r foo
        Then "Foo" should be found

    Scenario: Searching without matches
        When I run :search doesnotmatch
        Then the warning "Text 'doesnotmatch' not found on page!" should be shown

    @xfail_norun
    Scenario: Searching with / and spaces at the end (issue 874)
        When I run :set-cmd-text -s /space
        And I run :command-accept
        Then "space " should be found

    Scenario: Searching with / and slash in search term (issue 507)
        When I run :set-cmd-text -s //slash
        And I run :command-accept
        Then "/slash" should be found

    # This doesn't work because this is QtWebKit behavior.
    @xfail_norun
    Scenario: Searching text with umlauts
        When I run :search blub
        Then the warning "Text 'blub' not found on page!" should be shown

    ## ignore-case

    Scenario: Searching text with ignore-case = true
        When I set general -> ignore-case to true
        And I run :search bar
        Then "Bar" should be found

    Scenario: Searching text with ignore-case = false
        When I set general -> ignore-case to false
        And I run :search bar
        Then "bar" should be found

    Scenario: Searching text with ignore-case = smart (lower-case)
        When I set general -> ignore-case to smart
        And I run :search bar
        Then "Bar" should be found

    Scenario: Searching text with ignore-case = smart (upper-case)
        When I set general -> ignore-case to smart
        And I run :search Foo
        Then "Foo" should be found  # even though foo was first

    ## :search-next

    Scenario: Jumping to next match
        When I set general -> ignore-case to true
        And I run :search foo
        And I run :search-next
        Then "Foo" should be found

    Scenario: Jumping to next match with count
        When I set general -> ignore-case to true
        And I run :search baz
        And I run :search-next with count 2
        Then "BAZ" should be found

    Scenario: Jumping to next match with --reverse
        When I set general -> ignore-case to true
        And I run :search --reverse foo
        And I run :search-next
        Then "foo" should be found

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
        Then "foo" should be found

    # https://github.com/qutebrowser/qutebrowser/issues/2438
    Scenario: Jumping to next match after clearing
        When I set general -> ignore-case to true
        And I run :search foo
        And I run :search
        And I run :search-next
        Then "foo" should be found

    ## :search-prev

    Scenario: Jumping to previous match
        When I set general -> ignore-case to true
        And I run :search foo
        And I run :search-next
        And I run :search-prev
        Then "foo" should be found

    Scenario: Jumping to previous match with count
        When I set general -> ignore-case to true
        And I run :search baz
        And I run :search-next
        And I run :search-next
        And I run :search-prev with count 2
        Then "baz" should be found

    Scenario: Jumping to previous match with --reverse
        When I set general -> ignore-case to true
        And I run :search --reverse foo
        And I run :search-next
        And I run :search-prev
        Then "Foo" should be found

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
        Then "foo" should be found

    Scenario: Wrapping around page with --reverse
        When I run :search --reverse foo
        And I run :search-next
        And I run :search-next
        Then "Foo" should be found

    # TODO: wrapping message with scrolling
    # TODO: wrapping message without scrolling
