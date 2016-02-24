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

    @xfail
    Scenario: Using :follow-hint inside an iframe
        When I open data/hints/iframe.html
        And I run :hint all normal
        And I run :follow-hint a
        And I run :hint links normal
        And I run :follow-hint a
        Then data/hello.txt should be loaded

    @xfail
    Scenario: Using :follow-hint inside a scrolled iframe
        When I open data/hints/iframe_scroll.html
        And I run :hint all normal
        And I run :follow-hint a
        And I run :scroll bottom
        And I run :hint links normal
        And I run :follow-hint a
        Then data/hello2.txt should be loaded
