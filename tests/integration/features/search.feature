Feature: Searching on a page
    Searching text on the page (like /foo) with different options.

    Background:
        Given I open data/search.html

    ## searching

    Scenario: Searching text
        When I run :search foo
        And I run :yank-selected
        Then the clipboard should contain "foo"

    Scenario: Searching with --reverse
        When I set general -> ignore-case to true
        And I run :search -r foo
        And I run :yank-selected
        Then the clipboard should contain "Foo"

    Scenario: Searching without matches
        When I run :search doesnotmatch
        Then the warning "Text 'doesnotmatch' not found on page!" should be shown

    # xfail takes a long time to timeout, and this doesn't work because this is
    # QtWebKit behaviour.
    @skip
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

    ## :search-prev/next

    Scenario: Jumping to next match
        When I set general -> ignore-case to true
        And I run :search foo
        And I run :search-next
        And I run :yank-selected
        Then the clipboard should contain "Foo"

    Scenario: Jumping to next match without search
        When I run :search-next
        Then no crash should happen

    Scenario: Jumping to previous match
        When I set general -> ignore-case to true
        And I run :search foo
        And I run :search-next
        And I run :search-prev
        And I run :yank-selected
        Then the clipboard should contain "foo"

    Scenario: Jumping to previous match without search
        When I run :search-prev
        Then no crash should happen

    # TODO: with count

    ## wrapping

    Scenario: Wrapping around page
        When I set general -> wrap-search to true
        And I run :search foo
        And I run :search-next
        And I run :search-next
        And I run :yank-selected
        Then the clipboard should contain "foo"

    Scenario: Wrapping around page with wrap-search = false
        When I set general -> wrap-search to false
        And I run :search foo
        And I run :search-next
        And I run :search-next
        Then the warning "Search hit BOTTOM without match for: foo" should be shown

    Scenario: Wrapping around page with --reverse
        When I set general -> wrap-search to true
        And I run :search --reverse foo
        And I run :search-next
        And I run :search-next
        And I run :yank-selected
        Then the clipboard should contain "Foo"

    Scenario: Wrapping around page with wrap-search = false and --reverse
        When I set general -> wrap-search to false
        And I run :search --reverse foo
        And I run :search-next
        And I run :search-next
        Then the warning "Search hit TOP without match for: foo" should be shown

    # TODO: wrapping message with scrolling
    # TODO: wrapping message without scrolling
