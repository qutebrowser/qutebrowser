Feature: Going back and forward.
    Testing the :back/:forward commands.

    Scenario: Going back/forward
        Given I open data/backforward/1.txt
        When I open data/backforward/2.txt
        And I run :back
        And I run :reload
        And I run :forward
        And I run :reload
        Then the requests should be:
            data/backforward/1.txt
            data/backforward/2.txt
            data/backforward/1.txt
            data/backforward/2.txt
