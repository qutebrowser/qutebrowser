# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from collections import namedtuple
from qutebrowser.mainwindow.statusbar.url import UrlText
from qutebrowser.utils import usertypes


UrlType = usertypes.enum('UrlType', ['success', 'success_https', 'error',
                                    'warn', 'hover', 'normal'])


@pytest.fixture
def tab_widget():
    """Fixture providing a fake tab widget."""
    tab = namedtuple('Tab', 'cur_url load_status')
    tab.load_status = namedtuple('load_status', 'name')
    tab.cur_url = namedtuple('cur_url', 'toDisplayString')
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
            'statusbar.url.fg.hover': 'blue'},
        'fonts': {},
    }
    monkeypatch.setattr(
        'qutebrowser.mainwindow.statusbar.url.style.config', config_stub)
    widget = UrlText()
    qtbot.add_widget(widget)
    assert not widget.isVisible()
    return widget


@pytest.mark.parametrize('url', [
    ('http://abc123.com/this/awesome/url.html'),
    ('https://supersecret.gov/nsa/files.txt'),
    ('Th1$ i$ n0t @ n0rm@L uRL! P@n1c! <-->'),
    (None)
])
def test_set_url(url_widget, url):
    """Test text displayed by the widget."""
    url_widget.set_url(url)
    if url is not None:
        assert url_widget.text() == url
    else:
        assert url_widget.text() == ""


@pytest.mark.parametrize('url, title, text', [
    ('http://abc123.com/this/awesome/url.html', 'Awesome site', 'click me!'),
    ('https://supersecret.gov/nsa/files.txt', 'Secret area', None),
    ('Th1$ i$ n0t @ n0rm@L uRL! P@n1c! <-->', 'Probably spam', 'definitely'),
    (None, None, 'did I break?!')
])
def test_set_hover_url(url_widget, url, title, text):
    """Test text when hovering over a link."""
    url_widget.set_hover_url(url, title, text)
    if url is not None:
        assert url_widget.text() == url
    else:
        assert url_widget.text() == ''


@pytest.mark.parametrize('status, expected', [
    ('success', 'success'),
    ('success_https', 'success_https'),
    ('error', 'error'),
    ('warn', 'warn')
])
def test_on_load_status_changed(url_widget, status, expected):
    """Test text when status is changed."""
    url_widget.set_url('www.example.com')
    url_widget.on_load_status_changed(status)
    assert url_widget._urltype.name == expected


@pytest.mark.parametrize('load_status, url', [
    ('success', 'http://abc123.com/this/awesome/url.html'),
    ('success', 'http://reddit.com/r/linux'),
    ('success_https', 'www.google.com'),
    ('success_https', 'https://supersecret.gov/nsa/files.txt'),
    ('warn', 'www.shadysite.org/some/path/to/a/file/that/has/issues.htm'),
    ('error', 'Th1$ i$ n0t @ n0rm@L uRL! P@n1c! <-->'),
    ('error', None)
])
def test_on_tab_changed(url_widget, tab_widget, load_status, url):
    tab_widget.load_status.name = load_status
    tab_widget.cur_url.toDisplayString = lambda: url
    url_widget.on_tab_changed(tab_widget)
    if url is not None:
        assert url_widget._urltype.name == load_status
        assert url_widget.text() == url
    else:
        assert url_widget._urltype.name == 'normal'
        assert url_widget.text() == ''
