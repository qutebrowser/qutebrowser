Feature: Using hints

    Scenario: Following a hint.
        When I open data/hints/link.html
        And I run :hint links normal
        And I run :follow-hint a
        Then data/hello.txt should be loaded

    Scenario: Using :follow-hint outside of hint mode (issue 1105)
        When I run :follow-hint
        Then the error "follow-hint: This command is only allowed in hint mode." should be shown

    Scenario: Using :follow-hint with an invalid index.
        When I open data/hints/link.html
        And I run :hint links normal
        And I run :follow-hint xyz
        Then the error "No hint xyz!" should be shown

    ### Hinting problematic links

    Scenario: Following a hint (link containing formatting tags)
        When I open data/hints/link.html
        And I run :hint links normal
        And I run :follow-hint s
        Then data/hello2.txt should be loaded

    Scenario: Following a hint (link containing tag with display:block style)
        When I open data/hints/link.html
        And I run :hint links normal
        And I run :follow-hint d
        Then data/hello3.txt should be loaded

    Scenario: Following a hint (link containing tag with display:table style)
        When I open data/hints/link.html
        And I run :hint links normal
        And I run :follow-hint f
        Then data/hello4.txt should be loaded

    Scenario: Following a link wrapped across multiple lines.
        When I open data/hints/link.html
        And I run :hint links normal
        And I run :follow-hint g
        Then data/hello.txt should be loaded
