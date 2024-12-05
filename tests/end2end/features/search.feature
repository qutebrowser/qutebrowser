Feature: Searching on a page
    Searching text on the page (like /foo) with different options.

    Background:
        Given I open data/search.html
        And I run :tab-only

    ## searching

    Scenario: Searching text
        When I run :search foo
        And I wait for "search found foo" in the log
        Then "foo" should be found

    Scenario: Searching twice
        When I run :search foo
        And I wait for "search found foo" in the log
        And I run :search bar
        And I wait for "search found bar" in the log
        Then "Bar" should be found

    Scenario: Searching with --reverse
        When I set search.ignore_case to always
        And I run :search -r foo
        And I wait for "search found foo with flags FindBackward" in the log
        Then "Foo" should be found

    Scenario: Searching without matches
        When I run :search doesnotmatch
        And I wait for "search didn't find doesnotmatch" in the log
        Then the warning "Text 'doesnotmatch' not found on page!" should be shown

    @xfail_norun
    Scenario: Searching with / and spaces at the end (issue 874)
        When I run :cmd-set-text -s /space
        And I run :command-accept
        And I wait for "search found space " in the log
        Then "space " should be found

    Scenario: Searching with / and slash in search term (issue 507)
        When I run :cmd-set-text //slash
        And I run :command-accept
        And I wait for "search found /slash" in the log
        Then "/slash" should be found

    Scenario: Searching with arguments at start of search term
        When I run :cmd-set-text /-r reversed
        And I run :command-accept
        And I wait for "search found -r reversed" in the log
        Then "-r reversed" should be found

    Scenario: Searching with semicolons in search term
        When I run :cmd-set-text /;
        And I run :fake-key -g ;
        And I run :fake-key -g <space>
        And I run :fake-key -g semi
        And I run :command-accept
        And I wait for "search found ;; semi" in the log
        Then ";; semi" should be found

    # This doesn't work because this is QtWebKit behavior.
    @xfail_norun
    Scenario: Searching text with umlauts
        When I run :search blub
        And I wait for "search didn't find blub" in the log
        Then the warning "Text 'blub' not found on page!" should be shown

    Scenario: Searching text duplicates
        When I run :search foo
        And I wait for "search found foo" in the log
        And I run :search foo
        Then "Ignoring duplicate search request for foo, but resetting flags" should be logged

    Scenario: Reset search direction on duplicate search, forward-to-back
        When I run :search baz
        And I wait for "search found baz" in the log
        And I run :search -r baz
        And I wait for "Ignoring duplicate search request for baz, but resetting flags" in the log
        And I run :search-next
        And I wait for "next_result found baz with flags FindBackward" in the log
        Then "BAZ" should be found

    Scenario: Reset search direction on duplicate search, back-to-forward
        When I run :search -r baz
        And I wait for "search found baz with flags FindBackward" in the log
        And I run :search baz
        And I wait for "Ignoring duplicate search request for baz, but resetting flags" in the log
        And I run :search-next
        And I wait for "next_result found baz" in the log
        Then "baz" should be found

    ## search.ignore_case

    Scenario: Searching text with search.ignore_case = always
        When I set search.ignore_case to always
        And I run :search bar
        And I wait for "search found bar" in the log
        Then "Bar" should be found

    Scenario: Searching text with search.ignore_case = never
        When I set search.ignore_case to never
        And I run :search bar
        And I wait for "search found bar with flags FindCaseSensitively" in the log
        Then "bar" should be found

    Scenario: Searching text with search.ignore_case = smart (lower-case)
        When I set search.ignore_case to smart
        And I run :search bar
        And I wait for "search found bar" in the log
        Then "Bar" should be found

    Scenario: Searching text with search.ignore_case = smart (upper-case)
        When I set search.ignore_case to smart
        And I run :search Foo
        And I wait for "search found Foo with flags FindCaseSensitively" in the log
        # even though foo was first
        Then "Foo" should be found

    ## :search-next

    Scenario: Jumping to next match
        When I set search.ignore_case to always
        And I run :search foo
        And I wait for "search found foo" in the log
        And I run :search-next
        And I wait for "next_result found foo" in the log
        Then "Foo" should be found

    Scenario: Jumping to next match with count
        When I set search.ignore_case to always
        And I run :search baz
        And I wait for "search found baz" in the log
        And I run :search-next with count 2
        And I wait for "next_result found baz" in the log
        Then "BAZ" should be found

    Scenario: Jumping to next match with --reverse
        When I set search.ignore_case to always
        And I run :search --reverse foo
        And I wait for "search found foo with flags FindBackward" in the log
        And I run :search-next
        And I wait for "next_result found foo with flags FindBackward" in the log
        Then "foo" should be found

    Scenario: Jumping to next match without search
        # Make sure there was no search in the same window before
        When I open data/search.html in a new window
        And I run :search-next
        Then the error "No search done yet." should be shown

    # https://github.com/qutebrowser/qutebrowser/issues/7275
    @qtwebkit_skip
    Scenario: Jumping to next without matches
        When I run :search doesnotmatch
        And I wait for the warning "Text 'doesnotmatch' not found on page!"
        And I run :search-next
        Then the warning "Text 'doesnotmatch' not found on page!" should be shown

    Scenario: Repeating search in a second tab (issue #940)
        When I open data/search.html in a new tab
        And I run :search foo
        And I wait for "search found foo" in the log
        And I run :tab-prev
        And I run :search-next
        And I wait for "search found foo" in the log
        Then "foo" should be found

    # https://github.com/qutebrowser/qutebrowser/issues/2438
    Scenario: Jumping to next match after clearing
        When I set search.ignore_case to always
        And I run :search foo
        And I wait for "search found foo" in the log
        And I run :search
        And I run :search-next
        And I wait for "next_result found foo" in the log
        Then "foo" should be found

    ## :search-prev

    Scenario: Jumping to previous match
        When I set search.ignore_case to always
        And I run :search foo
        And I wait for "search found foo" in the log
        And I run :search-next
        And I wait for "next_result found foo" in the log
        And I run :search-prev
        And I wait for "prev_result found foo with flags FindBackward" in the log
        Then "foo" should be found

    Scenario: Jumping to previous match with count
        When I set search.ignore_case to always
        And I run :search baz
        And I wait for "search found baz" in the log
        And I run :search-next
        And I wait for "next_result found baz" in the log
        And I run :search-next
        And I wait for "next_result found baz" in the log
        And I run :search-prev with count 2
        And I wait for "prev_result found baz with flags FindBackward" in the log
        Then "baz" should be found

    Scenario: Jumping to previous match with --reverse
        When I set search.ignore_case to always
        And I run :search --reverse foo
        And I wait for "search found foo with flags FindBackward" in the log
        And I run :search-next
        And I wait for "next_result found foo with flags FindBackward" in the log
        And I run :search-prev
        And I wait for "prev_result found foo" in the log
        Then "Foo" should be found

    # This makes sure we don't mutate the original flags
    # Seems to be broken with QtWebKit, wontfix
    @qtwebkit_skip
    Scenario: Jumping to previous match with --reverse twice
        When I set search.ignore_case to always
        And I run :search --reverse baz
        # BAZ
        And I wait for "search found baz with flags FindBackward" in the log
        And I run :search-prev
        # Baz
        And I wait for "prev_result found baz" in the log
        And I run :search-prev
        # baz
        And I wait for "prev_result found baz" in the log
        Then "baz" should be found

    Scenario: Jumping to previous match without search
        # Make sure there was no search in the same window before
        When I open data/search.html in a new window
        And I run :search-prev
        Then the error "No search done yet." should be shown

    # https://github.com/qutebrowser/qutebrowser/issues/7275
    @qtwebkit_skip
    Scenario: Jumping to previous without matches
        When I run :search doesnotmatch
        And I wait for the warning "Text 'doesnotmatch' not found on page!"
        And I run :search-prev
        Then the warning "Text 'doesnotmatch' not found on page!" should be shown

    ## wrapping

    Scenario: Wrapping around page
        When I run :search foo
        And I wait for "search found foo" in the log
        And I run :search-next
        And I wait for "next_result found foo" in the log
        And I run :search-next
        And I wait for "next_result found foo" in the log
        Then "foo" should be found

    Scenario: Wrapping around page with --reverse
        When I run :search --reverse foo
        And I wait for "search found foo with flags FindBackward" in the log
        And I run :search-next
        And I wait for "next_result found foo with flags FindBackward" in the log
        And I run :search-next
        And I wait for "next_result found foo with flags FindBackward" in the log
        Then "Foo" should be found

    # TODO: wrapping message with scrolling
    # TODO: wrapping message without scrolling

    ## wrapping prevented

    Scenario: Preventing wrapping at the top of the page
        When I set search.ignore_case to always
        And I set search.wrap to false
        And I set search.wrap_messages to true
        And I run :search --reverse foo
        And I wait for "search found foo with flags FindBackward" in the log
        And I run :search-next
        And I wait for "next_result found foo with flags FindBackward" in the log
        And I run :search-next
        Then the message "Search hit TOP" should be shown

    Scenario: Preventing wrapping at the bottom of the page
        When I set search.ignore_case to always
        And I set search.wrap to false
        And I run :search foo
        And I wait for "search found foo" in the log
        And I run :search-next
        And I wait for "next_result found foo" in the log
        And I run :search-next
        Then the message "Search hit BOTTOM" should be shown

    ## search match counter

    @qtwebkit_skip
    Scenario: Setting search match counter on search
        When I set search.ignore_case to always
        And I set search.wrap to true
        And I run :search ba
        And I wait for "search found ba" in the log
        Then "Setting search match text to 1/5" should be logged

    @qtwebkit_skip
    Scenario: Updating search match counter on search-next
        When I set search.ignore_case to always
        And I set search.wrap to true
        And I run :search ba
        And I wait for "search found ba" in the log
        And I run :search-next
        And I wait for "next_result found ba" in the log
        And I run :search-next
        And I wait for "next_result found ba" in the log
        Then "Setting search match text to 3/5" should be logged

    @qtwebkit_skip
    Scenario: Updating search match counter on search-prev with wrapping
        When I set search.ignore_case to always
        And I set search.wrap to true
        And I run :search ba
        And I wait for "search found ba" in the log
        And I run :search-prev
        And I wait for the message "Search hit TOP, continuing at BOTTOM"
        Then "Setting search match text to 5/5" should be logged

    @qtwebkit_skip
    Scenario: Updating search match counter on search-prev without wrapping
        When I set search.ignore_case to always
        And I set search.wrap to false
        And I run :search ba
        And I wait for "search found ba" in the log
        And I run :search-prev
        And I wait for the message "Search hit TOP"
        Then "Setting search match text to 1/5" should be logged

    ## follow searched links
    @skip  # Too flaky
    Scenario: Follow a searched link
        When I run :search follow
        And I wait for "search found follow" in the log
        And I wait 0.5s
        And I run :selection-follow
        Then data/hello.txt should be loaded

    @skip  # Too flaky
    Scenario: Follow a searched link in a new tab
        When I run :window-only
        And I run :search follow
        And I wait for "search found follow" in the log
        And I wait 0.5s
        And I run :selection-follow -t
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            """
            - data/search.html
            - data/hello.txt (active)
            """

    Scenario: Don't follow searched text
        When I run :window-only
        And I run :search foo
        And I wait for "search found foo" in the log
        And I run :selection-follow
        Then the following tabs should be open:
            """
            - data/search.html (active)
            """

    Scenario: Don't follow searched text in a new tab
        When I run :window-only
        And I run :search foo
        And I wait for "search found foo" in the log
        And I run :selection-follow -t
        Then the following tabs should be open:
            """
            - data/search.html (active)
            """

    Scenario: Follow a manually selected link
        When I run :jseval --file (testdata)/search_select.js
        And I run :selection-follow
        Then data/hello.txt should be loaded

    Scenario: Follow a manually selected link in a new tab
        When I run :window-only
        And I run :jseval --file (testdata)/search_select.js
        And I run :selection-follow -t
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            """
            - data/search.html
            - data/hello.txt (active)
            """

    @qtwebkit_skip @skip  # Not supported in qtwebkit 
    Scenario: Follow a searched link in an iframe
        When I open data/iframe_search.html
        And I wait for "* search loaded" in the log
        And I run :tab-only
        And I run :search follow
        And I wait for "search found follow" in the log
        And I run :selection-follow
        Then "navigation request: url http://localhost:*/data/hello.txt (current http://localhost:*/data/iframe_search.html), type link_clicked, is_main_frame False" should be logged

    @qtwebkit_skip @skip  # Not supported in qtwebkit 
    Scenario: Follow a tabbed searched link in an iframe
        When I open data/iframe_search.html
        And I wait for "* search loaded" in the log
        And I run :tab-only
        And I run :search follow
        And I wait for "search found follow" in the log
        And I run :selection-follow -t
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            """
            - data/iframe_search.html
            - data/hello.txt (active)
            """

    Scenario: Closing a tab during a search
        When I run :open -b about:blank
        And I run :search a
        And I run :tab-close
        Then no crash should happen
