# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Opening pages

    Scenario: :open with URL
        Given I open about:blank
        When I run :open http://localhost:(port)/data/numbers/1.txt
        And I wait until data/numbers/1.txt is loaded
        And I run :tab-only
        Then the session should look like:
            windows:
            - tabs:
              - active: true
                history:
                - url: about:blank
                - active: true
                  url: http://localhost:*/data/numbers/1.txt

    Scenario: :open without URL
        When I set url.default_page to http://localhost:(port)/data/numbers/11.txt
        And I run :open
        Then data/numbers/11.txt should be loaded

    Scenario: :open without URL and -t
        When I set url.default_page to http://localhost:(port)/data/numbers/2.txt
        And I run :open -t
        Then data/numbers/2.txt should be loaded

    Scenario: :open with invalid URL
        When I set url.auto_search to never
        And I run :open foo!
        Then the error "Invalid URL" should be shown

    Scenario: :open with -t and -b
        When I run :open -t -b foo.bar
        Then the error "Only one of -t/-b/-w/-p can be given!" should be shown

    Scenario: Searching with :open
        When I set url.auto_search to naive
        And I set url.searchengines to {"DEFAULT": "http://localhost:(port)/data/numbers/{}.txt"}
        And I run :open 3
        Then data/numbers/3.txt should be loaded

    @flaky
    Scenario: Opening in a new tab
        Given I open about:blank
        When I run :tab-only
        And I run :open -t http://localhost:(port)/data/numbers/4.txt
        And I wait until data/numbers/4.txt is loaded
        Then the following tabs should be open:
            - about:blank
            - data/numbers/4.txt (active)

    Scenario: Opening in a new background tab
        Given I open about:blank
        When I run :tab-only
        And I run :open -b http://localhost:(port)/data/numbers/5.txt
        And I wait until data/numbers/5.txt is loaded
        Then the following tabs should be open:
            - about:blank (active)
            - data/numbers/5.txt

    Scenario: :open with count
        Given I open about:blank
        When I run :tab-only
        And I open about:blank in a new tab
        And I run :open http://localhost:(port)/data/numbers/6.txt with count 2
        And I wait until data/numbers/6.txt is loaded
        Then the session should look like:
            windows:
            - tabs:
              - history:
                - url: about:blank
              - active: true
                history:
                - url: about:blank
                - active: true
                  url: http://localhost:*/data/numbers/6.txt

    Scenario: Opening in a new tab (unrelated)
        Given I open about:blank
        When I set tabs.new_position.unrelated to next
        And I set tabs.new_position.related to prev
        And I run :tab-only
        And I run :open -t http://localhost:(port)/data/numbers/7.txt
        And I wait until data/numbers/7.txt is loaded
        Then the following tabs should be open:
            - about:blank
            - data/numbers/7.txt (active)

    Scenario: Opening in a new tab (related)
        Given I open about:blank
        When I set tabs.new_position.unrelated to next
        And I set tabs.new_position.related to prev
        And I run :tab-only
        And I run :open -t --related http://localhost:(port)/data/numbers/8.txt
        And I wait until data/numbers/8.txt is loaded
        Then the following tabs should be open:
            - data/numbers/8.txt (active)
            - about:blank

    Scenario: Opening in a new window
        Given I open about:blank
        When I run :tab-only
        And I run :open -w http://localhost:(port)/data/numbers/9.txt
        And I wait until data/numbers/9.txt is loaded
        Then the session should look like:
            windows:
            - tabs:
              - active: true
                history:
                - active: true
                  url: about:blank
            - tabs:
              - active: true
                history:
                - active: true
                  url: http://localhost:*/data/numbers/9.txt

    Scenario: Opening a quickmark
        When I run :quickmark-add http://localhost:(port)/data/numbers/10.txt quickmarktest
        And I run :open quickmarktest
        Then data/numbers/10.txt should be loaded
