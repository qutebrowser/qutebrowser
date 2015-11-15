Feature: Going back and forward.
    Testing the :back/:forward commands.

    Scenario: Going back/forward
        Given I open data/backforward/1.txt
        When I open data/backforward/2.txt
        And I run :tab-only
        And I run :back
        And I wait until data/backforward/1.txt is loaded
        And I reload
        And I run :forward
        And I wait until data/backforward/2.txt is loaded
        And I reload
        Then the requests should be:
            data/backforward/1.txt
            data/backforward/2.txt
            data/backforward/1.txt
            data/backforward/2.txt
        And the session should look like:
            windows:
            - tabs:
              - history:
                - url: http://localhost:*/data/backforward/1.txt
                - active: true
                  url: http://localhost:*/data/backforward/2.txt

    Scenario: Going back in a new tab
        Given I open data/backforward/1.txt
        When I open data/backforward/2.txt
        And I run :tab-only
        And I run :back -t
        And I wait until data/backforward/1.txt is loaded
        Then the session should look like:
            windows:
            - tabs:
              - history:
                - url: http://localhost:*/data/backforward/1.txt
                - active: true
                  url: http://localhost:*/data/backforward/2.txt
              - active: true
                history:
                - active: true
                  url: http://localhost:*/data/backforward/1.txt
                - url: http://localhost:*/data/backforward/2.txt

    Scenario: Going back in a new background tab
        Given I open data/backforward/1.txt
        When I open data/backforward/2.txt
        And I run :tab-only
        And I run :back -b
        And I wait until data/backforward/1.txt is loaded
        Then the session should look like:
            windows:
            - tabs:
              - active: true
                history:
                - url: http://localhost:*/data/backforward/1.txt
                - active: true
                  url: http://localhost:*/data/backforward/2.txt
              - history:
                - active: true
                  url: http://localhost:*/data/backforward/1.txt
                - url: http://localhost:*/data/backforward/2.txt

    Scenario: Going back with count.
        Given I open data/backforward/1.txt
        When I open data/backforward/2.txt
        And I open data/backforward/3.txt
        And I run :tab-only
        And I run :back with count 2
        And I wait until data/backforward/1.txt is loaded
        And I reload
        Then the session should look like:
            windows:
            - tabs:
              - history:
                - active: true
                  url: http://localhost:*/data/backforward/1.txt
                - url: http://localhost:*/data/backforward/2.txt
                - url: http://localhost:*/data/backforward/3.txt

    Scenario: Going back in a new window
        Given I have a fresh instance
        When I open data/backforward/1.txt
        And I open data/backforward/2.txt
        And I run :back -w
        And I wait until data/backforward/1.txt is loaded
        Then the session should look like:
            windows:
            - tabs:
              - active: true
                history:
                - url: about:blank
                - url: http://localhost:*/data/backforward/1.txt
                - active: true
                  url: http://localhost:*/data/backforward/2.txt
            - tabs:
              - active: true
                history:
                - url: about:blank
                - active: true
                  url: http://localhost:*/data/backforward/1.txt
                - url: http://localhost:*/data/backforward/2.txt

    Scenario: Going back without history
        Given I open data/backforward/1.txt
        When I run :back
        Then the error "At beginning of history." should be shown.

    Scenario: Going forward without history
        Given I open data/backforward/1.txt
        When I run :forward
        Then the error "At end of history." should be shown.
