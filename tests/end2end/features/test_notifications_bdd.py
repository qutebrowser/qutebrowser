# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

import pytest_bdd as bdd
bdd.scenarios('notifications.feature')


@bdd.given("the notification server supports body markup")
def supports_body_markup(notification_server):
    notification_server.supports_body_markup = True


@bdd.given("the notification server doesn't support body markup")
def doesnt_support_body_markup(notification_server):
    notification_server.supports_body_markup = False


@bdd.then(bdd.parsers.cfparse('a notification with id {id_:d} is presented'))
def notification_presented(notification_server, id_):
    assert id_ in notification_server.messages


@bdd.then(bdd.parsers.cfparse('notification {id_:d} has body "{body}"'))
def notification_body(notification_server, id_, body):
    assert notification_server.messages[id_]["body"] == body


@bdd.then(bdd.parsers.cfparse('notification {id_:d} has title "{title}"'))
def notification_title(notification_server, id_, title):
    assert notification_server.messages[id_]["title"] == title


@bdd.when(bdd.parsers.cfparse('I close the notification with id {id_:d}'))
def close_notification(notification_server, id_):
    notification_server.close(id_)
