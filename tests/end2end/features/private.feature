# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Using private browsing

    Background:
        Given I open about:blank
        And I clean up open tabs

    @qtwebkit_ng_xfail: private browsing is not implemented yet
    Scenario: Opening new tab in private window
        When I open about:blank in a private window
        And I run :window-only
        And I open data/javascript/localstorage.html in a new tab
        Then the page should contain the plaintext "Local storage status: not working"

    @qtwebkit_ng_xfail: private browsing is not implemented yet
    Scenario: Opening new tab in private window with :navigate next
        When I open data/navigate in a private window
        And I run :window-only
        And I run :navigate -t next
        And I wait until data/navigate/next.html is loaded
        And I open data/javascript/localstorage.html
        Then the page should contain the plaintext "Local storage status: not working"

    Scenario: Using command history in a new private browsing window
        When I run :set-cmd-text :message-info "Hello World"
        And I run :command-accept
        And I open about:blank in a private window
        And I run :set-cmd-text :message-error "This should only be shown once"
        And I run :command-accept
        And I wait for the error "This should only be shown once"
        And I run :close
        And I run :set-cmd-text :
        And I run :command-history-prev
        And I run :command-accept
        # Then the error should not be shown again

    ## https://github.com/qutebrowser/qutebrowser/issues/1219

    @qtwebkit_ng_skip: private browsing is not implemented yet
    Scenario: Sharing cookies with private browsing
        When I open cookies/set?qute-test=42 without waiting in a private window
        And I wait until cookies is loaded
        And I open cookies in a new tab
        And I set general -> private-browsing to false
        Then the cookie qute-test should be set to 42

    Scenario: Opening private window with :navigate increment
        # Private window handled in commands.py
        When I open data/numbers/1.txt in a private window
        And I run :window-only
        And I run :navigate -w increment
        And I wait until data/numbers/2.txt is loaded
        Then the session should look like:
            windows:
            - private: True
              tabs:
              - history:
                - url: http://localhost:*/data/numbers/1.txt
            - private: True
              tabs:
              - history:
                - url: http://localhost:*/data/numbers/2.txt

    Scenario: Opening private window with :navigate next
        # Private window handled in navigate.py
        When I open data/navigate in a private window
        And I run :window-only
        And I run :navigate -w next
        And I wait until data/navigate/next.html is loaded
        Then the session should look like:
            windows:
            - private: True
              tabs:
              - history:
                - url: http://localhost:*/data/navigate
            - private: True
              tabs:
              - history:
                - url: http://localhost:*/data/navigate/next.html

    Scenario: Opening private window with :tab-clone
        When I open data/hello.txt in a private window
        And I run :window-only
        And I run :tab-clone -w
        And I wait until data/hello.txt is loaded
        Then the session should look like:
            windows:
            - private: True
              tabs:
              - history:
                - url: http://localhost:*/data/hello.txt
            - private: True
              tabs:
              - history:
                - url: http://localhost:*/data/hello.txt

    Scenario: Opening private window via :click-element
        When I open data/click_element.html in a private window
        And I run :window-only
        And I run :click-element --target window id link
        And I wait until data/hello.txt is loaded
        Then the session should look like:
            windows:
            - private: True
              tabs:
              - history:
                - url: http://localhost:*/data/click_element.html
            - private: True
              tabs:
              - history:
                - url: http://localhost:*/data/hello.txt
