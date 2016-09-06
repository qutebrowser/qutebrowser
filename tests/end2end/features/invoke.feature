Feature: Invoking a new process
    Simulate what happens when running qutebrowser with an existing instance

    Background:
        Given I clean up open tabs

    Scenario: Using new-instance-open-target = tab
        When I set general -> new-instance-open-target to tab
        And I open data/title.html
        And I open data/search.html as a URL
        Then the following tabs should be open:
            - data/title.html
            - data/search.html (active)

    Scenario: Using new-instance-open-target = tab-bg
        When I set general -> new-instance-open-target to tab-bg
        And I open data/title.html
        And I open data/search.html as a URL
        Then the following tabs should be open:
            - data/title.html (active)
            - data/search.html

    Scenario: Using new-instance-open-target = window
        When I set general -> new-instance-open-target to window
        And I open data/title.html
        And I open data/search.html as a URL
        Then the session should look like:
            windows:
            - tabs:
              - history:
                - url: about:blank
                - url: http://localhost:*/data/title.html
            - tabs:
              - history:
                - url: http://localhost:*/data/search.html

    Scenario: Using new-instance-open-target.window = last-opened
        When I set general -> new-instance-open-target to tab
        And I set general -> new-instance-open-target.window to last-opened
        And I open data/title.html
        And I open data/search.html in a new window
        And I open data/hello.txt as a URL
        Then the session should look like:
            windows:
            - tabs:
              - history:
                - url: about:blank
                - url: http://localhost:*/data/title.html
            - tabs:
              - history:
                - url: http://localhost:*/data/search.html
              - history:
                - url: http://localhost:*/data/hello.txt

    Scenario: Using new-instance-open-target.window = first-opened
        When I set general -> new-instance-open-target to tab
        And I set general -> new-instance-open-target.window to first-opened
        And I open data/title.html
        And I open data/search.html in a new window
        And I open data/hello.txt as a URL
        Then the session should look like:
            windows:
            - tabs:
              - history:
                - url: about:blank
                - url: http://localhost:*/data/title.html
              - history:
                - url: http://localhost:*/data/hello.txt
            - tabs:
              - history:
                - url: http://localhost:*/data/search.html

    # issue #1060

    Scenario: Using target.window = first-opened after tab-detach
        When I set general -> new-instance-open-target to tab
        And I set general -> new-instance-open-target.window to first-opened
        And I open data/title.html
        And I open data/search.html in a new tab
        And I run :tab-detach
        And I wait until data/search.html is loaded
        And I open data/hello.txt as a URL
        Then the session should look like:
            windows:
            - tabs:
              - history:
                - url: about:blank
                - url: http://localhost:*/data/title.html
              - history:
                - url: http://localhost:*/data/hello.txt
            - tabs:
              - history:
                - url: http://localhost:*/data/search.html

    Scenario: Opening a new qutebrowser instance with no parameters
        When I set general -> new-instance-open-target to tab
        And I set general -> startpage to http://localhost:(port)/data/hello.txt
        And I open data/title.html
        And I spawn a new window
        And I wait until data/hello.txt is loaded
        Then the session should look like:
            windows:
            - tabs:
              - history:
                - url: about:blank
                - url: http://localhost:*/data/title.html
            - tabs:
              - history:
                - url: http://localhost:*/data/hello.txt
