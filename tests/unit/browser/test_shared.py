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

import pytest

from qutebrowser.browser import shared


@pytest.mark.parametrize('dnt, accept_language, custom_headers, expected', [
    # DNT
    (True, None, {}, {b'DNT': b'1'}),
    (False, None, {}, {b'DNT': b'0'}),
    (None, None, {}, {}),
    # Accept-Language
    (False, 'de, en', {}, {b'DNT': b'0', b'Accept-Language': b'de, en'}),
    # Custom headers
    (False, None, {'X-Qute': 'yes'}, {b'DNT': b'0', b'X-Qute': b'yes'}),
    # Mixed
    (False, 'de, en', {'X-Qute': 'yes'}, {b'DNT': b'0',
                                          b'Accept-Language': b'de, en',
                                          b'X-Qute': b'yes'}),
])
def test_custom_headers(config_stub, dnt, accept_language, custom_headers,
                        expected):
    headers = config_stub.val.content.headers
    headers.do_not_track = dnt
    headers.accept_language = accept_language
    headers.custom = custom_headers

    expected_items = sorted(expected.items())
    assert shared.custom_headers(url=None) == expected_items
