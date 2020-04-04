# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from PyQt5.QtCore import QUrl

from qutebrowser.browser import navigate
from qutebrowser.utils import urlutils


class TestIncDec:

    pytestmark = pytest.mark.usefixtures('config_stub')

    @pytest.mark.parametrize('incdec', ['increment', 'decrement'])
    @pytest.mark.parametrize('value', [
        '{}foo', 'foo{}', 'foo{}bar', '42foo{}'
    ])
    @pytest.mark.parametrize('url', [
        'http://example.com:80/v1/path/{}/test',
        'http://example.com:80/v1/query_test?value={}',
        'http://example.com:80/v1/anchor_test#{}',
        'http://host_{}_test.com:80',
        'http://m4ny.c0m:80/number5/3very?where=yes#{}',

        # Make sure that FullyDecoded is not used (to avoid losing information)
        'http://localhost/%3A{}',
        'http://localhost/:{}',
        'http://localhost/?v=%3A{}',
        'http://localhost/?v=:{}',
        'http://localhost/#%3A{}',
        'http://localhost/#:{}',

        # Make sure that spaces in paths work
        'http://example.com/path with {} spaces',
    ])
    def test_incdec(self, incdec, value, url, config_stub):
        if (value == '{}foo' and
                url == 'http://example.com/path with {} spaces'):
            pytest.xfail("https://github.com/qutebrowser/qutebrowser/issues/4917")

        config_stub.val.url.incdec_segments = ['host', 'path', 'query',
                                               'anchor']

        # The integer used should not affect test output, as long as it's
        # bigger than 1
        # 20 was chosen by dice roll, guaranteed to be random
        base_value = value.format(20)
        if incdec == 'increment':
            expected_value = value.format(21)
        else:
            expected_value = value.format(19)

        base_url = QUrl(url.format(base_value))
        expected_url = QUrl(url.format(expected_value))

        assert navigate.incdec(base_url, 1, incdec) == expected_url

    def test_port(self, config_stub):
        config_stub.val.url.incdec_segments = ['port']
        base_url = QUrl('http://localhost:8000')
        new_url = navigate.incdec(base_url, 1, 'increment')
        assert new_url == QUrl('http://localhost:8001')
        new_url = navigate.incdec(base_url, 1, 'decrement')
        assert new_url == QUrl('http://localhost:7999')

    def test_port_default(self, config_stub):
        """Test that a default port (with url.port() == -1) is not touched."""
        config_stub.val.url.incdec_segments = ['port']
        base_url = QUrl('http://localhost')
        with pytest.raises(navigate.Error):
            navigate.incdec(base_url, 1, 'increment')

    @pytest.mark.parametrize('inc_or_dec', ['increment', 'decrement'])
    @pytest.mark.parametrize('value', [
        '{}foo', 'foo{}', 'foo{}bar', '42foo{}'
    ])
    @pytest.mark.parametrize('url', [
        'http://example.com:80/v1/path/{}/test',
        'http://example.com:80/v1/query_test?value={}',
        'http://example.com:80/v1/anchor_test#{}',
        'http://host_{}_test.com:80',
        'http://m4ny.c0m:80/number5/3very?where=yes#{}',
    ])
    @pytest.mark.parametrize('count', [1, 5, 100])
    def test_count(self, inc_or_dec, value, url, count, config_stub):
        config_stub.val.url.incdec_segments = ['host', 'path', 'query',
                                               'anchor']
        base_value = value.format(20)
        if inc_or_dec == 'increment':
            expected_value = value.format(20 + count)
        else:
            if count > 20:
                return
            expected_value = value.format(20 - count)

        base_url = QUrl(url.format(base_value))
        expected_url = QUrl(url.format(expected_value))
        new_url = navigate.incdec(base_url, count, inc_or_dec)

        assert new_url == expected_url

    @pytest.mark.parametrize('number, expected, inc_or_dec', [
        ('01', '02', 'increment'),
        ('09', '10', 'increment'),
        ('009', '010', 'increment'),
        ('02', '01', 'decrement'),
        ('10', '9', 'decrement'),
        ('010', '009', 'decrement')
    ])
    def test_leading_zeroes(self, number, expected, inc_or_dec, config_stub):
        config_stub.val.url.incdec_segments = ['path']
        url = 'http://example.com/{}'
        base_url = QUrl(url.format(number))
        expected_url = QUrl(url.format(expected))
        new_url = navigate.incdec(base_url, 1, inc_or_dec)
        assert new_url == expected_url

    @pytest.mark.parametrize('url, segments, expected', [
        ('http://ex4mple.com/test_4?page=3#anchor2', ['host'],
         'http://ex5mple.com/test_4?page=3#anchor2'),
        ('http://ex4mple.com/test_4?page=3#anchor2', ['host', 'path'],
         'http://ex4mple.com/test_5?page=3#anchor2'),
        ('http://ex4mple.com/test_4?page=3#anchor5', ['host', 'path', 'query'],
         'http://ex4mple.com/test_4?page=4#anchor5'),
    ])
    def test_segment_ignored(self, url, segments, expected, config_stub):
        config_stub.val.url.incdec_segments = segments
        new_url = navigate.incdec(QUrl(url), 1, 'increment')
        assert new_url == QUrl(expected)

    @pytest.mark.parametrize('url', [
        "http://example.com/long/path/but/no/number",
        "http://ex4mple.com/number/in/hostname",
        "http://example.com:42/number/in/port",
        "http://www2.example.com/number/in/subdomain",
        "http://example.com/%C3%B6/urlencoded/data",
        "http://example.com/number/in/anchor#5",
        "http://www2.ex4mple.com:42/all/of/the/%C3%A4bove#5",
        "http://localhost/url_encoded_in_query/?v=%3A",
        "http://localhost/url_encoded_in_anchor/#%3A",
    ])
    def test_no_number(self, url):
        with pytest.raises(navigate.Error):
            navigate.incdec(QUrl(url), 1, "increment")

    @pytest.mark.parametrize('url, count', [
        ('http://example.com/page_0.html', 1),
        ('http://example.com/page_1.html', 2),
    ])
    def test_number_below_0(self, url, count):
        with pytest.raises(navigate.Error):
            navigate.incdec(QUrl(url), count, 'decrement')

    def test_invalid_url(self):
        with pytest.raises(urlutils.InvalidUrlError):
            navigate.incdec(QUrl(""), 1, "increment")

    def test_wrong_mode(self):
        """Test if incdec rejects a wrong parameter for inc_or_dec."""
        valid_url = QUrl("http://example.com/0")
        with pytest.raises(ValueError):
            navigate.incdec(valid_url, 1, "foobar")
