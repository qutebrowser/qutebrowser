# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import re

import pytest_bdd as bdd
bdd.scenarios('qutescheme.feature')


@bdd.then(bdd.parsers.parse("the {kind} request should be blocked"))
def request_blocked(request, quteproc, kind):
    blocking_set_msg = (
        "Blocking malicious request from qute://settings/set?* to "
        "qute://settings/set?*")
    blocking_csrf_msg = (
        "Blocking malicious request from "
        "http://localhost:*/data/misc/qutescheme_csrf.html to "
        "qute://settings/set?*")
    webkit_error_invalid = (
        "Error while loading qute://settings/set?*: Invalid qute://settings "
        "request")
    webkit_error_unsupported = (
        "Error while loading qute://settings/set?*: Unsupported request type")

    if request.config.webengine:
        expected_messages = {
            'img': [blocking_csrf_msg],
            'link': [blocking_set_msg],
            'redirect': [blocking_set_msg],
            'form': [blocking_set_msg],
        }
    else:  # QtWebKit
        expected_messages = {
            'img': [blocking_csrf_msg],
            'link': [blocking_csrf_msg, webkit_error_invalid],
            'redirect': [blocking_csrf_msg, webkit_error_invalid],
            'form': [webkit_error_unsupported],
        }

    for pattern in expected_messages[kind]:
        msg = quteproc.wait_for(message=pattern)
        msg.expected = True
