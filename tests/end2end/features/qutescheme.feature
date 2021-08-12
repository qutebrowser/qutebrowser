# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Special qute:// pages

    Background:
        Given I open about:blank

    # :help

    Scenario: :help without topic
        When the documentation is up to date
        And I run :tab-only
        And I run :help
        And I wait until qute://help/index.html is loaded
        Then the following tabs should be open:
            - qute://help/index.html (active)

    Scenario: :help with invalid topic
        When I run :help foo
        Then the error "Invalid help topic foo!" should be shown

    Scenario: :help with command
        When the documentation is up to date
        And I run :tab-only
        And I run :help :back
        And I wait until qute://help/commands.html#back is loaded
        Then the following tabs should be open:
            - qute://help/commands.html#back (active)

    Scenario: :help with invalid command
        When I run :help :foo
        Then the error "Invalid command foo!" should be shown

    Scenario: :help with setting
        When the documentation is up to date
        And I run :tab-only
        And I run :help editor.command
        And I wait until qute://help/settings.html#editor.command is loaded
        Then the following tabs should be open:
            - qute://help/settings.html#editor.command (active)

    Scenario: :help with -t
        When the documentation is up to date
        And I run :tab-only
        And I run :help -t
        And I wait until qute://help/index.html is loaded
        Then the following tabs should be open:
            - about:blank
            - qute://help/index.html (active)

    # https://github.com/qutebrowser/qutebrowser/issues/2513
    Scenario: Opening link with qute:help
        When the documentation is up to date
        And I run :tab-only
        And I open qute:help without waiting
        And I wait for "Changing title for idx 0 to 'qutebrowser help'" in the log
        And I hint with args "links normal" and follow ls
        Then qute://help/quickstart.html should be loaded

    Scenario: Opening a link with qute://help
        When the documentation is up to date
        And I run :tab-only
        And I open qute://help without waiting
        And I wait until qute://help/ is loaded
        And I hint with args "links normal" and follow ls
        Then qute://help/quickstart.html should be loaded

    Scenario: Opening a link with qute://help/index.html/..
        When the documentation is up to date
        And I open qute://help/index.html/.. without waiting
        Then qute://help/ should be loaded

    Scenario: Opening a link with qute://help/index.html/../
        When the documentation is up to date
        And I open qute://help/index.html/../ without waiting
        Then qute://help/ should be loaded

    @qtwebengine_skip
    Scenario: Opening a link with qute://help/img/ (QtWebKit)
        When the documentation is up to date
        And I open qute://help/img/ without waiting
        Then "*Error while * qute://*" should be logged
        And "*Is a directory*" should be logged
        And "* url='qute://help/img'* LoadStatus.error" should be logged

    @qtwebkit_skip
    Scenario: Opening a link with qute://help/img/ (QtWebEngine)
        When the documentation is up to date
        And I open qute://help/img/ without waiting
        Then "*Error while * qute://*" should be logged
        And "* url='qute://help/img'* LoadStatus.error" should be logged
        And "Load error: ERR_FILE_NOT_FOUND" should be logged

    # :history

    Scenario: :history without arguments
        When I run :tab-only
        And I run :history
        And I wait until qute://history/ is loaded
        Then the following tabs should be open:
            - qute://history/ (active)

    Scenario: :history with -t
        When I run :tab-only
        And I run :history -t
        And I wait until qute://history/ is loaded
        Then the following tabs should be open:
            - about:blank
            - qute://history/ (active)

    # qute://settings

    # Sometimes, an unrelated value gets set, which also breaks other tests
    @skip
    Scenario: Focusing input fields in qute://settings and entering valid value
        When I set search.ignore_case to never
        And I open qute://settings
        # scroll to the right - the table does not fit in the default screen
        And I run :scroll-to-perc -x 100
        And I run :jseval document.getElementById('input-search.ignore_case').value = ''
        And I run :click-element id input-search.ignore_case
        And I wait for "Entering mode KeyMode.insert *" in the log
        And I press the keys "always"
        And I press the key "<Escape>"
        # an explicit Tab to unfocus the input field seems to stabilize the tests
        And I press the key "<Tab>"
        And I wait for "Config option changed: search.ignore_case *" in the log
        Then the option search.ignore_case should be set to always

    # Sometimes, an unrelated value gets set
    # Too flaky...
    @skip
    Scenario: Focusing input fields in qute://settings and entering invalid value
        When I open qute://settings
        # scroll to the right - the table does not fit in the default screen
        And I run :scroll-to-perc -x 100
        And I run :jseval document.getElementById('input-search.ignore_case').value = ''
        And I run :click-element id input-search.ignore_case
        And I wait for "Entering mode KeyMode.insert *" in the log
        And I press the keys "foo"
        And I press the key "<Escape>"
        # an explicit Tab to unfocus the input field seems to stabilize the tests
        And I press the key "<Tab>"
        Then "Invalid value 'foo' *" should be logged

    Scenario: qute://settings CSRF via img
        When I open data/misc/qutescheme_csrf.html
        And I run :click-element id via-img
        Then the img request should be blocked

    Scenario: qute://settings CSRF via link
        When I open data/misc/qutescheme_csrf.html
        And I run :click-element id via-link
        Then the link request should be blocked

    Scenario: qute://settings CSRF via redirect
        When I open data/misc/qutescheme_csrf.html
        And I run :click-element id via-redirect
        Then the redirect request should be blocked

    Scenario: qute://settings CSRF via form
        When I open data/misc/qutescheme_csrf.html
        And I run :click-element id via-form
        Then the form request should be blocked

    @qtwebkit_skip
    Scenario: qute://settings CSRF token (webengine)
        When I open qute://settings
        And I run :jseval const xhr = new XMLHttpRequest(); xhr.open("GET", "qute://settings/set"); xhr.send()
        Then "RequestDeniedError while handling qute://* URL: Invalid CSRF token!" should be logged
        And the error "Invalid CSRF token for qute://settings!" should be shown

    # pdfjs support

    Scenario: pdfjs is used for pdf files
        Given pdfjs is available
        When I set content.pdfjs to true
        And I open data/misc/test.pdf without waiting
        Then the javascript message "PDF * [*] (PDF.js: *)" should be logged

    @qtwebkit_pdf_imageformat_skip
    Scenario: pdfjs is not used when disabled
        When I set content.pdfjs to false
        And I set downloads.location.prompt to false
        And I open data/misc/test.pdf without waiting
        Then "Download test.pdf finished" should be logged

    Scenario: Downloading a pdf via pdf.js button (issue 1214)
        Given pdfjs is available
        When I set content.pdfjs to true
        And I set downloads.location.prompt to true
        And I open data/misc/test.pdf without waiting
        And I wait for "[qute://pdfjs/*] PDF * (PDF.js: *)" in the log
        And I run :jseval document.getElementById("download").click()
        And I wait for "Asking question <qutebrowser.utils.usertypes.Question default=* mode=<PromptMode.download: 5> option=None text=* title='Save file to:'>, *" in the log
        And I run :mode-leave
        Then no crash should happen

    # :pyeval

    Scenario: Running :pyeval
        When I run :debug-pyeval 1+1
        And I wait until qute://pyeval/ is loaded
        Then the page should contain the plaintext "2"

    Scenario: Causing exception in :pyeval
        When I run :debug-pyeval 1/0
        And I wait until qute://pyeval/ is loaded
        Then the page should contain the plaintext "ZeroDivisionError"

    Scenario: Running :pyveal with --file using a file that exists as python code
        When I run :debug-pyeval --file (testdata)/misc/pyeval_file.py
        Then the message "Hello World" should be shown
        And "pyeval output: No error" should be logged

    Scenario: Running :pyeval --file using a non existing file
        When I run :debug-pyeval --file nonexistentfile
        Then the error "[Errno 2] *: 'nonexistentfile'" should be shown

    Scenario: Running :pyeval with --quiet
        When I run :debug-pyeval --quiet 1+1
        Then "pyeval output: 2" should be logged

    ## :messages

    Scenario: :messages without level
        When I run :message-error the-error-message
        And I run :message-warning the-warning-message
        And I run :message-info the-info-message
        And I run :messages
        Then qute://log/?level=info should be loaded
        And the error "the-error-message" should be shown
        And the warning "the-warning-message" should be shown
        And the page should contain the plaintext "the-error-message"
        And the page should contain the plaintext "the-warning-message"
        And the page should contain the plaintext "the-info-message"

    Scenario: Showing messages of type 'warning' or greater
        When I run :message-error the-error-message
        And I run :message-warning the-warning-message
        And I run :message-info the-info-message
        And I run :messages warning
        Then qute://log/?level=warning should be loaded
        And the error "the-error-message" should be shown
        And the warning "the-warning-message" should be shown
        And the page should contain the plaintext "the-error-message"
        And the page should contain the plaintext "the-warning-message"
        And the page should not contain the plaintext "the-info-message"

    Scenario: Showing messages of type 'info' or greater
        When I run :message-error the-error-message
        And I run :message-warning the-warning-message
        And I run :message-info the-info-message
        And I run :messages info
        Then qute://log/?level=info should be loaded
        And the error "the-error-message" should be shown
        And the warning "the-warning-message" should be shown
        And the page should contain the plaintext "the-error-message"
        And the page should contain the plaintext "the-warning-message"
        And the page should contain the plaintext "the-info-message"

    Scenario: Showing messages of category 'message'
        When I run :message-info the-info-message
        And I run :messages -f message
        Then qute://log/?level=info&logfilter=message should be loaded
        And the page should contain the plaintext "the-info-message"

    Scenario: Showing messages of category 'misc'
        When I run :message-info the-info-message
        And I run :messages -f misc
        Then qute://log/?level=info&logfilter=misc should be loaded
        And the page should not contain the plaintext "the-info-message"

    @qtwebengine_flaky
    Scenario: Showing messages of an invalid level
        When I run :messages cataclysmic
        Then the error "Invalid log level cataclysmic!" should be shown

    Scenario: Showing messages with an invalid category
        When I run :messages -f invalid
        Then the error "Invalid log category invalid - *" should be shown

    Scenario: Using qute://log directly
        When I open qute://log without waiting
        And I wait for "Changing title for idx * to 'log'" in the log
        Then no crash should happen

    # FIXME More possible tests:
    # :message --plain
    # Using qute://log directly with invalid category
    # same with invalid level

    # :version

    Scenario: Open qute://version
        When I open qute://version
        Then the page should contain the plaintext "Version info"

    # qute://gpl

    Scenario: Open qute://gpl
        When I open qute://gpl
        Then the page should contain the plaintext "GNU GENERAL PUBLIC LICENSE"
