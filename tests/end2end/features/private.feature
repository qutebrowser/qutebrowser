# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Using private browsing

    Background:
        Given I open about:blank
        And I clean up open tabs

    Scenario: Opening new tab in private window
        When I open about:blank in a private window
        And I open cookies/set?qute-private-test=42 without waiting in a new tab
        And I wait until cookies is loaded
        And I run :close
        And I wait for "removed: main-window" in the log
        And I open cookies
        Then the cookie qute-private-test should not be set

    Scenario: Opening new tab in private window with :navigate next
        When I open data/navigate in a private window
        And I run :navigate -t next
        And I wait until data/navigate/next.html is loaded
        And I open cookies/set?qute-private-test=42 without waiting
        And I wait until cookies is loaded
        And I run :close
        And I wait for "removed: main-window" in the log
        And I open cookies
        Then the cookie qute-private-test should not be set

    Scenario: Using command history in a new private browsing window
        When I run :set-cmd-text :message-info "Hello World"
        And I run :command-accept
        And I open about:blank in a private window
        And I run :set-cmd-text :message-error "This should only be shown once"
        And I run :command-accept
        And I wait for the error "This should only be shown once"
        And I run :close
        And I wait for "removed: main-window" in the log
        And I run :set-cmd-text :
        And I run :command-history-prev
        And I run :command-accept
        # Then the error should not be shown again

    ## https://github.com/qutebrowser/qutebrowser/issues/1219

    Scenario: Make sure private data is cleared when closing last private window
        When I open about:blank in a private window
        And I open cookies/set?cookie-to-delete=1 without waiting in a new tab
        And I wait until cookies is loaded
        And I run :close
        And I open about:blank in a private window
        And I open cookies
        Then the cookie cookie-to-delete should not be set

    Scenario: Make sure private data is not cleared when closing a private window but another remains
        When I open about:blank in a private window
        And I open about:blank in a private window
        And I open cookies/set?cookie-to-preserve=1 without waiting in a new tab
        And I wait until cookies is loaded
        And I run :close
        And I open about:blank in a private window
        And I open cookies
        Then the cookie cookie-to-preserve should be set to 1

    Scenario: Sharing cookies with private browsing
        When I open cookies/set?qute-test=42 without waiting in a private window
        And I wait until cookies is loaded
        And I open cookies in a new tab
        And I set content.private_browsing to false
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

    Scenario: Skipping private window when saving session
        When I open data/hello.txt in a private window
        And I run :session-save (tmpdir)/session.yml
        And I wait for "Saved session */session.yml." in the log
        Then the file session.yml should not contain "hello.txt"

    # https://github.com/qutebrowser/qutebrowser/issues/2638
    Scenario: Turning off javascript with private browsing
        When I set content.javascript.enabled to false
        And I open data/javascript/consolelog.html in a private window
        Then the javascript message "console.log works!" should not be logged

    # Probably needs qutewm to work properly...
    @qtwebkit_skip: Only applies to QtWebEngine @xfail_norun
    Scenario: Make sure local storage is isolated with private browsing
        When I open data/hello.txt in a private window
        And I run :jseval localStorage.qute_private_test = 42
        And I wait for "42" in the log
        And I run :close
        And I wait for "removed: main-window" in the log
        And I open data/hello.txt
        And I run :jseval localStorage.qute_private_test
        Then "No output or error" should be logged

    Scenario: Opening quickmark in private window
        When I open data/numbers/1.txt in a private window
        And I run :window-only
        And I run :quickmark-add http://localhost:(port)/data/numbers/2.txt two
        And I run :quickmark-load two
        And I wait until data/numbers/2.txt is loaded
        Then the session should look like:
            windows:
            - private: True
              tabs:
              - history:
                - url: http://localhost:*/data/numbers/1.txt
                - url: http://localhost:*/data/numbers/2.txt

  @skip  # Too flaky
  Scenario: Saving a private session with only-active-window
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a private window
        And I open data/numbers/4.txt in a new tab
        And I open data/numbers/5.txt in a new tab
        And I run :session-save --only-active-window window_session_name
        And I run :window-only
        And I wait for "removed: tab" in the log
        And I wait for "removed: tab" in the log
        And I run :tab-only
        And I wait for "removed: tab" in the log
        And I wait for "removed: tab" in the log
        And I wait for "removed: tab" in the log
        And I run :session-load -c window_session_name
        And I wait until data/numbers/5.txt is loaded
        Then the session should look like:
            windows:
                - tabs:
                    - history:
                        - url: http://localhost:*/data/numbers/3.txt
                    - history:
                        - url: http://localhost:*/data/numbers/4.txt
                    - history:
                        - active: true
                          url: http://localhost:*/data/numbers/5.txt

    # https://github.com/qutebrowser/qutebrowser/issues/5810

    Scenario: Using qute:// scheme after reiniting private profile
        When I open about:blank in a private window
        And I run :close
        And I open qute://version in a private window
        Then the page should contain the plaintext "Version info"

    Scenario: Downloading after reiniting private profile
        When I open about:blank in a private window
        And I run :close
        And I open data/downloads/downloads.html in a private window
        And I run :click-element id download
        And I wait for "*PromptMode.download*" in the log
        And I run :leave-mode
        Then "Removed download *: download.bin *" should be logged

    Scenario: Adblocking after reiniting private profile
        When I open about:blank in a private window
        And I run :close
        And I set content.host_blocking.lists to ["http://localhost:(port)/data/adblock/qutebrowser"]
        And I run :adblock-update
        And I wait for the message "adblock: Read 1 hosts from 1 sources."
        And I open data/adblock/external_logo.html in a private window
        Then "Request to qutebrowser.org blocked by host blocker." should be logged

    @pyqt!=5.15.0   # cookie filtering is broken on QtWebEngine 5.15.0
    Scenario: Cookie filtering after reiniting private profile
        When I open about:blank in a private window
        And I run :close
        And I set content.cookies.accept to never
        And I open data/title.html in a private window
        And I open cookies/set?unsuccessful-cookie=1 without waiting in a new tab
        And I wait until cookies is loaded
        And I open cookies
        Then the cookie unsuccessful-cookie should not be set

    Scenario: Disabling JS after reiniting private profile
        When I open about:blank in a new window
        And I run :window-only
        And I set content.javascript.enabled to false
        And I open about:blank in a private window
        And I run :close
        And I open data/javascript/enabled.html in a private window
        Then the page should contain the plaintext "JavaScript is disabled"
