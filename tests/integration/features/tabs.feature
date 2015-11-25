Feature: Tab management
    Tests for various :tab-* commands.

    Background:
        Given I clean up open tabs

    # :tab-close

    Scenario: :tab-close
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-close
        Then the session should look like:
          windows:
            - tabs:
              - history:
                - ...
                - url: http://localhost:*/data/numbers/1.txt
              - active: true
                history:
                - url: http://localhost:*/data/numbers/2.txt

    Scenario: :tab-close with count
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-close with count 1
        Then the session should look like:
          windows:
            - tabs:
              - history:
                - url: http://localhost:*/data/numbers/2.txt
              - active: true
                history:
                - url: http://localhost:*/data/numbers/3.txt

    Scenario: :tab-close with invalid count
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-close with count 23
        Then the session should look like:
          windows:
            - tabs:
              - history:
                - ...
                - url: http://localhost:*/data/numbers/1.txt
              - history:
                - url: http://localhost:*/data/numbers/2.txt
              - active: true
                history:
                - url: http://localhost:*/data/numbers/3.txt

    Scenario: :tab-close with select-on-remove = right
        When I set tabs -> select-on-remove to right
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close
        Then the session should look like:
          windows:
            - tabs:
              - history:
                - ...
                - url: http://localhost:*/data/numbers/1.txt
              - active: true
                history:
                - url: http://localhost:*/data/numbers/3.txt

    Scenario: :tab-close with select-on-remove = left
        When I set tabs -> select-on-remove to left
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close
        Then the session should look like:
          windows:
            - tabs:
              - active: true
                history:
                - ...
                - url: http://localhost:*/data/numbers/1.txt
              - history:
                - url: http://localhost:*/data/numbers/3.txt

    Scenario: :tab-close with select-on-remove = previous
        When I set tabs -> select-on-remove to previous
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I open data/numbers/4.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close
        Then the session should look like:
          windows:
            - tabs:
              - history:
                - ...
                - url: http://localhost:*/data/numbers/1.txt
              - history:
                - url: http://localhost:*/data/numbers/3.txt
              - active: true
                history:
                - url: http://localhost:*/data/numbers/4.txt

    Scenario: :tab-close with select-on-remove = left and --right
        When I set tabs -> select-on-remove to left
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close --right
        Then the session should look like:
          windows:
            - tabs:
              - history:
                - ...
                - url: http://localhost:*/data/numbers/1.txt
              - active: true
                history:
                - url: http://localhost:*/data/numbers/3.txt

    Scenario: :tab-close with select-on-remove = right and --left
        When I set tabs -> select-on-remove to right
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close --left
        Then the session should look like:
          windows:
            - tabs:
              - active: true
                history:
                - ...
                - url: http://localhost:*/data/numbers/1.txt
              - history:
                - url: http://localhost:*/data/numbers/3.txt

    Scenario: :tab-close with select-on-remove = left and --opposite
        When I set tabs -> select-on-remove to left
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close --opposite
        Then the session should look like:
          windows:
            - tabs:
              - history:
                - ...
                - url: http://localhost:*/data/numbers/1.txt
              - active: true
                history:
                - url: http://localhost:*/data/numbers/3.txt

    Scenario: :tab-close with select-on-remove = right and --opposite
        When I set tabs -> select-on-remove to right
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close --opposite
        Then the session should look like:
          windows:
            - tabs:
              - active: true
                history:
                - ...
                - url: http://localhost:*/data/numbers/1.txt
              - history:
                - url: http://localhost:*/data/numbers/3.txt

    Scenario: :tab-close with select-on-remove = previous and --opposite
        When I set tabs -> select-on-remove to previous
        And I run :tab-close --opposite
        Then the error "-o is not supported with 'tabs->select-on-remove' set to 'previous'!" should be shown.

    Scenario: :tab-close should restore selection behaviour
        When I set tabs -> select-on-remove to right
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I open data/numbers/4.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close --left
        And I run :tab-focus 2
        And I run :tab-close
        Then the session should look like:
          windows:
            - tabs:
              - history:
                - ...
                - url: http://localhost:*/data/numbers/1.txt
              - active: true
                history:
                - url: http://localhost:*/data/numbers/4.txt

    # :tab-only

    Scenario: :tab-only
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-only
        Then the session should look like:
          windows:
            - tabs:
              - active: true
                history:
                - url: http://localhost:*/data/numbers/3.txt

    Scenario: :tab-only with --left
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-only --left
        Then the session should look like:
          windows:
            - tabs:
              - history:
                - ...
                - url: http://localhost:*/data/numbers/1.txt
              - active: true
                history:
                - url: http://localhost:*/data/numbers/2.txt

    Scenario: :tab-only with --right
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-only --right
        Then the session should look like:
          windows:
            - tabs:
              - active: true
                history:
                - url: http://localhost:*/data/numbers/2.txt
              - history:
                - url: http://localhost:*/data/numbers/3.txt

    Scenario: :tab-only with --left and --right
        When I run :tab-only --left --right
        Then the error "Only one of -l/-r can be given!" should be shown.
