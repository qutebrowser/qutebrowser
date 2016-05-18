# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Clayton Craft (craftyguy) <craftyguy@gmail.com>
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


"""Test Statusbar url."""

import pytest
import collections

from qutebrowser.browser import webview
from qutebrowser.mainwindow.statusbar import url


@pytest.fixture
def tab_widget():
    """Fixture providing a fake tab widget."""
    tab = collections.namedtuple('Tab', 'cur_url load_status')
    tab.cur_url = collections.namedtuple('cur_url', 'toDisplayString')
    return tab


@pytest.fixture
def url_widget(qtbot, monkeypatch, config_stub):
    """Fixture providing a Url widget."""
    config_stub.data = {
        'colors': {
            'statusbar.url.bg': 'white',
            'statusbar.url.fg': 'black',
            'statusbar.url.fg.success': 'yellow',
            'statusbar.url.fg.success.https': 'green',
            'statusbar.url.fg.error': 'red',
            'statusbar.url.fg.warn': 'orange',
            'statusbar.url.fg.hover': 'blue'
        },
        'fonts': {},
    }
    monkeypatch.setattr(
        'qutebrowser.mainwindow.statusbar.url.style.config', config_stub)
    widget = url.UrlText()
    qtbot.add_widget(widget)
    assert not widget.isVisible()
    return widget


@pytest.mark.parametrize('url_text', [
    'http://abc123.com/this/awesome/url.html',
    'https://supersecret.gov/nsa/files.txt',
    'Th1$ i$ n0t @ n0rm@L uRL! P@n1c! <-->',
    None
])
def test_set_url(url_widget, url_text):
    """Test text displayed by the widget."""
    url_widget.set_url(url_text)
    if url_text is not None:
        assert url_widget.text() == url_text
    else:
        assert url_widget.text() == ""


@pytest.mark.parametrize('url_text, title, text', [
    ('http://abc123.com/this/awesome/url.html', 'Awesome site', 'click me!'),
    ('https://supersecret.gov/nsa/files.txt', 'Secret area', None),
    (None, None, 'did I break?!')
])
def test_set_hover_url(url_widget, url_text, title, text):
    """Test text when hovering over a link."""
    url_widget.set_hover_url(url_text, title, text)
    if url_text is not None:
        assert url_widget.text() == url_text
        assert url_widget._urltype == url.UrlType.hover
    else:
        assert url_widget.text() == ''
        assert url_widget._urltype == url.UrlType.normal


@pytest.mark.parametrize('url_text, expected', [
    ('http://test.gr/%CE%B1%CE%B2%CE%B3%CE%B4.txt', 'http://test.gr/αβγδ.txt'),
    ('http://test.ru/%D0%B0%D0%B1%D0%B2%D0%B3.txt', 'http://test.ru/абвг.txt'),
    ('http://test.com/s%20p%20a%20c%20e.txt', 'http://test.com/s p a c e.txt'),
    ('http://test.com/%22quotes%22.html', 'http://test.com/%22quotes%22.html'),
    ('http://username:secret%20password@test.com', 'http://username@test.com'),
    ('http://valid.com/[%20]', 'http://valid.com/[ ]'),
    ('http://invalid.com[%20]', 'http://invalid.com[%20]')
])
def test_set_hover_url_encoded(url_widget, url_text, expected):
    """Test text when hovering over a percent encoded link."""
    url_widget.set_hover_url(url_text, 'title', 'text')
    assert url_widget.text() == expected
    assert url_widget._urltype == url.UrlType.hover


@pytest.mark.parametrize('status, expected', [
    (webview.LoadStatus.success, url.UrlType.success),
    (webview.LoadStatus.success_https, url.UrlType.success_https),
    (webview.LoadStatus.error, url.UrlType.error),
    (webview.LoadStatus.warn, url.UrlType.warn),
    (webview.LoadStatus.loading, url.UrlType.normal),
    (webview.LoadStatus.none, url.UrlType.normal)
])
def test_on_load_status_changed(url_widget, status, expected):
    """Test text when status is changed."""
    url_widget.set_url('www.example.com')
    url_widget.on_load_status_changed(status.name)
    assert url_widget._urltype == expected


@pytest.mark.parametrize('load_status, url_text', [
    (url.UrlType.success, 'http://abc123.com/this/awesome/url.html'),
    (url.UrlType.success, 'http://reddit.com/r/linux'),
    (url.UrlType.success_https, 'www.google.com'),
    (url.UrlType.success_https, 'https://supersecret.gov/nsa/files.txt'),
    (url.UrlType.warn, 'www.shadysite.org/some/path/to/file/with/issues.htm'),
    (url.UrlType.error, 'Th1$ i$ n0t @ n0rm@L uRL! P@n1c! <-->'),
    (url.UrlType.error, None)
])
def test_on_tab_changed(url_widget, tab_widget, load_status, url_text):
    tab_widget.load_status = load_status
    tab_widget.cur_url.toDisplayString = lambda: url_text
    url_widget.on_tab_changed(tab_widget)
    if url_text is not None:
        assert url_widget._urltype == load_status
        assert url_widget.text() == url_text
    else:
        assert url_widget._urltype == url.UrlType.normal
        assert url_widget.text() == ''


@pytest.mark.parametrize('url_text, load_status, expected_status', [
    ('http://abc123.com/this/awesome/url.html', webview.LoadStatus.success,
        url.UrlType.success),
    ('https://supersecret.gov/nsa/files.txt', webview.LoadStatus.success_https,
        url.UrlType.success_https),
    ('Th1$ i$ n0t @ n0rm@L uRL! P@n1c! <-->', webview.LoadStatus.error,
        url.UrlType.error),
    ('http://www.qutebrowser.org/CONTRIBUTING.html', webview.LoadStatus.loading,
        url.UrlType.normal),
    ('www.whatisthisurl.com', webview.LoadStatus.warn, url.UrlType.warn)
])
def test_normal_url(url_widget, url_text, load_status, expected_status):
    url_widget.set_url(url_text)
    url_widget.on_load_status_changed(load_status.name)
    url_widget.set_hover_url(url_text, "", "")
    url_widget.set_hover_url("", "", "")
    assert url_widget.text() == url_text
    assert url_widget._urltype == expected_status
