# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2020-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

import pytest
import pytest_bdd as bdd
bdd.scenarios('notifications.feature')


pytestmark = pytest.mark.usefixtures('notification_server')


@bdd.given("the notification server supports body markup")
def supports_body_markup(notification_server, quteproc):
    notification_server.supports_body_markup = True
    quteproc.send_cmd(
        ":debug-pyeval -q __import__('qutebrowser').browser.webengine.notification."
        "dbus_presenter._fetch_capabilities()")
    quteproc.wait_for(
        message="Notification server capabilities: ['actions', 'body-markup']")


@bdd.given("the notification server doesn't support body markup")
def doesnt_support_body_markup(notification_server, quteproc):
    notification_server.supports_body_markup = False
    quteproc.send_cmd(
        ":debug-pyeval -q __import__('qutebrowser').browser.webengine.notification."
        "dbus_presenter._fetch_capabilities()")
    quteproc.wait_for(message="Notification server capabilities: ['actions']")


@bdd.then(bdd.parsers.cfparse('a notification with id {id_:d} should be presented'))
def notification_presented(notification_server, id_):
    assert id_ in notification_server.messages


@bdd.then('1 notification should be presented')
def notification_presented_single(notification_server):
    assert len(notification_server.messages) == 1


@bdd.then(bdd.parsers.cfparse('{count:d} notifications should be presented'))
def notification_presented_count(notification_server, count):
    assert len(notification_server.messages) == count


@bdd.then(bdd.parsers.cfparse('notification {id_:d} should have body "{body}"'))
def notification_body(notification_server, id_, body):
    assert notification_server.messages[id_].body == body


@bdd.then(bdd.parsers.cfparse('notification {id_:d} should have title "{title}"'))
def notification_title(notification_server, id_, title):
    assert notification_server.messages[id_].title == title


@bdd.when(bdd.parsers.cfparse('I close the notification with id {id_:d}'))
def close_notification(notification_server, id_):
    notification_server.close(id_)


@bdd.when(bdd.parsers.cfparse('I click the notification with id {id_:d}'))
def click_notification(notification_server, id_):
    notification_server.click(id_)


@bdd.when(bdd.parsers.cfparse(
    'I trigger a {name} action on the notification with id {id_:d}'))
def custom_notification_action(notification_server, id_, name):
    notification_server.action(id_, name)
