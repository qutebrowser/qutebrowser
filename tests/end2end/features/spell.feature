# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Setting spell checking for QtWebEngine

    Background:
        Given spell check languages are []

    @qtwebkit_skip @qt>=5.8
    Scenario: Turn spell check on
        Given spell check is off
        When I run :set ui spell true
        Then ui -> spell should be true
        Then spell check is on

    @qtwebkit_skip @qt>=5.8
    Scenario: Turn spell check off
        Given spell check is on
        When I run :set ui spell false
        Then ui -> spell should be false
        Then spell check is off

    @qtwebkit_skip @qt>=5.8
    Scenario: Set an invalid language
        When I run :set ui spell-languages invalid-language (invalid command)
        Then the error "set: Invalid value 'invalid-language' *" should be shown
        Then actual spell check languages are []

    @qtwebkit_skip @qt>=5.8
    Scenario: Set valid but not installed language
        When I run :set ui spell-languages af-ZA
        Then the warning "Language af-ZA is not installed." should be shown
        Then actual spell check languages are []

    @qtwebkit_skip @qt>=5.8
    Scenario: Set valid and installed language
        When I run :set ui spell-languages en-US
        Then ui -> spell-languages should be en-US
        Then actual spell check languages are ['en-US-7-1']
