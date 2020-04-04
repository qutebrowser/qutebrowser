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

import json

import pytest_bdd as bdd

# pylint: disable=unused-import
from end2end.features.test_yankpaste_bdd import init_fake_clipboard
# pylint: enable=unused-import


@bdd.then(bdd.parsers.parse('"{text}" should be found'))
def check_found_text(request, quteproc, text):
    if request.config.webengine:
        # WORKAROUND
        # This probably should work with Qt 5.9:
        # https://codereview.qt-project.org/#/c/192920/
        # https://codereview.qt-project.org/#/c/192921/
        # https://bugreports.qt.io/browse/QTBUG-53134
        return
    quteproc.send_cmd(':yank selection')
    quteproc.wait_for(message='Setting fake clipboard: {}'.format(
        json.dumps(text)))


bdd.scenarios('search.feature')
