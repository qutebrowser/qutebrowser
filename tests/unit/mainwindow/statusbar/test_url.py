# SPDX-FileCopyrightText: Clayton Craft (craftyguy) <craftyguy@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test Statusbar url."""

import pytest

from qutebrowser.qt.core import QUrl

from qutebrowser.utils import usertypes, urlutils, qtutils
from qutebrowser.mainwindow.statusbar import url


@pytest.fixture
def url_widget(qtbot, monkeypatch, config_stub):
    """Fixture providing a Url widget."""
    widget = url.UrlText()
    qtbot.add_widget(widget)
    assert not widget.isVisible()
    return widget


qurl_idna2003 = pytest.mark.skipif(
    qtutils.version_check("6.3.0", compiled=False),
    reason="Different result with Qt >= 6.3.0: "
    "https://bugreports.qt.io/browse/QTBUG-85371"
)
qurl_uts46 = pytest.mark.xfail(
    not qtutils.version_check("6.3.0", compiled=False),
    reason="Different result with Qt < 6.3.0: "
    "https://bugreports.qt.io/browse/QTBUG-85371"
)


@pytest.mark.parametrize('url_text, expected', [
    ('http://example.com/foo/bar.html', 'http://example.com/foo/bar.html'),
    ('http://test.gr/%CE%B1%CE%B2%CE%B3%CE%B4.txt', 'http://test.gr/αβγδ.txt'),
    ('http://test.ru/%D0%B0%D0%B1%D0%B2%D0%B3.txt', 'http://test.ru/абвг.txt'),
    ('http://test.com/s%20p%20a%20c%20e.txt', 'http://test.com/s p a c e.txt'),
    ('http://test.com/%22quotes%22.html', 'http://test.com/%22quotes%22.html'),
    ('http://username:secret%20password@test.com', 'http://username@test.com'),
    ('http://example.com%5b/', '(invalid URL!) http://example.com%5b/'),
    # https://bugreports.qt.io/browse/QTBUG-60364
    pytest.param(
        'http://www.xn--80ak6aa92e.com',
        'http://www.xn--80ak6aa92e.com',
        marks=qurl_idna2003
    ),
    pytest.param(
        'http://www.xn--80ak6aa92e.com',
        '(www.xn--80ak6aa92e.com) http://www.аррӏе.com',
        marks=qurl_uts46,
    ),
    # IDN URL
    ('http://www.ä.com', '(www.xn--4ca.com) http://www.ä.com'),
    (None, ''),
])
@pytest.mark.parametrize('which', ['normal', 'hover'])
def test_set_url(url_widget, url_text, expected, which):
    """Test text when hovering over a percent encoded link."""
    if which == 'normal':
        if url_text is None:
            qurl = None
        else:
            qurl = QUrl(url_text)
            if not qurl.isValid():
                # Special case for the invalid URL above
                expected = "Invalid URL!"
        url_widget.set_url(qurl)
    else:
        url_widget.set_hover_url(url_text)

    assert url_widget.text() == expected

    if which == 'hover' and expected:
        assert url_widget._urltype == url.UrlType.hover
    else:
        assert url_widget._urltype == url.UrlType.normal


@pytest.mark.parametrize('status, expected', [
    (usertypes.LoadStatus.success, url.UrlType.success),
    (usertypes.LoadStatus.success_https, url.UrlType.success_https),
    (usertypes.LoadStatus.error, url.UrlType.error),
    (usertypes.LoadStatus.warn, url.UrlType.warn),
    (usertypes.LoadStatus.loading, url.UrlType.normal),
    (usertypes.LoadStatus.none, url.UrlType.normal)
])
def test_on_load_status_changed(url_widget, status, expected):
    """Test text when status is changed."""
    url_widget.set_url(QUrl('www.example.com'))
    url_widget.on_load_status_changed(status)
    assert url_widget._urltype == expected


@pytest.mark.parametrize('load_status, qurl', [
    (usertypes.LoadStatus.success,
     QUrl('http://abc123.com/this/awesome/url.html')),
    (usertypes.LoadStatus.success,
     QUrl('http://reddit.com/r/linux')),
    (usertypes.LoadStatus.success,
     QUrl('http://ä.com/')),
    (usertypes.LoadStatus.success_https,
     QUrl('www.google.com')),
    (usertypes.LoadStatus.success_https,
     QUrl('https://supersecret.gov/nsa/files.txt')),
    (usertypes.LoadStatus.warn,
     QUrl('www.shadysite.org/some/file/with/issues.htm')),
    (usertypes.LoadStatus.error,
     QUrl('invalid::/url')),
    (usertypes.LoadStatus.error,
     QUrl()),
])
def test_on_tab_changed(url_widget, fake_web_tab, load_status, qurl):
    tab_widget = fake_web_tab(load_status=load_status, url=qurl)
    url_widget.on_tab_changed(tab_widget)

    assert url_widget._urltype.name == load_status.name
    if not qurl.isValid():
        expected = ''
    else:
        expected = urlutils.safe_display_string(qurl)
    assert url_widget.text() == expected


@pytest.mark.parametrize('qurl, load_status, expected_status', [
    (
        QUrl('http://abc123.com/this/awesome/url.html'),
        usertypes.LoadStatus.success,
        url.UrlType.success
    ),
    (
        QUrl('https://supersecret.gov/nsa/files.txt'),
        usertypes.LoadStatus.success_https,
        url.UrlType.success_https
    ),
    (
        QUrl('http://www.qutebrowser.org/CONTRIBUTING.html'),
        usertypes.LoadStatus.loading,
        url.UrlType.normal
    ),
    (
        QUrl('www.whatisthisurl.com'),
        usertypes.LoadStatus.warn,
        url.UrlType.warn
    ),
])
def test_normal_url(url_widget, qurl, load_status, expected_status):
    url_widget.set_url(qurl)
    url_widget.on_load_status_changed(load_status)
    url_widget.set_hover_url(qurl.toDisplayString())
    url_widget.set_hover_url("")
    assert url_widget.text() == qurl.toDisplayString()
    assert url_widget._urltype == expected_status
