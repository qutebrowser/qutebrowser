# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Setting spell checking for QtWebEngine

    @qtwebkit_skip @qt>=5.8
    Scenario: Turn spell check on
        Given I set spellcheck.enabled to false
        When I run :set spellcheck.enabled true
        Then the option spellcheck.enabled should be set to true

    @qtwebkit_skip @qt>=5.8
    Scenario: Turn spell check off
        Given I set spellcheck.enabled to true
        When I run :set spellcheck.enabled false
        Then the option spellcheck.enabled should be set to false

    @qtwebkit_skip @qt>=5.8
    Scenario: Set an invalid language
        When I run :set spellcheck.languages ['invalid-language'] (invalid command)
        Then the error "set: Invalid value 'invalid-language' *" should be shown

    @qtwebkit_skip @qt>=5.8 @cannot_have_dict=af-ZA
    Scenario: Set valid but not installed language
        When I run :set spellcheck.languages ['af-ZA']
        Then the warning "Language af-ZA is not installed." should be shown

    @qtwebkit_skip @qt>=5.8 @must_have_dict=en-US
    Scenario: Set valid and installed language
        When I run :set spellcheck.languages ["en-US"]
        Then the option spellcheck.languages should be set to ["en-US"]
