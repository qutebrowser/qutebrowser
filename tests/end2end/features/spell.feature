# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Setting spell checking for QtWebEngine

    Background:
        Given spell check languages are []

    @qtwebkit_skip @qt>=5.8
    Scenario: Turn spell check on
        Given spell check is off
        When I run :set spell true
        Then the option spell should be set to true
        Then spell check is on

    @qtwebkit_skip @qt>=5.8
    Scenario: Turn spell check off
        Given spell check is on
        When I run :set spell false
        Then the option spell should be set to false
        Then spell check is off

    @qtwebkit_skip @qt>=5.8
    Scenario: Set an invalid language
        When I run :set spell_languages ['invalid-language'] (invalid command)
        Then the error "set: Invalid value 'invalid-language' *" should be shown
        Then actual spell check languages are []

    @qtwebkit_skip @qt>=5.8 @cannot_have_dict=af-ZA
    Scenario: Set valid but not installed language
        When I run :set spell_languages ['af-ZA']
        Then the warning "Language af-ZA is not installed." should be shown
        Then actual spell check languages are []

    @qtwebkit_skip @qt>=5.8 @must_have_dict=en-US
    Scenario: Set valid and installed language
        When I run :set spell_languages ["en-US"]
        Then the option spell_languages should be set to ["en-US"]
        Then actual spell check languages are ['en-US-7-1']
