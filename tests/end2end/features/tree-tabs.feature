# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Tree tabs
    Tests for tree-tabs consistency and commands

    Background:
        Given I clean up open tabs
        And I initialize tree-tabs

    Scenario: Open a unrelated tab with new_position_unrelated = last
        Given I set tabs.new_position.unrelated to last
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I open data/numbers/4.txt in a new tab
        Then the following tree should be shown:
            - data/numbers/1.txt
            - data/numbers/2.txt
            - data/numbers/3.txt
            - data/numbers/4.txt

    Scenario: Open a unrelated tab with new_position_unrelated = first
        Given I set tabs.new_position.unrelated to first
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I open data/numbers/4.txt in a new tab
        Then the following tree should be shown:
            - data/numbers/4.txt
            - data/numbers/3.txt
            - data/numbers/2.txt
            - data/numbers/1.txt

    Scenario: Open a unrelated tab with new_position_unrelated = next
        Given I set tabs.new_position.unrelated to next
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I open data/numbers/4.txt in a new tab
        And I open data/numbers/5.txt in a new tab
        And I run :tab-focus 3
        And I open data/numbers/6.txt in a new tab
        And I open data/numbers/7.txt in a new tab
        Then the following tree should be shown:
            - data/numbers/1.txt
            - data/numbers/2.txt
            - data/numbers/3.txt
            - data/numbers/6.txt
            - data/numbers/7.txt
            - data/numbers/4.txt
            - data/numbers/5.txt

    Scenario: Open a unrelated tab with new_position_unrelated = prev
        Given I set tabs.new_position.unrelated to prev
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new tab
        And I open data/numbers/3.txt in a new tab
        And I open data/numbers/4.txt in a new tab
        And I open data/numbers/5.txt in a new tab
        And I run :tab-focus 3
        And I open data/numbers/6.txt in a new tab
        And I open data/numbers/7.txt in a new tab
        Then the following tree should be shown:
            - data/numbers/5.txt
            - data/numbers/4.txt
            - data/numbers/7.txt
            - data/numbers/6.txt
            - data/numbers/3.txt
            - data/numbers/2.txt
            - data/numbers/1.txt

    Scenario: Open a related tab with new_position_related = last
        Given I set tabs.new_position.related to last
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related background tab
        And I open data/numbers/3.txt in a new related background tab
        And I open data/numbers/4.txt in a new related background tab
        And I open data/numbers/5.txt in a new related background tab
        And I run :tab-focus 3
        And I open data/numbers/6.txt in a new related background tab
        And I open data/numbers/7.txt in a new related background tab
        And I open data/numbers/8.txt in a new related background tab
        Then the following tree should be shown:
            - data/numbers/1.txt
                - data/numbers/2.txt
                - data/numbers/3.txt
                    - data/numbers/6.txt
                    - data/numbers/7.txt
                    - data/numbers/8.txt
                - data/numbers/4.txt
                - data/numbers/5.txt

    @xfail
    Scenario: Open a related tab with new_position_related = first
        # Not implemented yet
        Given I set tabs.new_position.related to first
        When I open data/numbers/1.txt
        And I open data/numbers/2.txt in a new related background tab
        And I open data/numbers/3.txt in a new related background tab
        And I open data/numbers/4.txt in a new related background tab
        And I open data/numbers/5.txt in a new related background tab
        And I run :tab-focus 3
        And I open data/numbers/6.txt in a new related background tab
        And I open data/numbers/7.txt in a new related background tab
        And I open data/numbers/8.txt in a new related background tab
        Then the following tree should be shown:
            - data/numbers/1.txt
                - data/numbers/5.txt
                - data/numbers/4.txt
                    - data/numbers/8.txt
                    - data/numbers/7.txt
                    - data/numbers/6.txt
                - data/numbers/3.txt
                - data/numbers/2.txt

    @skip
    Scenario: Open a related tab with new_position_related = next
        Given I set tabs.new_position.related to next
        # This should work like last

    @skip
    Scenario: Open a related tab with new_position_related = prev
        Given I set tabs.new_position.related to prev
        # This should work like first

    Scenario: qute://treegroup
        When I open qute://treegroup/A
        And I open qute://treegroup/B in a new tab
        And I open qute://treegroup/C in a new tab
        Then the page should contain the plaintext "Group for tree tabs"
        And the following tree should be shown:
            - qute://treegroup/A
            - qute://treegroup/B
            - qute://treegroup/C

    Scenario: :tree-tab-create-group
        When I run :tree-tab-create-group A
        And I run :tree-tab-create-group B
        Then the page should contain the plaintext "Group for tree tabs"
        And the following tree should be shown:
            - about:blank
            - qute://treegroup/A
            - qute://treegroup/B

    Scenario: :tab-close-tree
        When I open qute://treegroup/A
        And I open qute://treegroup/B in a new tab
        And I open qute://treegroup/C in a new tab
        And I run :tab-close
        Then the following tree should be shown:
            - qute://treegroup/A
            - qute://treegroup/B
    
    Scenario: Create complex tree
        When I open qute://treegroup/A
        And I run :open -t -r qute://treegroup/B
        And I run :open -t -r qute://treegroup/C
        And I run :open -t -r qute://treegroup/D
        And I run :tab-focus 1
        And I run :open -t -r qute://treegroup/E
        And I run :tab-focus 5
        And I run :open -t -r qute://treegroup/F
        And I run :tab-focus 5
        And I run :open -t -r qute://treegroup/G
        And I run :open -t -r qute://treegroup/H
        And I run :open -t -r qute://treegroup/I
        And I run :open -t -r qute://treegroup/J
        And I run :tab-focus 7
        And I run :open -t -r qute://treegroup/L
        And I run :tab-focus 7
        And I run :open -t -r qute://treegroup/M
        And I run :open -t -r qute://treegroup/N
        Then the following tree should be shown:
            - qute://treegroup/A
                - qute://treegroup/B
                    - qute://treegroup/C
                        - qute://treegroup/D
                - qute://treegroup/E
                    - qute://treegroup/F
                    - qute://treegroup/G
                        - qute://treegroup/H
                            - qute://treegroup/I
                                - qute://treegroup/J
                        - qute://treegroup/L
                        - qute://treegroup/M
                            - qute://treegroup/N

    Scenario: Delete from complex tree
        When I open qute://treegroup/A
        And I run :open -t -r qute://treegroup/B
        And I run :open -t -r qute://treegroup/C
        And I run :open -t -r qute://treegroup/D
        And I run :tab-focus 1
        And I run :open -t -r qute://treegroup/E
        And I run :tab-focus 5
        And I run :open -t -r qute://treegroup/F
        And I run :tab-focus 5
        And I run :open -t -r qute://treegroup/G
        And I run :open -t -r qute://treegroup/H
        And I run :open -t -r qute://treegroup/I
        And I run :open -t -r qute://treegroup/J
        And I run :tab-focus 7
        And I run :open -t -r qute://treegroup/L
        And I run :tab-focus 7
        And I run :open -t -r qute://treegroup/M
        And I run :open -t -r qute://treegroup/N
        And I run :tab-focus 7
        And I run :tab-close
        Then the following tree should be shown:
            - qute://treegroup/A
                - qute://treegroup/B
                    - qute://treegroup/C
                        - qute://treegroup/D
                - qute://treegroup/E
                    - qute://treegroup/F
                    - qute://treegroup/H
                        - qute://treegroup/I
                            - qute://treegroup/J
                        - qute://treegroup/L
                        - qute://treegroup/M
                            - qute://treegroup/N

    Scenario: Recursively delete from complex tree
        When I open qute://treegroup/A
        And I run :open -t -r qute://treegroup/B
        And I run :open -t -r qute://treegroup/C
        And I run :open -t -r qute://treegroup/D
        And I run :tab-focus 1
        And I run :open -t -r qute://treegroup/E
        And I run :tab-focus 5
        And I run :open -t -r qute://treegroup/F
        And I run :tab-focus 5
        And I run :open -t -r qute://treegroup/G
        And I run :open -t -r qute://treegroup/H
        And I run :open -t -r qute://treegroup/I
        And I run :open -t -r qute://treegroup/J
        And I run :tab-focus 7
        And I run :open -t -r qute://treegroup/L
        And I run :tab-focus 7
        And I run :open -t -r qute://treegroup/M
        And I run :open -t -r qute://treegroup/N
        And I run :tab-focus 7
        And I run :tab-close -r
        Then the following tree should be shown:
            - qute://treegroup/A
                - qute://treegroup/B
                    - qute://treegroup/C
                        - qute://treegroup/D
                - qute://treegroup/E
                    - qute://treegroup/F

    Scenario: Undo
        When I open qute://treegroup/A
        And I run :open -t -r qute://treegroup/B
        And I run :open -t -r qute://treegroup/C
        And I run :open -t -r qute://treegroup/D
        And I run :tab-focus 1
        And I run :open -t -r qute://treegroup/E
        And I run :tab-focus 5
        And I run :open -t -r qute://treegroup/F
        And I run :tab-focus 5
        And I run :open -t -r qute://treegroup/G
        And I run :open -t -r qute://treegroup/H
        And I run :open -t -r qute://treegroup/I
        And I run :open -t -r qute://treegroup/J
        And I run :tab-focus 7
        And I run :open -t -r qute://treegroup/L
        And I run :tab-focus 7
        And I run :open -t -r qute://treegroup/M
        And I run :open -t -r qute://treegroup/N
        And I run :tab-focus 7
        And I run :tab-close
        And I run :open -t qute://treegroup/O
        And I run :undo
        Then the following tree should be shown:
            - qute://treegroup/A
                - qute://treegroup/B
                    - qute://treegroup/C
                        - qute://treegroup/D
                - qute://treegroup/E
                    - qute://treegroup/F
                    - qute://treegroup/G
                        - qute://treegroup/H
                            - qute://treegroup/I
                                - qute://treegroup/J
                        - qute://treegroup/L
                        - qute://treegroup/M
                            - qute://treegroup/N
            - qute://treegroup/O

    Scenario: Undo a recursive tree
        When I open qute://treegroup/A
        And I run :open -t -r qute://treegroup/B
        And I run :open -t -r qute://treegroup/C
        And I run :open -t -r qute://treegroup/D
        And I run :tab-focus 1
        And I run :open -t -r qute://treegroup/E
        And I run :tab-focus 5
        And I run :open -t -r qute://treegroup/F
        And I run :tab-focus 5
        And I run :open -t -r qute://treegroup/G
        And I run :open -t -r qute://treegroup/H
        And I run :open -t -r qute://treegroup/I
        And I run :open -t -r qute://treegroup/J
        And I run :tab-focus 7
        And I run :open -t -r qute://treegroup/L
        And I run :tab-focus 7
        And I run :open -t -r qute://treegroup/M
        And I run :open -t -r qute://treegroup/N
        And I run :tab-focus 7
        And I run :tab-close -r
        And I run :open -t qute://treegroup/O
        And I run :undo
        Then the following tree should be shown:
            - qute://treegroup/A
                - qute://treegroup/B
                    - qute://treegroup/C
                        - qute://treegroup/D
                - qute://treegroup/E
                    - qute://treegroup/F
                    - qute://treegroup/G
                        - qute://treegroup/H
                            - qute://treegroup/I
                                - qute://treegroup/J
                        - qute://treegroup/L
                        - qute://treegroup/M
                            - qute://treegroup/N
            - qute://treegroup/O

    Scenario: tab-promote
        Given I set tabs.new_position.related to last
        When I open qute://treegroup/A
        And I run :open -t -r qute://treegroup/B
        And I run :open -t -r qute://treegroup/C
        And I run :open -t -r qute://treegroup/D
        And I run :tab-focus -n 1
        And I run :open -t -r qute://treegroup/E
        And I run :tab-focus -n 5
        And I run :open -t -r qute://treegroup/F
        And I run :tab-focus -n 5
        And I run :open -t -r qute://treegroup/G
        And I run :open -t -r qute://treegroup/H
        And I run :open -t -r qute://treegroup/I
        And I run :open -t -r qute://treegroup/J
        And I run :tab-focus -n 7
        And I run :open -t -r qute://treegroup/L
        And I run :tab-focus -n 7
        And I run :open -t -r qute://treegroup/M
        And I run :open -t -r qute://treegroup/N
        And I run :tab-focus -n 7
        # And I run :tree-tab-promote
        Then the following tree should be shown:
            - qute://treegroup/A
                - qute://treegroup/B
                    - qute://treegroup/C
                        - qute://treegroup/D
                - qute://treegroup/E
                    - qute://treegroup/F
                    - qute://treegroup/G
                        - qute://treegroup/H
                            - qute://treegroup/I
                                - qute://treegroup/J
                        - qute://treegroup/L
                        - qute://treegroup/M
                            - qute://treegroup/N

    Scenario: tab-demote
        When I open qute://treegroup/A
        And I run :open -t -r qute://treegroup/B
        And I run :open -t -r qute://treegroup/C
        And I run :open -t -r qute://treegroup/D
        And I run :tab-focus -n 1
        And I run :open -t -r qute://treegroup/E
        And I run :tab-focus -n 5
        And I run :open -t -r qute://treegroup/F
        And I run :tab-focus -n 5
        And I run :open -t -r qute://treegroup/G
        And I run :open -t -r qute://treegroup/H
        And I run :open -t -r qute://treegroup/I
        And I run :open -t -r qute://treegroup/J
        And I run :tab-focus -n 7
        And I run :open -t -r qute://treegroup/L
        And I run :tab-focus -n 7
        And I run :open -t -r qute://treegroup/M
        And I run :open -t -r qute://treegroup/N
        And I run :tab-focus -n 11
        And I run :tree-tab-demote
        And I run :tab-focus -n 5
        And I run :tree-tab-demote
        Then the following tree should be shown:
            - qute://treegroup/A
                - qute://treegroup/B
                    - qute://treegroup/C
                        - qute://treegroup/D
                    - qute://treegroup/E
                        - qute://treegroup/F
                        - qute://treegroup/G
                            - qute://treegroup/H
                                - qute://treegroup/I
                                    - qute://treegroup/J
                                - qute://treegroup/L
                            - qute://treegroup/M
                                - qute://treegroup/N

    @skip
    Scenario: Collapse a tree

    @skip
    Scenario: Collapse an ancestor of a collapsed tree

    @skip
    Scenario: Un-collapse a tree

    @skip
    Scenario: Un-Collapse an ancestor of a collapsed tree

    @skip
    Scenario: Close a collapsed tree

    @skip
    Scenario: Recursively close a tree that contains a collapsed descendentant

    @skip
    Scenario: Undo closing a collapsed tree

    @skip
    Scenario: Undo closing a tree that contained a collapsed descentant

    @skip
    Scenario: :tab-move a leaf

    @skip
    Scenario: :tab-move a tree

    Scenario: :tab-move minus
        When I open qute://treegroup/A
        And I run :open -t -r qute://treegroup/B
        And I run :open -t -r qute://treegroup/C
        And I run :open -t -r qute://treegroup/D
        And I run :tab-focus 1
        And I run :open -t -r qute://treegroup/E
        And I run :tab-focus 5
        And I run :open -t -r qute://treegroup/F
        And I run :tab-focus 5
        And I run :open -t -r qute://treegroup/G
        And I run :open -t -r qute://treegroup/H
        And I run :open -t -r qute://treegroup/I
        And I run :open -t -r qute://treegroup/J
        And I run :tab-focus 7
        And I run :open -t -r qute://treegroup/L
        And I run :tab-focus 7
        And I run :open -t -r qute://treegroup/M
        And I run :open -t -r qute://treegroup/N
        And I run :tab-focus 1
        And I run :open -b -r qute://treegroup/O
        And I run :open -b -r qute://treegroup/P
        And I run :tab-focus 5
        And I run :tab-move -
        And I run :tab-move -
        Then the following tree should be shown:
            - qute://treegroup/A
                - qute://treegroup/B
                    - qute://treegroup/C
                        - qute://treegroup/D
                - qute://treegroup/O
                - qute://treegroup/P
                - qute://treegroup/E
                    - qute://treegroup/F
                    - qute://treegroup/G
                        - qute://treegroup/H
                            - qute://treegroup/I
                                - qute://treegroup/J
                        - qute://treegroup/L
                        - qute://treegroup/M
                            - qute://treegroup/N

    Scenario: :tab-move plus
        When I open qute://treegroup/A
        And I run :open -t -r qute://treegroup/B
        And I run :open -t -r qute://treegroup/C
        And I run :open -t -r qute://treegroup/D
        And I run :tab-focus 1
        And I run :open -t -r qute://treegroup/E
        And I run :tab-focus 5
        And I run :open -t -r qute://treegroup/F
        And I run :tab-focus 5
        And I run :open -t -r qute://treegroup/G
        And I run :open -t -r qute://treegroup/H
        And I run :open -t -r qute://treegroup/I
        And I run :open -t -r qute://treegroup/J
        And I run :tab-focus 7
        And I run :open -t -r qute://treegroup/L
        And I run :tab-focus 7
        And I run :open -t -r qute://treegroup/M
        And I run :open -t -r qute://treegroup/N
        And I run :tab-focus 1
        And I run :open -b -r qute://treegroup/O
        And I run :open -b -r qute://treegroup/P
        And I run :tab-focus 5
        And I run :tab-move +
        And I run :tab-move +
        And I run :tab-move +
        Then the following tree should be shown:
            - qute://treegroup/A
                - qute://treegroup/E
                    - qute://treegroup/F
                    - qute://treegroup/G
                        - qute://treegroup/H
                            - qute://treegroup/I
                                - qute://treegroup/J
                        - qute://treegroup/L
                        - qute://treegroup/M
                            - qute://treegroup/N
                - qute://treegroup/B
                    - qute://treegroup/C
                        - qute://treegroup/D
                - qute://treegroup/O
                - qute://treegroup/P

    @skip
    Scenario: :tree-tab-navigate-on-same-level

    @skip
    Scenario: :tree-tab-navigate-on-same-level 2

    @skip
    Scenario: Save and restore a session

    @skip
    Scenario: Save and restore a session with collapsed trees

    @skip
    Scenario: :tree-tab-cycle-hide once

    @skip
    Scenario: :tree-tab-cycle-hide three times

    @skip
    Scenario: :tree-tab-cycle-hide three times with collapsed descendants

    @skip
    Scenario: :tree-tab-cycle-hide enough times it resets
