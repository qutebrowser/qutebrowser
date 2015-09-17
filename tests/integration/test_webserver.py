# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Test the httpbin webserver used for tests."""

import urllib.request
import urllib.error

import pytest


@pytest.mark.parametrize('path, content, expected', [
    ('/', '<title>httpbin(1): HTTP Client Testing Service</title>', True),
    # https://github.com/Runscope/httpbin/issues/245
    ('/', 'www.google-analytics.com', False),
    ('/data/hello.txt', 'Hello World!', True),
])
def test_httpbin(httpbin, qtbot, path, content, expected):
    with qtbot.waitSignal(httpbin.new_request, raising=True, timeout=100):
        url = 'http://localhost:{}{}'.format(httpbin.port, path)
        try:
            response = urllib.request.urlopen(url)
        except urllib.error.HTTPError as e:
            # "Though being an exception (a subclass of URLError), an HTTPError
            # can also function as a non-exceptional file-like return value
            # (the same thing that urlopen() returns)."
            # ...wat
            print(e.read().decode('utf-8'))
            raise

    data = response.read().decode('utf-8')

    assert httpbin.get_requests() == [('GET', path)]
    assert (content in data) == expected
