Feature: Using hints

    Scenario: Using :follow-hint outside of hint mode (issue 1105)
        When I run :follow-hint
        Then the error "follow-hint: This command is only allowed in hint mode." should be shown

    Scenario: Using :follow-hint with an invalid index.
        When I open data/hints/html/simple.html
        And I run :hint links normal
        And I run :follow-hint xyz
        Then the error "No hint xyz!" should be shown

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
