Feature: Going back and forward.
    Testing the :back/:forward commands.

    Scenario: Going back/forward
        Given I open data/backforward/1.txt
        When I open data/backforward/2.txt
        And I run :back
        And I reload
        And I run :forward
        And I reload
        Then the requests should be:
            data/backforward/1.txt
            data/backforward/2.txt
            data/backforward/1.txt
            data/backforward/2.txt

   Scenario: Going back without history
       Given I open data/backforward/1.txt
       When I run :back
       Then the error "At beginning of history." should be shown.

   Scenario: Going forward without history
       Given I open data/backforward/1.txt
       When I run :forward
       Then the error "At end of history." should be shown.
