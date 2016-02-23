Feature: Using hints

    Scenario: Using :follow-hint outside of hint mode (issue 1105)
        When I run :follow-hint
        Then the error "follow-hint: This command is only allowed in hint mode." should be shown

    Scenario: Using :follow-hint with an invalid index.
        When I open data/hints/html/simple.html
        And I run :hint links normal
        And I run :follow-hint xyz
        Then the error "No hint xyz!" should be shown

    ### TODO: use test_hints_html.py for zoom tests

    Scenario: Following a link with zoom 75%.
        When I open data/hints/html/zoom_precision.html
        And I run :zoom 75
        And I run :hint links normal
        And I run :follow-hint a
        And I run :zoom 100
        Then data/hello.txt should be loaded

    Scenario: Following a link with zoom 75% and zoom-text-only == True.
        When I open data/hints/html/zoom_precision.html
        And I run :set ui zoom-text-only true
        And I run :zoom 75
        And I run :hint links normal
        And I run :follow-hint a
        And I run :zoom 100
        And I run :set ui zoom-text-only false
        Then data/hello.txt should be loaded
