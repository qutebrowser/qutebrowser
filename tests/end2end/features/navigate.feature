# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Using :navigate

    Scenario: :navigate with invalid argument
        When I run :navigate foo
        Then the error "where: Invalid value foo - expected one of: prev, next, up, increment, decrement, strip" should be shown

    # up

    Scenario: Navigating up in qute://help/
        When the documentation is up to date
        And I open qute://help/commands.html
        And I run :navigate up
        Then qute://help/ should be loaded

    # prev/next

    Scenario: Navigating to previous page
        When I open data/navigate in a new tab
        And I run :navigate prev
        Then data/navigate/prev.html should be loaded

    Scenario: Navigating to next page
        When I open data/navigate
        And I run :navigate next
        Then data/navigate/next.html should be loaded

    Scenario: Navigating to previous page without links
        When I open data/numbers/1.txt
        And I run :navigate prev
        Then the error "No prev links found!" should be shown

    Scenario: Navigating to next page without links
        When I open data/numbers/1.txt
        And I run :navigate next
        Then the error "No forward links found!" should be shown

    Scenario: Navigating to next page to a fragment
        When I open data/navigate#fragment
        And I run :navigate next
        Then data/navigate/next.html should be loaded

    Scenario: Navigating to previous page with rel
        When I open data/navigate/rel.html
        And I run :navigate prev
        Then data/navigate/prev.html should be loaded

    Scenario: Navigating to next page with rel
        When I open data/navigate/rel.html
        And I run :navigate next
        Then data/navigate/next.html should be loaded

    Scenario: Navigating to previous page with rel nofollow
        When I open data/navigate/rel_nofollow.html
        And I run :navigate prev
        Then data/navigate/prev.html should be loaded

    Scenario: Navigating to next page with rel nofollow
        When I open data/navigate/rel_nofollow.html
        And I run :navigate next
        Then data/navigate/next.html should be loaded

    @qtwebkit_skip
    Scenario: Navigating with invalid selector
        When I open data/navigate
        And I set hints.selectors to {"links": ["@"]}
        And I run :navigate next
        Then the error "SyntaxError: Failed to execute 'querySelectorAll' on 'Document': '@' is not a valid selector." should be shown

    Scenario: Navigating with no next selector
        When I set hints.selectors to {'all': ['a']}
        And I run :navigate next
        Then the error "Undefined hinting group 'links'" should be shown

    # increment/decrement

    @qtwebengine_todo: Doesn't find any elements
    Scenario: Navigating multiline links
        When I open data/navigate/multilinelinks.html
        And I run :navigate next
        Then data/numbers/5.txt should be loaded
