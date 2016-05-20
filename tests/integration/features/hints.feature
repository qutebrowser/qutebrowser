Feature: Using hints

    Scenario: Using :follow-hint outside of hint mode (issue 1105)
        When I run :follow-hint
        Then the error "follow-hint: This command is only allowed in hint mode." should be shown

    Scenario: Using :follow-hint with an invalid index.
        When I open data/hints/html/simple.html
        And I run :hint links normal
        And I run :follow-hint xyz
        Then the error "No hint xyz!" should be shown

    ### Opening in current or new tab

    Scenario: Following a hint and force to open in current tab.
        When I open data/hints/link_blank.html
        And I run :hint links current
        And I run :follow-hint a
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - data/hello.txt (active)

    Scenario: Following a hint and allow to open in new tab.
        When I open data/hints/link_blank.html
        And I run :hint links normal
        And I run :follow-hint a
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - data/hints/link_blank.html
            - data/hello.txt (active)

    Scenario: Following a hint to link with sub-element and force to open in current tab.
        When I open data/hints/link_span.html
        And I run :tab-close
        And I run :hint links current
        And I run :follow-hint a
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - data/hello.txt (active)

    Scenario: Entering and leaving hinting mode (issue 1464)
      When I open data/hints/html/simple.html
      And I run :hint
      And I run :fake-key -g <Esc>
      Then no crash should happen

    Scenario: Using :hint spawn with flags and -- (issue 797)
        When I open data/hints/link.html
        And I run :hint -- all spawn -v echo
        And I run :follow-hint a
        Then the message "Command exited successfully." should be shown

    Scenario: Using :hint spawn with flags (issue 797)
        When I open data/hints/html/simple.html
        And I run :hint all spawn -v echo
        And I run :follow-hint a
        Then the message "Command exited successfully." should be shown

    Scenario: Yanking to primary selection without it being supported (#1336)
        When selection is not supported
        And I run :debug-set-fake-clipboard
        And I open data/hints/html/simple.html
        And I run :hint links yank-primary
        And I run :follow-hint a
        Then the clipboard should contain "http://localhost:(port)/data/hello.txt"

    ### iframes

    Scenario: Using :follow-hint inside an iframe
        When I open data/hints/iframe.html
        And I run :hint all normal
        And I run :follow-hint a
        And I run :hint links normal
        And I run :follow-hint a
        Then "acceptNavigationRequest, url http://localhost:*/data/hello.txt, type NavigationTypeLinkClicked, *" should be logged

    Scenario: Using :follow-hint inside a scrolled iframe
        When I open data/hints/iframe_scroll.html
        And I run :hint all normal
        And I run :follow-hint a
        And I run :scroll bottom
        And I run :hint links normal
        And I run :follow-hint a
        Then "acceptNavigationRequest, url http://localhost:*/data/hello2.txt, type NavigationTypeLinkClicked, *" should be logged

    Scenario: Opening a link inside a specific iframe
        When I open data/hints/iframe_target.html
        And I run :hint links normal
        And I run :follow-hint a
        Then "acceptNavigationRequest, url http://localhost:*/data/hello.txt, type NavigationTypeLinkClicked, *" should be logged

    Scenario: Opening a link with specific target frame in a new tab
        When I open data/hints/iframe_target.html
        And I run :hint links tab
        And I run :follow-hint a
        Then the following tabs should be open:
            - data/hints/iframe_target.html
            - data/hello.txt (active)
