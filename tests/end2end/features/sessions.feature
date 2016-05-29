Feature: Saving and loading sessions

  # https://github.com/The-Compiler/qutebrowser/issues/879

  Scenario: Saving a session with a page using history.replaceState()
    When I open data/sessions/history_replace_state.html
    Then the javascript message "Calling history.replaceState" should be logged
    And the session should look like:
      windows:
      - tabs:
        - history:
          - url: about:blank
          - active: true
            url: http://localhost:*/data/sessions/history_replace_state.html?state=2
            title: Test title

  Scenario: Saving a session with a page using history.replaceState() and navigating away
    When I open data/sessions/history_replace_state.html
    And I open data/hello.txt
    Then the javascript message "Calling history.replaceState" should be logged
    And the session should look like:
      windows:
      - tabs:
        - history:
          - url: about:blank
          - url: http://localhost:*/data/sessions/history_replace_state.html?state=2
            # What we'd *really* expect here is "Test title", but that
            # workaround is the best we can do.
            title: http://localhost:*/data/sessions/history_replace_state.html?state=2
          - active: true
            url: http://localhost:*/data/hello.txt
