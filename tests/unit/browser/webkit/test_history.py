# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import base64
import logging

import pytest
import hypothesis
from hypothesis import strategies
from PyQt5.QtCore import QUrl
from PyQt5.QtWebKit import QWebHistoryInterface

from qutebrowser.browser.webkit import history
from qutebrowser.utils import objreg


class FakeWebHistory:

    """A fake WebHistory object."""

    def __init__(self, history_dict):
        self.history_dict = history_dict


@pytest.fixture(autouse=True)
def prerequisites(config_stub, fake_save_manager):
    """Make sure everything is ready to initialize a WebHistory."""
    config_stub.data = {'general': {'private-browsing': False}}


@pytest.fixture()
def hist(tmpdir):
    return history.WebHistory(hist_dir=str(tmpdir), hist_name='history')


def test_async_read_twice(monkeypatch, qtbot, tmpdir, caplog):
    (tmpdir / 'filled-history').write('\n'.join([
        '12345 http://example.com/ title',
        '67890 http://example.com/',
        '12345 http://qutebrowser.org/ blah',
    ]))
    hist = history.WebHistory(hist_dir=str(tmpdir), hist_name='filled-history')
    next(hist.async_read())
    with pytest.raises(StopIteration):
        next(hist.async_read())
    expected = "Ignoring async_read() because reading is started."
    assert len(caplog.records) == 1
    assert caplog.records[0].msg == expected


def test_async_read_no_datadir(qtbot, config_stub, fake_save_manager):
    config_stub.data = {'general': {'private-browsing': False}}
    hist = history.WebHistory(hist_dir=None, hist_name='history')
    with qtbot.waitSignal(hist.async_read_done):
        list(hist.async_read())


@pytest.mark.parametrize('redirect', [True, False])
def test_adding_item_during_async_read(qtbot, hist, redirect):
    """Check what happens when adding URL while reading the history."""
    url = QUrl('http://www.example.com/')

    with qtbot.assertNotEmitted(hist.add_completion_item), \
            qtbot.assertNotEmitted(hist.item_added):
        hist.add_url(url, redirect=redirect, atime=12345)

    if redirect:
        with qtbot.assertNotEmitted(hist.add_completion_item):
            with qtbot.waitSignal(hist.async_read_done):
                list(hist.async_read())
    else:
        with qtbot.waitSignals([hist.add_completion_item,
                                hist.async_read_done]):
            list(hist.async_read())

    assert not hist._temp_history

    expected = history.Entry(url=url, atime=12345, redirect=redirect, title="")
    assert list(hist.history_dict.values()) == [expected]


def test_private_browsing(qtbot, tmpdir, fake_save_manager, config_stub):
    """Make sure no data is saved at all with private browsing."""
    config_stub.data = {'general': {'private-browsing': True}}
    private_hist = history.WebHistory(hist_dir=str(tmpdir),
                                      hist_name='history')

    # Before initial read
    with qtbot.assertNotEmitted(private_hist.add_completion_item), \
            qtbot.assertNotEmitted(private_hist.item_added):
        private_hist.add_url(QUrl('http://www.example.com/'))
    assert not private_hist._temp_history

    # read
    with qtbot.assertNotEmitted(private_hist.add_completion_item), \
            qtbot.assertNotEmitted(private_hist.item_added):
        with qtbot.waitSignals([private_hist.async_read_done]):
            list(private_hist.async_read())

    # after read
    with qtbot.assertNotEmitted(private_hist.add_completion_item), \
            qtbot.assertNotEmitted(private_hist.item_added):
        private_hist.add_url(QUrl('http://www.example.com/'))

    assert not private_hist._temp_history
    assert not private_hist._new_history
    assert not private_hist.history_dict


def test_iter(hist):
    list(hist.async_read())

    url = QUrl('http://www.example.com/')
    hist.add_url(url, atime=12345)

    entry = history.Entry(url=url, atime=12345, redirect=False, title="")
    assert list(hist) == [entry]


def test_len(hist):
    assert len(hist) == 0
    list(hist.async_read())

    url = QUrl('http://www.example.com/')
    hist.add_url(url)

    assert len(hist) == 1


@pytest.mark.parametrize('line', [
    '12345 http://example.com/ title',  # with title
    '67890 http://example.com/',  # no title
    '12345 http://qutebrowser.org/ ',  # trailing space
    ' ',
    '',
])
def test_read(hist, tmpdir, line):
    (tmpdir / 'filled-history').write(line + '\n')
    hist = history.WebHistory(hist_dir=str(tmpdir), hist_name='filled-history')
    list(hist.async_read())


def test_updated_entries(hist, tmpdir):
    (tmpdir / 'filled-history').write('12345 http://example.com/\n'
                                      '67890 http://example.com/\n')
    hist = history.WebHistory(hist_dir=str(tmpdir), hist_name='filled-history')
    list(hist.async_read())

    assert hist.history_dict['http://example.com/'].atime == 67890
    hist.add_url(QUrl('http://example.com/'), atime=99999)
    assert hist.history_dict['http://example.com/'].atime == 99999


def test_invalid_read(hist, tmpdir, caplog):
    (tmpdir / 'filled-history').write('foobar\n12345 http://example.com/')
    hist = history.WebHistory(hist_dir=str(tmpdir), hist_name='filled-history')
    with caplog.at_level(logging.WARNING):
        list(hist.async_read())

    entries = list(hist.history_dict.values())

    assert len(entries) == 1
    assert len(caplog.records) == 1
    msg = "Invalid history entry 'foobar': 2 or 3 fields expected!"
    assert caplog.records[0].msg == msg


def test_get_recent(hist, tmpdir):
    (tmpdir / 'filled-history').write('12345 http://example.com/')
    hist = history.WebHistory(hist_dir=str(tmpdir), hist_name='filled-history')
    list(hist.async_read())

    hist.add_url(QUrl('http://www.qutebrowser.org/'), atime=67890)
    lines = hist.get_recent()

    expected = ['12345 http://example.com/',
                '67890 http://www.qutebrowser.org/']
    assert lines == expected


def test_save(hist, tmpdir):
    hist_file = tmpdir / 'filled-history'
    hist_file.write('12345 http://example.com/\n')

    hist = history.WebHistory(hist_dir=str(tmpdir), hist_name='filled-history')
    list(hist.async_read())

    hist.add_url(QUrl('http://www.qutebrowser.org/'), atime=67890)
    hist.save()

    lines = hist_file.read().splitlines()
    expected = ['12345 http://example.com/',
                '67890 http://www.qutebrowser.org/']
    assert lines == expected

    hist.add_url(QUrl('http://www.the-compiler.org/'), atime=99999)
    hist.save()
    expected.append('99999 http://www.the-compiler.org/')

    lines = hist_file.read().splitlines()
    assert lines == expected


def test_clear(qtbot, hist, tmpdir):
    hist_file = tmpdir / 'filled-history'
    hist_file.write('12345 http://example.com/\n')

    hist = history.WebHistory(hist_dir=str(tmpdir), hist_name='filled-history')
    list(hist.async_read())

    hist.add_url(QUrl('http://www.qutebrowser.org/'))

    with qtbot.waitSignal(hist.cleared):
        hist.clear()

    assert not hist_file.read()
    assert not hist.history_dict
    assert not hist._new_history

    hist.add_url(QUrl('http://www.the-compiler.org/'), atime=67890)
    hist.save()

    lines = hist_file.read().splitlines()
    assert lines == ['67890 http://www.the-compiler.org/']


def test_add_item(qtbot, hist):
    list(hist.async_read())
    url = 'http://www.example.com/'

    with qtbot.waitSignals([hist.add_completion_item, hist.item_added]):
        hist.add_url(QUrl(url), atime=12345, title="the title")

    entry = history.Entry(url=QUrl(url), redirect=False, atime=12345,
                          title="the title")
    assert hist.history_dict[url] == entry


def test_add_item_redirect(qtbot, hist):
    list(hist.async_read())
    url = 'http://www.example.com/'
    with qtbot.assertNotEmitted(hist.add_completion_item):
        with qtbot.waitSignal(hist.item_added):
            hist.add_url(QUrl(url), redirect=True, atime=12345)

    entry = history.Entry(url=QUrl(url), redirect=True, atime=12345, title="")
    assert hist.history_dict[url] == entry


def test_add_item_redirect_update(qtbot, tmpdir):
    """A redirect update added should override a non-redirect one."""
    url = 'http://www.example.com/'

    hist_file = tmpdir / 'filled-history'
    hist_file.write('12345 {}\n'.format(url))
    hist = history.WebHistory(hist_dir=str(tmpdir), hist_name='filled-history')
    list(hist.async_read())

    with qtbot.assertNotEmitted(hist.add_completion_item):
        with qtbot.waitSignal(hist.item_added):
            hist.add_url(QUrl(url), redirect=True, atime=67890)

    entry = history.Entry(url=QUrl(url), redirect=True, atime=67890, title="")
    assert hist.history_dict[url] == entry


@pytest.mark.parametrize('line, expected', [
    (
        # old format without title
        '12345 http://example.com/',
        history.Entry(atime=12345, url=QUrl('http://example.com/'), title='',)
    ),
    (
        # trailing space without title
        '12345 http://example.com/ ',
        history.Entry(atime=12345, url=QUrl('http://example.com/'), title='',)
    ),
    (
        # new format with title
        '12345 http://example.com/ this is a title',
        history.Entry(atime=12345, url=QUrl('http://example.com/'),
                      title='this is a title')
    ),
    (
        # weird NUL bytes
        '\x0012345 http://example.com/',
        history.Entry(atime=12345, url=QUrl('http://example.com/'), title=''),
    ),
    (
        # redirect flag
        '12345-r http://example.com/ this is a title',
        history.Entry(atime=12345, url=QUrl('http://example.com/'),
                      title='this is a title', redirect=True)
    ),
])
def test_entry_parse_valid(line, expected):
    entry = history.Entry.from_str(line)
    assert entry == expected


@pytest.mark.parametrize('line', [
    '12345',  # one field
    '12345 ::',  # invalid URL
    'xyz http://www.example.com/',  # invalid timestamp
    '12345-x http://www.example.com/',  # invalid flags
    '12345-r-r http://www.example.com/',  # double flags
])
def test_entry_parse_invalid(line):
    with pytest.raises(ValueError):
        history.Entry.from_str(line)


@hypothesis.given(strategies.text())
def test_entry_parse_hypothesis(text):
    """Make sure parsing works or gives us ValueError."""
    try:
        history.Entry.from_str(text)
    except ValueError:
        pass


@pytest.mark.parametrize('entry, expected', [
    # simple
    (
        history.Entry(12345, QUrl('http://example.com/'), "the title"),
        "12345 http://example.com/ the title",
    ),
    # timestamp as float
    (
        history.Entry(12345.678, QUrl('http://example.com/'), "the title"),
        "12345 http://example.com/ the title",
    ),
    # no title
    (
        history.Entry(12345.678, QUrl('http://example.com/'), ""),
        "12345 http://example.com/",
    ),
    # redirect flag
    (
        history.Entry(12345.678, QUrl('http://example.com/'), "",
                      redirect=True),
        "12345-r http://example.com/",
    ),
])
def test_entry_str(entry, expected):
    assert str(entry) == expected


@pytest.yield_fixture
def hist_interface():
    entry = history.Entry(atime=0, url=QUrl('http://www.example.com/'),
                          title='example')
    history_dict = {'http://www.example.com/': entry}
    fake_hist = FakeWebHistory(history_dict)
    interface = history.WebHistoryInterface(fake_hist)
    QWebHistoryInterface.setDefaultInterface(interface)
    yield
    QWebHistoryInterface.setDefaultInterface(None)


def test_history_interface(qtbot, webview, hist_interface):
    html = "<a href='about:blank'>foo</a>"
    data = base64.b64encode(html.encode('utf-8')).decode('ascii')
    url = QUrl("data:text/html;charset=utf-8;base64,{}".format(data))
    with qtbot.waitSignal(webview.loadFinished):
        webview.load(url)


def test_init(qapp, tmpdir, monkeypatch, fake_save_manager):
    monkeypatch.setattr(history.standarddir, 'data', lambda: str(tmpdir))
    history.init(qapp)
    hist = objreg.get('web-history')
    assert hist.parent() is qapp
    assert QWebHistoryInterface.defaultInterface()._history is hist
    assert fake_save_manager.add_saveable.called
    objreg.delete('web-history')
