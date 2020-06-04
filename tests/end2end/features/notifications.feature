# vim: ft=cucumber fileencoding=utf-8 sts=4 sw=4 et:

Feature: Notifications
    HTML5 notification API interaction

    Background:
        Given I open data/prompt/notifications.html
        And I set content.notifications to true
        And I run :click-element id button

    @qtwebengine_notifications
    Scenario: Notification is shown
        When I run :click-element id show-button
        Then the javascript message "notification shown" should be logged
        And a notification with id 1 is presented

