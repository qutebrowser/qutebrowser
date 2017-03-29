# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for the global page history."""

import logging

import pytest
import hypothesis
from hypothesis import strategies
from PyQt5.QtCore import QUrl

from qutebrowser.browser import history
from qutebrowser.utils import objreg, urlutils, usertypes


@pytest.fixture(autouse=True)
def prerequisites(config_stub, fake_save_manager, init_sql):
    """Make sure everything is ready to initialize a WebHistory."""
    config_stub.data = {'general': {'private-browsing': False}}


@pytest.fixture()
def hist(tmpdir):
    return history.WebHistory()


@pytest.fixture()
def mock_time(mocker):
    m = mocker.patch('qutebrowser.browser.history.time')
    m.time.return_value = 12345
    return 12345


def test_iter(hist):
    urlstr = 'http://www.example.com/'
    url = QUrl(urlstr)
    hist.add_url(url, atime=12345)

    assert list(hist) == [(urlstr, '', 12345, False)]


def test_len(hist):
    assert len(hist) == 0

    url = QUrl('http://www.example.com/')
    hist.add_url(url)

    assert len(hist) == 1


def test_updated_entries(tmpdir, hist):
    hist.add_url(QUrl('http://example.com/'), atime=67890)
    assert list(hist) == [('http://example.com/', '', 67890, False)]

    hist.add_url(QUrl('http://example.com/'), atime=99999)
    assert list(hist) == [('http://example.com/', '', 99999, False)]


def test_get_recent(hist):
    hist.add_url(QUrl('http://www.qutebrowser.org/'), atime=67890)
    hist.add_url(QUrl('http://example.com/'), atime=12345)
    assert list(hist.get_recent()) == [
        ('http://www.qutebrowser.org/', '', 67890 , False),
        ('http://example.com/', '', 12345, False),
    ]


def test_save(tmpdir, hist):
    hist.add_url(QUrl('http://example.com/'), atime=12345)
    hist.add_url(QUrl('http://www.qutebrowser.org/'), atime=67890)

    hist2 = history.WebHistory()
    assert list(hist2) == [('http://example.com/', '', 12345, False),
                           ('http://www.qutebrowser.org/', '', 67890, False)]


def test_clear(qtbot, tmpdir, hist, mocker):
    hist.add_url(QUrl('http://example.com/'))
    hist.add_url(QUrl('http://www.qutebrowser.org/'))

    m = mocker.patch('qutebrowser.browser.history.message.confirm_async')
    hist.clear()
    m.assert_called()


def test_clear_force(qtbot, tmpdir, hist):
    hist.add_url(QUrl('http://example.com/'))
    hist.add_url(QUrl('http://www.qutebrowser.org/'))

    with qtbot.waitSignal(hist.cleared):
        hist.clear(force=True)

    assert not len(hist)


@pytest.mark.parametrize('item', [
    ('http://www.example.com', 12346, 'the title', False),
    ('http://www.example.com', 12346, 'the title', True)
])
def test_add_item(qtbot, hist, item):
    (url, atime, title, redirect) = item
    hist.add_url(QUrl(url), atime=atime, title=title, redirect=redirect)
    assert hist[url] == (url, title, atime, redirect)


def test_add_item_invalid(qtbot, hist, caplog):
    with caplog.at_level(logging.WARNING):
        hist.add_url(QUrl())
    assert not list(hist)


@pytest.mark.parametrize('level, url, req_url, expected', [
    (logging.DEBUG, 'a.com', 'a.com', [('a.com', 'title', 12345, False)]),
    (logging.DEBUG, 'a.com', 'b.com', [('a.com', 'title', 12345, False),
                                       ('b.com', 'title', 12345, True)]),
    (logging.WARNING, 'a.com', '', [('a.com', 'title', 12345, False)]),
    (logging.WARNING, '', '', []),
])
def test_add_from_tab(hist, level, url, req_url, expected, mock_time, caplog):
    with caplog.at_level(level):
        hist.add_from_tab(QUrl(url), QUrl(req_url), 'title')
    assert set(list(hist)) == set(expected)


def test_add_item_redirect_update(qtbot, tmpdir, hist):
    """A redirect update added should override a non-redirect one."""
    url = 'http://www.example.com/'
    hist.add_url(QUrl(url), atime=5555)
    hist.add_url(QUrl(url), redirect=True, atime=67890)

    assert hist[url] == (url, '', 67890, True)


@pytest.fixture
def hist_interface():
    # pylint: disable=invalid-name
    QtWebKit = pytest.importorskip('PyQt5.QtWebKit')
    from qutebrowser.browser.webkit import webkithistory
    QWebHistoryInterface = QtWebKit.QWebHistoryInterface
    # pylint: enable=invalid-name
    entry = history.Entry(atime=0, url=QUrl('http://www.example.com/'),
                          title='example')
    history_dict = {'http://www.example.com/': entry}
    interface = webkithistory.WebHistoryInterface(history_dict)
    QWebHistoryInterface.setDefaultInterface(interface)
    yield
    QWebHistoryInterface.setDefaultInterface(None)


def test_history_interface(qtbot, webview, hist_interface):
    html = b"<a href='about:blank'>foo</a>"
    url = urlutils.data_url('text/html', html)
    with qtbot.waitSignal(webview.loadFinished):
        webview.load(url)


@pytest.fixture
def cleanup_init():
    # prevent test_init from leaking state
    yield
    try:
        hist = objreg.get('web-history')
        hist.setParent(None)
        objreg.delete('web-history')
        from PyQt5.QtWebKit import QWebHistoryInterface
        QWebHistoryInterface.setDefaultInterface(None)
    except:
        pass


@pytest.mark.parametrize('backend', [usertypes.Backend.QtWebEngine,
                                     usertypes.Backend.QtWebKit])
def test_init(backend, qapp, tmpdir, monkeypatch, cleanup_init):
    if backend == usertypes.Backend.QtWebKit:
        pytest.importorskip('PyQt5.QtWebKitWidgets')
    else:
        assert backend == usertypes.Backend.QtWebEngine

    monkeypatch.setattr(history.standarddir, 'data', lambda: str(tmpdir))
    monkeypatch.setattr(history.objects, 'backend', backend)
    history.init(qapp)
    hist = objreg.get('web-history')
    assert hist.parent() is qapp

    try:
        from PyQt5.QtWebKit import QWebHistoryInterface
    except ImportError:
        QWebHistoryInterface = None

    if backend == usertypes.Backend.QtWebKit:
        default_interface = QWebHistoryInterface.defaultInterface()
        assert default_interface._history is hist
    else:
        assert backend == usertypes.Backend.QtWebEngine
        if QWebHistoryInterface is None:
            default_interface = None
        else:
            default_interface = QWebHistoryInterface.defaultInterface()
        # For this to work, nothing can ever have called setDefaultInterface
        # before (so we need to test webengine before webkit)
        assert default_interface is None


def test_read(hist, tmpdir, caplog):
    histfile = tmpdir / 'history'
    histfile.write('''12345 http://example.com/ title
                      12346 http://qutebrowser.org/
                      67890 http://example.com/path

                      xyz http://example.com/bad-timestamp
                      12345
                      http://example.com/no-timestamp
                      68891-r http://example.com/path/other
                      68891-r-r http://example.com/double-flag''')

    with caplog.at_level(logging.WARNING):
        hist.read(str(histfile))

    assert list(hist) == [
        ('http://example.com/', 'title', 12345, False),
        ('http://qutebrowser.org/', '', 12346, False),
        ('http://example.com/path', '', 67890, False),
        ('http://example.com/path/other', '', 68891, True)
    ]
