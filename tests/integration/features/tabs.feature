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

    Scenario: :tab-close with select-on-remove = right
        When I set tabs -> select-on-remove to right
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-close with select-on-remove = left
        When I set tabs -> select-on-remove to left
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close
        Then the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/3.txt

    Scenario: :tab-close with select-on-remove = previous
        When I set tabs -> select-on-remove to previous
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

    Scenario: :tab-close with select-on-remove = left and --right
        When I set tabs -> select-on-remove to left
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close --right
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-close with select-on-remove = right and --left
        When I set tabs -> select-on-remove to right
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close --left
        Then the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/3.txt

    Scenario: :tab-close with select-on-remove = left and --opposite
        When I set tabs -> select-on-remove to left
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close --opposite
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/3.txt (active)

    Scenario: :tab-close with select-on-remove = right and --opposite
        When I set tabs -> select-on-remove to right
        And I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-close --opposite
        Then the following tabs should be open:
            - data/numbers/1.txt (active)
            - data/numbers/3.txt

    Scenario: :tab-close with select-on-remove = previous and --opposite
        When I set tabs -> select-on-remove to previous
        And I run :tab-close --opposite
        Then the error "-o is not supported with 'tabs->select-on-remove' set to 'previous'!" should be shown

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

    Scenario: :tab-only with --left
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-only --left
        Then the following tabs should be open:
            - data/numbers/1.txt
            - data/numbers/2.txt (active)

    Scenario: :tab-only with --right
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 2
        And I run :tab-only --right
        Then the following tabs should be open:
            - data/numbers/2.txt (active)
            - data/numbers/3.txt

    Scenario: :tab-only with --left and --right
        When I run :tab-only --left --right
        Then the error "Only one of -l/-r can be given!" should be shown

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
        Then the error "Numeric argument is too large for internal int representation." should be shown

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
        When I run :tab-focus 2 with count 2
        Then the error "Both count and argument given!" should be shown

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

    Scenario: :tab-focus last with no last focused tab
        Given I have a fresh instance
        And I run :tab-focus last
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
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I run :tab-focus 1
        And I run :tab-move + with count 3
        Then the error "Can't move tab to position 4!" should be shown

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
        When I open data/hello.txt
        And I run :tab-clone -b
        Then the following tabs should be open:
            - data/hello.txt (active)
            - data/hello.txt

    Scenario: Cloning to new window
        Given I have a fresh instance
        When I open data/title.html
        And I run :tab-clone -w
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
        Given I have a fresh instance
        When I open data/title.html
        And I set tabs -> tabs-are-windows to true
        And I run :tab-clone
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
