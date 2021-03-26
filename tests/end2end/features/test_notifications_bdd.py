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

from qutebrowser.utils import qtutils


bdd.scenarios('notifications.feature')


pytestmark = [
    pytest.mark.usefixtures('notification_server'),
    pytest.mark.qtwebengine_notifications,
    pytest.mark.skipif(
        not qtutils.version_check('5.14'),
        reason="Custom notification presenters segfault with Qt/PyQtWebEngine 5.13",
    ),
]


@bdd.given("the notification server supports body markup")
def supports_body_markup(notification_server, quteproc):
    notification_server.supports_body_markup = True
    quteproc.send_cmd(
        ":debug-pyeval -q __import__('qutebrowser').browser.webengine.notification."
        "bridge._drop_adapter()")


@bdd.given("the notification server doesn't support body markup")
def doesnt_support_body_markup(notification_server, quteproc):
    notification_server.supports_body_markup = False
    quteproc.send_cmd(
        ":debug-pyeval -q __import__('qutebrowser').browser.webengine.notification."
        "bridge._drop_adapter()")


@bdd.given('I clean up the notification server')
def cleanup_notification_server(notification_server):
    notification_server.cleanup()


@bdd.then('1 notification should be presented')
def notification_presented_single(notification_server):
    assert len(notification_server.messages) == 1


@bdd.then(bdd.parsers.cfparse('{count:d} notifications should be presented'))
def notification_presented_count(notification_server, count):
    assert len(notification_server.messages) == count


@bdd.then(bdd.parsers.parse('the notification should have body "{body}"'))
def notification_body(notification_server, body):
    msg = notification_server.last_msg()
    assert msg.body == body


@bdd.then(bdd.parsers.parse('the notification should have title "{title}"'))
def notification_title(notification_server, title):
    msg = notification_server.last_msg()
    assert msg.title == title


@bdd.then(bdd.parsers.cfparse(
    'the notification should have image dimensions {width:d}x{height:d}'))
def notification_image_dimensions(notification_server, width, height):
    msg = notification_server.last_msg()
    assert (msg.img_width, msg.img_height) == (width, height)


@bdd.then('the notification should be closed via web')
def notification_closed(notification_server):
    if not qtutils.version_check('5.15'):
        # Signal connection gets lost on Qt 5.14 as the notification gets destroyed
        pytest.skip("Broken with Qt 5.14")
    msg = notification_server.last_msg()
    assert msg.closed_via_web


@bdd.when('I close the notification')
def close_notification(notification_server):
    notification_server.close(notification_server.last_id)


@bdd.when(bdd.parsers.cfparse('I close the notification with id {id_:d}'))
def close_notification_id(notification_server, id_):
    notification_server.close(id_)


@bdd.when('I click the notification')
def click_notification(notification_server):
    notification_server.click(notification_server.last_id)


@bdd.when(bdd.parsers.cfparse('I click the notification with id {id_:d}'))
def click_notification_id(notification_server, id_):
    notification_server.click(id_)


@bdd.when(bdd.parsers.cfparse(
    'I trigger a {name} action on the notification with id {id_:d}'))
def custom_notification_action(notification_server, id_, name):
    notification_server.action(id_, name)
