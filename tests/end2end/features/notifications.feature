# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Notifications
    HTML5 notification API interaction

    Background:
        When I open data/javascript/notifications.html
        And I set content.notifications.enabled to true
        And I run :click-element id button

    Scenario: Notification is shown
        When I run :click-element id show-button
        Then the javascript message "notification shown" should be logged
        And a notification with id 1 should be presented

    Scenario: Notification containing escaped characters
        Given the notification server supports body markup
        When I run :click-element id show-symbols-button
        Then the javascript message "notification shown" should be logged
        And notification 1 should have body "&lt;&lt; &amp;&amp; &gt;&gt;"
        And notification 1 should have title "<< && >>"

    Scenario: Notification containing escaped characters with no body markup
        Given the notification server doesn't support body markup
        When I run :click-element id show-symbols-button
        Then the javascript message "notification shown" should be logged
        And notification 1 should have body "<< && >>"
        And notification 1 should have title "<< && >>"

    Scenario: Notification with RGB image
        When I run :click-element id show-image-button-noalpha
        Then the javascript message "notification shown" should be logged
        And notification 1 should have title "RGB"

    Scenario: Notification with RGBA image
        When I run :click-element id show-image-button
        Then the javascript message "notification shown" should be logged
        And notification 1 should have title "RGBA"

    # As a WORKAROUND for https://www.riverbankcomputing.com/pipermail/pyqt/2020-May/042918.html
    # and other issues, those can only run with PyQtWebEngine >= 5.15.0
    #
    # For these tests, we need to wait for the notification to be shown before
    # we try to close it, otherwise we wind up in race-condition-ish
    # situations.

    @pyqtwebengine>=5.15.0
    Scenario: Replacing existing notifications
        When I run :click-element id show-replacing-button
        Then the javascript message "i=1 notification shown" should be logged
        And the javascript message "i=2 notification shown" should be logged
        And the javascript message "i=3 notification shown" should be logged
        And 1 notification should be presented
        And notification 1 should have title "i=3"

    @pyqtwebengine<5.15.0
    Scenario: Replacing existing notifications (old Qt)
        When I run :click-element id show-replacing-button
        Then the javascript message "i=1 notification shown" should be logged
        And "Ignoring notification tag 'counter' due to PyQt bug" should be logged
        And the javascript message "i=2 notification shown" should be logged
        And "Ignoring notification tag 'counter' due to PyQt bug" should be logged
        And the javascript message "i=3 notification shown" should be logged
        And "Ignoring notification tag 'counter' due to PyQt bug" should be logged
        And 3 notifications should be presented
        And notification 1 should have title "i=1"
        And notification 2 should have title "i=2"
        And notification 3 should have title "i=3"

    @pyqtwebengine>=5.15.0
    Scenario: User closes presented notification
        When I run :click-element id show-button
        And I wait for the javascript message "notification shown"
        And I close the notification with id 1
        Then the javascript message "notification closed" should be logged

    @pyqtwebengine<5.15.0
    Scenario: User closes presented notification (old Qt)
        When I run :click-element id show-button
        And I wait for the javascript message "notification shown"
        And I close the notification with id 1
        Then "Ignoring close request for notification 1 due to PyQt bug" should be logged
        And the javascript message "notification closed" should not be logged
        And no crash should happen

    @pyqtwebengine>=5.15.0
    Scenario: User closes some other application's notification
        When I run :click-element id show-button
        And I wait for the javascript message "notification shown"
        And I close the notification with id 1234
        Then the javascript message "notification closed" should not be logged

    @pyqtwebengine>=5.15.0
    Scenario: User clicks presented notification
        When I run :click-element id show-button
        And I wait for the javascript message "notification shown"
        And I click the notification with id 1
        Then the javascript message "notification clicked" should be logged

    @pyqtwebengine<5.15.0
    Scenario: User clicks presented notification (old Qt)
        When I run :click-element id show-button
        And I wait for the javascript message "notification shown"
        And I click the notification with id 1
        Then "Ignoring click request for notification 1 due to PyQt bug" should be logged
        Then the javascript message "notification clicked" should not be logged
        And no crash should happen

    @pyqtwebengine>=5.15.0
    Scenario: User clicks some other application's notification
        When I run :click-element id show-button
        And I wait for the javascript message "notification shown"
        And I click the notification with id 1234
        Then the javascript message "notification clicked" should not be logged

    @pyqtwebengine>=5.15.0
    Scenario: Unknown action with some other application's notification
        When I run :click-element id show-button
        And I wait for the javascript message "notification shown"
        And I trigger a custom action on the notification with id 1234
        Then no crash should happen
