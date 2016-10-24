Feature: Miscellaneous utility commands exposed to the user.

    Background:
        Given I open data/scroll/simple.html
        And I run :tab-only

    ## :later

    Scenario: :later before
        When I run :later 500 scroll down
        Then the page should not be scrolled

    Scenario: :later after
        When I run :later 500 scroll down
        And I wait 0.6s
        Then the page should be scrolled vertically

    # for some reason, argparser gives us the error instead, see #2046
    @xfail
    Scenario: :later with negative delay
        When I run :later -1 scroll down
        Then the error "I can't run something in the past!" should be shown

    Scenario: :later with humongous delay
        When I run :later 36893488147419103232 scroll down
        Then the error "Numeric argument is too large for internal int representation." should be shown

    ## :repeat

    Scenario: :repeat simple
        When I run :repeat 5 scroll-px 10 0
        And I wait until the scroll position changed to 50/0
		# Then already covered by above And

    Scenario: :repeat zero times
        When I run :repeat 0 scroll-px 10 0
        And I wait 0.01s
        Then the page should not be scrolled

    # argparser again
    @xfail
    Scenario: :repeat negative times
        When I run :repeat -4 scroll-px 10 0
        Then the error "A negative count doesn't make sense." should be shown
        And the page should not be scrolled

    ## :debug-all-objects

    Scenario: :debug-all-objects
        When I run :debug-all-objects
        Then "*Qt widgets - *Qt objects - *" should be logged

	## :debug-cache-stats

	Scenario: :debug-cache-stats
		When I run :debug-cache-stats
		Then "config: CacheInfo(*)" should be logged
		And "style: CacheInfo(*)" should be logged

	## :debug-console

	# (!) the following two scenarios have a sequential dependency
	Scenario: opening the debug console
		When I run :debug-console
		Then "initializing debug console" should be logged
		And "showing debug console" should be logged

	Scenario: closing the debug console
		When I run :debug-console
		Then "hiding debug console" should be logged
