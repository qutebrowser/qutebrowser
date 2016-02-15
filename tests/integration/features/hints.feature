Feature: Using hints

    Scenario: Following a hint.
        When I open data/hints/link.html
        And I run :hint links normal
        And I run :follow-hint a
        And I wait until data/hello.txt is loaded
        Then the requests should be:
            data/hints/link.html
            data/hello.txt

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
        # bypass Qt cache
        And I run :reload --force
        And I run :hint links normal
        And I run :follow-hint s
        And I wait until data/hello2.txt is loaded
        Then the requests should be:
            data/hints/link.html
            data/hello2.txt

    Scenario: Following a hint (link containing tag with display:block style)
        When I open data/hints/link.html
        # bypass Qt cache
        And I run :reload --force
        And I run :hint links normal
        And I run :follow-hint d
        And I wait until data/hello3.txt is loaded
        Then the requests should be:
            data/hints/link.html
            data/hello3.txt

    Scenario: Following a hint (link containing tag with display:table style)
        When I open data/hints/link.html
        # bypass Qt cache
        And I run :reload --force
        And I run :hint links normal
        And I run :follow-hint f
        And I wait until data/hello4.txt is loaded
        Then the requests should be:
            data/hints/link.html
            data/hello4.txt

    Scenario: Following a link wrapped across multiple lines.
        When I open data/hints/link.html
        # bypass Qt cache
        And I run :reload --force
        And I run :hint links normal
        And I run :follow-hint g
        And I wait until data/hello.txt is loaded
        # bypass Qt cache
        And I run :reload --force
        Then the requests should be:
            data/hints/link.html
            data/hello.txt
