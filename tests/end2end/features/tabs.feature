# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Tab management
    Tests for various :tab-* commands.

    Background:
        Given I clean up open tabs
        And I set tabs -> tabs-are-windows to false

    # :tab-close

    Scenario: :tab-close
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-close
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt (active)

    Scenario: :tab-close with count
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-close with count 1
        Then the following tabs should be open:
            - data/numbers/2.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-close with invalid count
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-close with count 23
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-close with select-on-remove = next
        When I set tabs -> select-on-remove to next
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-close with select-on-remove = prev
        When I set tabs -> select-on-remove to prev
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close
        Then the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/3.txt

    Scenario: :tab-close with select-on-remove = last-used
        When I set tabs -> select-on-remove to last-used
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I open data/numbers/4.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/3.txt
            - data/numbers/4.txt (active)

    Scenario: :tab-close with select-on-remove = prev and --next
        When I set tabs -> select-on-remove to prev
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close --next
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-close with select-on-remove = next and --prev
        When I set tabs -> select-on-remove to next
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close --prev
        Then the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/3.txt

    Scenario: :tab-close with select-on-remove = prev and --opposite
        When I set tabs -> select-on-remove to prev
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close --opposite
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-close with select-on-remove = next and --opposite
        When I set tabs -> select-on-remove to next
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close --opposite
        Then the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/3.txt

    Scenario: :tab-close with select-on-remove = last-used and --opposite
        When I set tabs -> select-on-remove to last-used
        And I run :tab-close --opposite
        Then the error "-o is not supported with 'tabs->select-on-remove' set to 'last-used'!" should be shown

    Scenario: :tab-close should restore selection behavior
        When I set tabs -> select-on-remove to next
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I open data/numbers/4.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close --prev
        And I run :tab-focus 2
        And I run :tab-close
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/4.txt (active)

    # :tab-only

    Scenario: :tab-only
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-only
        Then the following tabs should be open:
            - data/numbers/3.txt (active)

    Scenario: :tab-only with --prev
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-only --prev
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt (active)

    Scenario: :tab-only with --next
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-only --next
        Then the following tabs should be open:
            - data/numbers/2.txt (active)
            - data/numbers/3.txt

    Scenario: :tab-only with --prev and --next
        When I run :tab-only --prev --next
        Then the error "Only one of -p/-n can be given!" should be shown

    # :tab-focus

    Scenario: :tab-focus with invalid index
        When I run :tab-focus foo
        Then the error "Invalid value foo." should be shown

    Scenario: :tab-focus with index
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt (active)
            - data/numbers/3.txt

    Scenario: :tab-focus without index/count
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-focus
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-focus with invalid index
        When I run :tab-focus 23
        Then the error "There's no tab with index 23!" should be shown

    Scenario: :tab-focus with very big index
        When I run :tab-focus 99999999999999
        Then the error "There's no tab with index 99999999999999!" should be shown

    Scenario: :tab-focus with count
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus with count 2
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt (active)
            - data/numbers/3.txt

    Scenario: :tab-focus with count and index
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 4 with count 2
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt (active)
            - data/numbers/3.txt

    Scenario: :tab-focus last
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 1
        And I run :tab-focus 3
        And I run :tab-focus last
        Then the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/2.txt
            - data/numbers/3.txt

    Scenario: :tab-focus with current tab number
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 1
        And I run :tab-focus 3
        And I run :tab-focus 3
        Then the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/2.txt
            - data/numbers/3.txt

    Scenario: :tab-focus with -1
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 1
        And I run :tab-focus -1
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-focus negative index
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus -2
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt (active)
            - data/numbers/3.txt

    Scenario: :tab-focus with invalid negative index
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus -5
        Then the error "There's no tab with index -1!" should be shown

    Scenario: :tab-focus last with no last focused tab
        When I run :tab-focus last
        Then the error "No last focused tab!" should be shown

    # tab-prev/tab-next

    Scenario: :tab-prev
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I run :tab-prev
        Then the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/2.txt

    Scenario: :tab-next
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I run :tab-focus 1
        And I run :tab-next
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt (active)

    Scenario: :tab-prev with count
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-prev with count 2
        Then the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/2.txt
            - data/numbers/3.txt

    Scenario: :tab-next with count
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 1
        And I run :tab-next with count 2
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-prev on first tab without wrap
        When I set tabs -> wrap to false
        And I open data/numbers/1.txt
        And I run :tab-prev
        Then the error "First tab" should be shown

    Scenario: :tab-next with last tab without wrap
        When I set tabs -> wrap to false
        And I open data/numbers/1.txt
        And I run :tab-next
        Then the error "Last tab" should be shown

    Scenario: :tab-prev on first tab with wrap
        When I set tabs -> wrap to true
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 1
        And I run :tab-prev
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-next with last tab with wrap
        When I set tabs -> wrap to true
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-next
        Then the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/2.txt
            - data/numbers/3.txt

    Scenario: :tab-next with last tab, wrap and count
        When I set tabs -> wrap to true
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-next with count 2
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt (active)
            - data/numbers/3.txt

    # :tab-move

    Scenario: :tab-move with absolute position.
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-move
        Then the following tabs should be open:
            - data/numbers/3.txt (active)
            - data/numbers/1.txt
            - data/numbers/2.txt

    Scenario: :tab-move with absolute position and count.
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-move with count 2
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/3.txt (active)
            - data/numbers/2.txt

    Scenario: :tab-move with absolute position and invalid count.
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-move with count 23
        Then the error "Can't move tab to position 23!" should be shown.
        And the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-move with index.
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-move 2
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/3.txt (active)
            - data/numbers/2.txt

    Scenario: :tab-move with negative index.
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-move -3
        Then the following tabs should be open:
            - data/numbers/3.txt (active)
            - data/numbers/1.txt
            - data/numbers/2.txt

    Scenario: :tab-move with invalid index.
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-move -5
        Then the error "Can't move tab to position -1!" should be shown.
        And the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-move with index and count.
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-move 1 with count 2
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/3.txt (active)
            - data/numbers/2.txt

    Scenario: :tab-move with index and invalid count.
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-move -2 with count 4
        Then the error "Can't move tab to position 4!" should be shown.
        And the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-move with relative position (negative).
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-move -
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/3.txt (active)
            - data/numbers/2.txt

    Scenario: :tab-move with relative position (positive).
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 1
        And I run :tab-move +
        Then the following tabs should be open:
            - data/numbers/2.txt
            - data/numbers/1.txt (active)
            - data/numbers/3.txt

    Scenario: :tab-move with relative position (negative) and count.
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-move - with count 2
        Then the following tabs should be open:
            - data/numbers/3.txt (active)
            - data/numbers/1.txt
            - data/numbers/2.txt

    Scenario: :tab-move with relative position and too big count.
        When I set tabs -> wrap to false
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 1
        And I run :tab-move + with count 3
        Then the error "Can't move tab to position 4!" should be shown

    Scenario: :tab-move with relative position (positive) and wrap
        When I set tabs -> wrap to true
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-move +
        Then the following tabs should be open:
            - data/numbers/3.txt (active)
            - data/numbers/1.txt
            - data/numbers/2.txt

    Scenario: :tab-move with relative position (negative), wrap and count
        When I set tabs -> wrap to true
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 1
        And I run :tab-move - with count 8
        Then the following tabs should be open:
            - data/numbers/2.txt
            - data/numbers/1.txt (active)
            - data/numbers/3.txt

    Scenario: Make sure :tab-move retains metadata
        When I open data/title.html
        And I open data/hello.txt in a new tab
        And I run :tab-focus 1
        And I run :tab-move +
        Then the session should look like:
            windows:
            - tabs:
              - history:
                - url: http://localhost:*/data/hello.txt
              - active: true
                history:
                - url: about:blank
                - url: http://localhost:*/data/title.html
                  title: Test title

    # :tab-clone

    Scenario: :tab-clone with -b and -w
        When I run :tab-clone -b -w
        Then the error "Only one of -b/-w can be given!" should be shown.

    Scenario: Cloning a tab with history and title
        When I open data/title.html
        And I run :tab-clone
        And I wait until data/title.html is loaded
        Then the session should look like:
            windows:
            - tabs:
              - history:
                - url: about:blank
                - url: http://localhost:*/data/title.html
                  title: Test title
              - active: true
                history:
                - url: about:blank
                - url: http://localhost:*/data/title.html
                  title: Test title

    Scenario: Cloning zoom value
        When I open data/hello.txt
        And I run :zoom 120
        And I run :tab-clone
        And I wait until data/hello.txt is loaded
        Then the session should look like:
            windows:
            - tabs:
              - history:
                - url: about:blank
                - url: http://localhost:*/data/hello.txt
                  zoom: 1.2
              - active: true
                history:
                - url: about:blank
                - url: http://localhost:*/data/hello.txt
                  zoom: 1.2

    Scenario: Cloning to background tab
        When I open data/hello2.txt
        And I run :tab-clone -b
        And I wait until data/hello2.txt is loaded
        Then the following tabs should be open:
            - data/hello2.txt (active)
            - data/hello2.txt

    Scenario: Cloning to new window
        When I open data/title.html
        And I run :tab-clone -w
        And I wait until data/title.html is loaded
        Then the session should look like:
            windows:
            - tabs:
              - active: true
                history:
                - url: about:blank
                - url: http://localhost:*/data/title.html
                  title: Test title
            - tabs:
              - active: true
                history:
                - url: about:blank
                - url: http://localhost:*/data/title.html
                  title: Test title

    Scenario: Cloning with tabs-are-windows = true
        When I open data/title.html
        And I set tabs -> tabs-are-windows to true
        And I run :tab-clone
        And I wait until data/title.html is loaded
        Then the session should look like:
            windows:
            - tabs:
              - active: true
                history:
                - url: about:blank
                - url: http://localhost:*/data/title.html
                  title: Test title
            - tabs:
              - active: true
                history:
                - url: about:blank
                - url: http://localhost:*/data/title.html
                  title: Test title

    # https://github.com/qutebrowser/qutebrowser/issues/2289

    @qtwebkit_skip @qt==5.8.0
    Scenario: Cloning a tab with a special URL
        When I open chrome://gpu
        And I run :tab-clone
        Then the error "Can't serialize special URL!" should be shown

    @qtwebkit_skip @qt<5.9
    Scenario: Cloning a tab with a view-source URL
        When I open view-source:http://localhost:(port)
        And I run :tab-clone
        Then the error "Can't serialize special URL!" should be shown

    @qtwebkit_skip @qt>=5.9
    Scenario: Cloning a tab with a special URL (Qt 5.9)
        When I open chrome://gpu
        And I run :tab-clone
        Then no crash should happen

    # :tab-detach

    Scenario: Detaching a tab
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I run :tab-detach
        And I wait until data/numbers/2.txt is loaded
        Then the session should look like:
            windows:
            - tabs:
              - history:
                - url: about:blank
                - url: http://localhost:*/data/numbers/1.txt
            - tabs:
              - history:
                - url: http://localhost:*/data/numbers/2.txt

    Scenario: Detaching multiple tabs
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I open data/numbers/4.txt in a new tab
        And I open data/numbers/5.txt in a new tab
        And I open data/numbers/6.txt in a new tab
        And I open data/numbers/7.txt in a new tab
        And I run :tab-detach 4-7
        And I wait until data/numbers/7.txt is loaded
        Then the session should look like:
            windows:
            - tabs:
              - history:
                - url: about:blank
                - url: http://localhost:*/data/numbers/1.txt
              - history:
                - url: http://localhost:*/data/numbers/2.txt
              - history:
                - url: http://localhost:*/data/numbers/3.txt
            - tabs:
              - history:
                - url: http://localhost:*/data/numbers/4.txt
              - history:
                - url: http://localhost:*/data/numbers/5.txt
              - history:
                - url: http://localhost:*/data/numbers/6.txt
              - history:
                - url: http://localhost:*/data/numbers/7.txt

    Scenario: Detach tab from window with only one tab
        When I open data/hello.txt
        And I run :tab-detach
        Then the error "Cannot detach all tabs." should be shown

    # :undo

    Scenario: Undo without any closed tabs
        Given I have a fresh instance
        When I run :undo
        Then the error "Nothing to undo!" should be shown

    Scenario: Undo closing a tab
        When I open data/numbers/1.txt
        And I run :tab-only
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt
        And I run :tab-close
        And I run :undo
        And I wait until data/numbers/3.txt is loaded
        Then the session should look like:
            windows:
            - tabs:
              - history:
                - url: about:blank
                - url: http://localhost:*/data/numbers/1.txt
              - active: true
                history:
                - url: http://localhost:*/data/numbers/2.txt
                - url: http://localhost:*/data/numbers/3.txt

    @qtwebengine_flaky
    Scenario: Undo with auto-created last tab
        When I open data/hello.txt
        And I run :tab-only
        And I set tabs -> last-close to blank
        And I run :tab-close
        And I wait until about:blank is loaded
        And I run :undo
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - data/hello.txt (active)

    @qtwebengine_flaky
    Scenario: Undo with auto-created last tab, with history
        When I open data/hello.txt
        And I open data/hello2.txt
        And I run :tab-only
        And I set tabs -> last-close to blank
        And I run :tab-close
        And I wait until about:blank is loaded
        And I run :undo
        And I wait until data/hello2.txt is loaded
        Then the following tabs should be open:
            - data/hello2.txt (active)

    Scenario: Undo with auto-created last tab (startpage)
        When I open data/hello.txt
        And I run :tab-only
        And I set tabs -> last-close to startpage
        And I set general -> startpage to http://localhost:(port)/data/numbers/4.txt,http://localhost:(port)/data/numbers/5.txt
        And I run :tab-close
        And I wait until data/numbers/4.txt is loaded
        And I run :undo
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - data/hello.txt (active)

    Scenario: Undo with auto-created last tab (default-page)
        When I open data/hello.txt
        And I run :tab-only
        And I set tabs -> last-close to default-page
        And I set general -> default-page to http://localhost:(port)/data/numbers/6.txt
        And I run :tab-close
        And I wait until data/numbers/6.txt is loaded
        And I run :undo
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - data/hello.txt (active)

    Scenario: Double-undo with single tab on last-close default page
        Given I have a fresh instance
        When I open about:blank
        And I set tabs -> last-close to default-page
        And I set general -> default-page to about:blank
        And I run :undo
        And I run :undo
        Then the error "Nothing to undo!" should be shown
        And the error "Nothing to undo!" should be shown

    Scenario: Undo a tab closed by index
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-close with count 1
        And I run :undo
        Then the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/2.txt
            - data/numbers/3.txt

    Scenario: Undo a tab closed after switching tabs
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-close with count 1
        And I run :tab-focus 2
        And I run :undo
        Then the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/2.txt
            - data/numbers/3.txt

    Scenario: Undo a tab closed after rearranging tabs
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-close with count 1
        And I run :tab-focus 2
        And I run :tab-move with count 1
        And I run :undo
        Then the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/3.txt
            - data/numbers/2.txt

    Scenario: Undo a tab closed after new tab opened
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I run :tab-close with count 1
        And I open data/numbers/3.txt in a new tab
        And I run :undo
        And I wait until data/numbers/1.txt is loaded
        Then the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/2.txt
            - data/numbers/3.txt

    # last-close

    # FIXME:qtwebengine
    @qtwebengine_skip: Waits for an earlier about:blank and fails
    Scenario: last-close = blank
        When I open data/hello.txt
        And I set tabs -> last-close to blank
        And I run :tab-only
        And I run :tab-close
        And I wait until about:blank is loaded
        Then the following tabs should be open:
            - about:blank (active)

    Scenario: last-close = startpage
        When I set general -> startpage to http://localhost:(port)/data/numbers/7.txt,http://localhost:(port)/data/numbers/8.txt
        And I set tabs -> last-close to startpage
        And I open data/hello.txt
        And I run :tab-only
        And I run :tab-close
        And I wait until data/numbers/7.txt is loaded
        Then the following tabs should be open:
            - data/numbers/7.txt (active)

    Scenario: last-close = default-page
        When I set general -> default-page to http://localhost:(port)/data/numbers/9.txt
        And I set tabs -> last-close to default-page
        And I open data/hello.txt
        And I run :tab-only
        And I run :tab-close
        And I wait until data/numbers/9.txt is loaded
        Then the following tabs should be open:
            - data/numbers/9.txt (active)

    Scenario: last-close = close
        When I open data/hello.txt
        And I set tabs -> last-close to close
        And I run :tab-only
        And I run :tab-close
        Then qutebrowser should quit

    # tab settings

    Scenario: opening links with tabs->background-tabs true
        When I set tabs -> background-tabs to true
        And I open data/hints/html/simple.html
        And I hint with args "all tab" and follow a
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - data/hints/html/simple.html (active)
            - data/hello.txt

    Scenario: opening tab with tabs->new-tab-position prev
        When I set tabs -> new-tab-position to prev
        And I set tabs -> background-tabs to false
        And I open about:blank
        And I open data/hints/html/simple.html in a new tab
        And I run :click-element id link --target=tab
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - about:blank
            - data/hello.txt (active)
            - data/hints/html/simple.html

    Scenario: opening tab with tabs->new-tab-position next
        When I set tabs -> new-tab-position to next
        And I set tabs -> background-tabs to false
        And I open about:blank
        And I open data/hints/html/simple.html in a new tab
        And I run :click-element id link --target=tab
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - about:blank
            - data/hints/html/simple.html
            - data/hello.txt (active)

    Scenario: opening tab with tabs->new-tab-position first
        When I set tabs -> new-tab-position to first
        And I set tabs -> background-tabs to false
        And I open about:blank
        And I open data/hints/html/simple.html in a new tab
        And I run :click-element id link --target=tab
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - data/hello.txt (active)
            - about:blank
            - data/hints/html/simple.html

    Scenario: opening tab with tabs->new-tab-position last
        When I set tabs -> new-tab-position to last
        And I set tabs -> background-tabs to false
        And I open data/hints/html/simple.html
        And I open about:blank in a new tab
        And I run :tab-focus last
        And I run :click-element id link --target=tab
        And I wait until data/hello.txt is loaded
        Then the following tabs should be open:
            - data/hints/html/simple.html
            - about:blank
            - data/hello.txt (active)

    # :buffer

    Scenario: :buffer without args
        When I run :buffer
        Then the error "buffer: The following arguments are required: index" should be shown

    Scenario: :buffer with a matching title
        When I open data/title.html
        And I open data/search.html in a new tab
        And I open data/scroll/simple.html in a new tab
        And I run :buffer "Searching text"
        And I wait for "Current tab changed, focusing <qutebrowser.browser.* tab_id=* url='http://localhost:*/data/search.html'>" in the log
        Then the following tabs should be open:
            - data/title.html
            - data/search.html (active)
            - data/scroll/simple.html

    Scenario: :buffer with no matching title
        When I run :buffer "invalid title"
        Then the error "No matching tab for: invalid title" should be shown

    Scenario: :buffer with matching title and two windows
        When I open data/title.html
        And I open data/search.html in a new tab
        And I open data/scroll/simple.html in a new tab
        And I open data/caret.html in a new window
        And I open data/paste_primary.html in a new tab
        And I run :buffer "Scrolling"
        And I wait for "Focus object changed: *" in the log
        Then the session should look like:
            windows:
            - active: true
              tabs:
              - history:
                - url: about:blank
                - url: http://localhost:*/data/title.html
              - history:
                - url: http://localhost:*/data/search.html
              - active: true
                history:
                - url: http://localhost:*/data/scroll/simple.html
            - tabs:
              - history:
                - url: http://localhost:*/data/caret.html
              - active: true
                history:
                - url: http://localhost:*/data/paste_primary.html

    Scenario: :buffer with no matching index
        When I open data/title.html
        And I run :buffer "666"
        Then the error "There's no tab with index 666!" should be shown

    Scenario: :buffer with no matching window index
        When I open data/title.html
        And I run :buffer "99/1"
        Then the error "There's no window with id 99!" should be shown

    @qtwebengine_flaky
    Scenario: :buffer with matching window index
        Given I have a fresh instance
        When I open data/title.html
        And I open data/search.html in a new tab
        And I open data/scroll/simple.html in a new tab
        And I run :open -w http://localhost:(port)/data/caret.html
        And I open data/paste_primary.html in a new tab
        And I wait until data/caret.html is loaded
        And I run :buffer "0/2"
        And I wait for "Focus object changed: *" in the log
        Then the session should look like:
            windows:
            - active: true
              tabs:
              - history:
                - url: about:blank
                - url: http://localhost:*/data/title.html
              - active: true
                history:
                - url: http://localhost:*/data/search.html
              - history:
                - url: http://localhost:*/data/scroll/simple.html
            - tabs:
              - history:
                - url: http://localhost:*/data/caret.html
              - active: true
                history:
                - url: http://localhost:*/data/paste_primary.html

    Scenario: :buffer with wrong argument (-1)
        When I open data/title.html
        And I run :buffer "-1"
        Then the error "There's no tab with index -1!" should be shown

    Scenario: :buffer with wrong argument (/)
        When I open data/title.html
        And I run :buffer "/"
        Then the following tabs should be open:
            - data/title.html (active)

    Scenario: :buffer with wrong argument (//)
        When I open data/title.html
        And I run :buffer "//"
        Then the following tabs should be open:
            - data/title.html (active)

    Scenario: :buffer with wrong argument (0/x)
        When I open data/title.html
        And I run :buffer "0/x"
        Then the error "No matching tab for: 0/x" should be shown

    Scenario: :buffer with wrong argument (1/2/3)
        When I open data/title.html
        And I run :buffer "1/2/3"
        Then the error "No matching tab for: 1/2/3" should be shown

    # Other

    Scenario: Using :tab-next after closing last tab (#1448)
        When I set tabs -> last-close to close
        And I run :tab-only
        And I run :tab-close ;; tab-next
        Then qutebrowser should quit
        And no crash should happen

    Scenario: Using :tab-prev after closing last tab (#1448)
        When I set tabs -> last-close to close
        And I run :tab-only
        And I run :tab-close ;; tab-prev
        Then qutebrowser should quit
        And no crash should happen

    Scenario: Opening link with tabs-are-windows set (#2162)
        When I set tabs -> tabs-are-windows to true
        And I open data/hints/html/simple.html
        And I hint with args "all tab-fg" and follow a
        And I wait until data/hello.txt is loaded
        Then the session should look like:
            windows:
            - tabs:
              - history:
                - url: about:blank
                - url: http://localhost:*/data/hints/html/simple.html
            - tabs:
              - history:
                - url: http://localhost:*/data/hello.txt

    # :tab-pin

    Scenario: :tab-pin command
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-pin
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt
            - data/numbers/3.txt (active) (pinned)

    Scenario: :tab-pin unpin
        When I open data/numbers/1.txt
        And I run :tab-pin
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-pin
        And I run :tab-pin
        Then the following tabs should be open:
            - data/numbers/1.txt (pinned)
            - data/numbers/2.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-pin to index 2
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-pin with count 2
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt (pinned)
            - data/numbers/3.txt (active)

    Scenario: :tab-pin with an invalid count
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-pin with count 23
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt
            - data/numbers/3.txt (active)

    Scenario: Pinned :tab-close prompt yes
        When I open data/numbers/1.txt
        And I run :tab-pin
        And I open data/numbers/2.txt in a new tab
        And I run :tab-pin
        And I run :tab-close
        And I wait for "*want to close a pinned tab*" in the log
        And I run :prompt-accept yes
        Then the following tabs should be open:
            - data/numbers/1.txt (active) (pinned)

    Scenario: Pinned :tab-close prompt no
        When I open data/numbers/1.txt
        And I run :tab-pin
        And I open data/numbers/2.txt in a new tab
        And I run :tab-pin
        And I run :tab-close
        And I wait for "*want to close a pinned tab*" in the log
        And I run :prompt-accept no
        Then the following tabs should be open:
            - data/numbers/1.txt (pinned)
            - data/numbers/2.txt (active) (pinned)

    Scenario: Pinned :tab-only prompt yes
        When I open data/numbers/1.txt
        And I run :tab-pin
        And I open data/numbers/2.txt in a new tab
        And I run :tab-pin
        And I run :tab-next
        And I run :tab-only
        And I wait for "*want to close a pinned tab*" in the log
        And I run :prompt-accept yes
        Then the following tabs should be open:
            - data/numbers/1.txt (active) (pinned)

    Scenario: Pinned :tab-only prompt no
        When I open data/numbers/1.txt
        And I run :tab-pin
        And I open data/numbers/2.txt in a new tab
        And I run :tab-pin
        And I run :tab-next
        And I run :tab-only
        And I wait for "*want to close a pinned tab*" in the log
        And I run :prompt-accept no
        Then the following tabs should be open:
            - data/numbers/1.txt (active) (pinned)
            - data/numbers/2.txt (pinned)

    Scenario: Pinned :tab-only close all but pinned tab
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I run :tab-pin
        And I run :tab-only
        Then the following tabs should be open:
            - data/numbers/2.txt (active) (pinned)

    Scenario: :tab-pin open url
        When I open data/numbers/1.txt
        And I run :tab-pin
        And I open data/numbers/2.txt without waiting
        Then the message "Tab is pinned!" should be shown
        And the following tabs should be open:
            - data/numbers/1.txt (active) (pinned)

    Scenario: Cloning a pinned tab
        When I open data/numbers/1.txt
        And I run :tab-pin
        And I run :tab-clone
        And I wait until data/numbers/1.txt is loaded
        Then the following tabs should be open:
            - data/numbers/1.txt (pinned)
            - data/numbers/1.txt (pinned) (active)

    Scenario: Undo a pinned tab
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I run :tab-pin
        And I run :tab-close --force
        And I run :undo
        And I wait until data/numbers/2.txt is loaded
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt (pinned) (active)
