# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Invoking a new process
    Simulate what happens when running qutebrowser with an existing instance

    Background:
        Given I clean up open tabs

    Scenario: Using new_instance_open_target = tab
        When I set new_instance_open_target to tab
        And I open data/title.html
        And I open data/search.html as a URL
        Then the following tabs should be open:
            - data/title.html
            - data/search.html (active)

    Scenario: Using new_instance_open_target = tab-bg
        When I set new_instance_open_target to tab-bg
        And I open data/title.html
        And I open data/search.html as a URL
        Then the following tabs should be open:
            - data/title.html (active)
            - data/search.html

    Scenario: Using new_instance_open_target = window
        When I set new_instance_open_target to window
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

    Scenario: Using new_instance_open_target = private-window
        When I set new_instance_open_target to private-window
        And I open data/title.html
        And I open data/search.html as a URL
        Then the session should look like:
            windows:
            - tabs:
              - history:
                - url: about:blank
                - url: http://localhost:*/data/title.html
            - private: True
              tabs:
              - history:
                - url: http://localhost:*/data/search.html

    Scenario: Using new_instance_open_target_window = last-opened
        When I set new_instance_open_target to tab
        And I set new_instance_open_target_window to last-opened
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

    Scenario: Using new_instance_open_target_window = first-opened
        When I set new_instance_open_target to tab
        And I set new_instance_open_target_window to first-opened
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

    Scenario: Using target_window = first-opened after tab-give
        When I set new_instance_open_target to tab
        And I set new_instance_open_target_window to first-opened
        And I open data/title.html
        And I open data/search.html in a new tab
        And I run :tab-give
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
        When I set new_instance_open_target to tab
        And I set url.start_pages to ["http://localhost:(port)/data/hello.txt"]
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
