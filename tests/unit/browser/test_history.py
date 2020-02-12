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

"""Tests for the global page history."""

import logging

import pytest
from PyQt5.QtCore import QUrl

from qutebrowser.browser import history
from qutebrowser.utils import urlutils, usertypes
from qutebrowser.api import cmdutils
from qutebrowser.misc import sql, objects


@pytest.fixture(autouse=True)
def prerequisites(config_stub, fake_save_manager, init_sql, fake_args):
    """Make sure everything is ready to initialize a WebHistory."""
    config_stub.data = {'general': {'private-browsing': False}}


class TestSpecialMethods:

    def test_iter(self, web_history):
        urlstr = 'http://www.example.com/'
        url = QUrl(urlstr)
        web_history.add_url(url, atime=12345)

        assert list(web_history) == [(urlstr, '', 12345, False)]

    def test_len(self, web_history):
        assert len(web_history) == 0

        url = QUrl('http://www.example.com/')
        web_history.add_url(url)

        assert len(web_history) == 1

    def test_contains(self, web_history):
        web_history.add_url(QUrl('http://www.example.com/'),
                            title='Title', atime=12345)
        assert 'http://www.example.com/' in web_history
        assert 'www.example.com' not in web_history
        assert 'Title' not in web_history
        assert 12345 not in web_history


class TestGetting:

    def test_get_recent(self, web_history):
        web_history.add_url(QUrl('http://www.qutebrowser.org/'), atime=67890)
        web_history.add_url(QUrl('http://example.com/'), atime=12345)
        assert list(web_history.get_recent()) == [
            ('http://www.qutebrowser.org/', '', 67890, False),
            ('http://example.com/', '', 12345, False),
        ]

    def test_entries_between(self, web_history):
        web_history.add_url(QUrl('http://www.example.com/1'), atime=12345)
        web_history.add_url(QUrl('http://www.example.com/2'), atime=12346)
        web_history.add_url(QUrl('http://www.example.com/3'), atime=12347)
        web_history.add_url(QUrl('http://www.example.com/4'), atime=12348)
        web_history.add_url(QUrl('http://www.example.com/5'), atime=12348)
        web_history.add_url(QUrl('http://www.example.com/6'), atime=12349)
        web_history.add_url(QUrl('http://www.example.com/7'), atime=12350)

        times = [x.atime for x in web_history.entries_between(12346, 12349)]
        assert times == [12349, 12348, 12348, 12347]

    def test_entries_before(self, web_history):
        web_history.add_url(QUrl('http://www.example.com/1'), atime=12346)
        web_history.add_url(QUrl('http://www.example.com/2'), atime=12346)
        web_history.add_url(QUrl('http://www.example.com/3'), atime=12347)
        web_history.add_url(QUrl('http://www.example.com/4'), atime=12348)
        web_history.add_url(QUrl('http://www.example.com/5'), atime=12348)
        web_history.add_url(QUrl('http://www.example.com/6'), atime=12348)
        web_history.add_url(QUrl('http://www.example.com/7'), atime=12349)
        web_history.add_url(QUrl('http://www.example.com/8'), atime=12349)

        times = [x.atime for x in
                 web_history.entries_before(12348, limit=3, offset=2)]
        assert times == [12348, 12347, 12346]


class TestDelete:

    def test_clear(self, qtbot, tmpdir, web_history, mocker):
        web_history.add_url(QUrl('http://example.com/'))
        web_history.add_url(QUrl('http://www.qutebrowser.org/'))

        m = mocker.patch('qutebrowser.browser.history.message.confirm_async',
                         new=mocker.Mock, spec=[])
        history.history_clear()
        assert m.called

    def test_clear_force(self, qtbot, tmpdir, web_history):
        web_history.add_url(QUrl('http://example.com/'))
        web_history.add_url(QUrl('http://www.qutebrowser.org/'))
        history.history_clear(force=True)
        assert not len(web_history)
        assert not len(web_history.completion)

    @pytest.mark.parametrize('raw, escaped', [
        ('http://example.com/1', 'http://example.com/1'),
        ('http://example.com/1 2', 'http://example.com/1%202'),
    ])
    def test_delete_url(self, web_history, raw, escaped):
        web_history.add_url(QUrl('http://example.com/'), atime=0)
        web_history.add_url(QUrl(escaped), atime=0)
        web_history.add_url(QUrl('http://example.com/2'), atime=0)

        before = set(web_history)
        completion_before = set(web_history.completion)

        web_history.delete_url(QUrl(raw))

        diff = before.difference(set(web_history))
        assert diff == {(escaped, '', 0, False)}

        completion_diff = completion_before.difference(
            set(web_history.completion))
        assert completion_diff == {(raw, '', 0)}


class TestAdd:

    @pytest.fixture()
    def mock_time(self, mocker):
        m = mocker.patch('qutebrowser.browser.history.time')
        m.time.return_value = 12345
        return 12345

    @pytest.mark.parametrize(
        'url, atime, title, redirect, history_url, completion_url', [
            ('http://www.example.com', 12346, 'the title', False,
             'http://www.example.com', 'http://www.example.com'),
            ('http://www.example.com', 12346, 'the title', True,
             'http://www.example.com', None),
            ('http://www.example.com/sp ce', 12346, 'the title', False,
             'http://www.example.com/sp%20ce', 'http://www.example.com/sp ce'),
            ('https://user:pass@example.com', 12346, 'the title', False,
             'https://user@example.com', 'https://user@example.com'),
        ]
    )
    def test_add_url(self, qtbot, web_history,
                     url, atime, title, redirect, history_url, completion_url):
        web_history.add_url(QUrl(url), atime=atime, title=title,
                            redirect=redirect)
        assert list(web_history) == [(history_url, title, atime, redirect)]
        if completion_url is None:
            assert not len(web_history.completion)
        else:
            expected = [(completion_url, title, atime)]
            assert list(web_history.completion) == expected

    def test_no_sql_web_history(self, web_history, monkeypatch):
        monkeypatch.setattr(objects, 'debug_flags', {'no-sql-history'})
        web_history.add_url(QUrl('https://www.example.com/'), atime=12346,
                            title='Hello World', redirect=False)
        assert not list(web_history)

    def test_invalid(self, qtbot, web_history, caplog):
        with caplog.at_level(logging.WARNING):
            web_history.add_url(QUrl())
        assert not list(web_history)
        assert not list(web_history.completion)

    @pytest.mark.parametrize('known_error', [True, False])
    @pytest.mark.parametrize('completion', [True, False])
    def test_error(self, monkeypatch, web_history, message_mock, caplog,
                   known_error, completion):
        def raise_error(url, replace=False):
            if known_error:
                raise sql.KnownError("Error message")
            raise sql.BugError("Error message")

        if completion:
            monkeypatch.setattr(web_history.completion, 'insert', raise_error)
        else:
            monkeypatch.setattr(web_history, 'insert', raise_error)

        if known_error:
            with caplog.at_level(logging.ERROR):
                web_history.add_url(QUrl('https://www.example.org/'))
            msg = message_mock.getmsg(usertypes.MessageLevel.error)
            assert msg.text == "Failed to write history: Error message"
        else:
            with pytest.raises(sql.BugError):
                web_history.add_url(QUrl('https://www.example.org/'))

    @pytest.mark.parametrize('level, url, req_url, expected', [
        (logging.DEBUG, 'a.com', 'a.com', [('a.com', 'title', 12345, False)]),
        (logging.DEBUG, 'a.com', 'b.com', [('a.com', 'title', 12345, False),
                                           ('b.com', 'title', 12345, True)]),
        (logging.WARNING, 'a.com', '', [('a.com', 'title', 12345, False)]),
        (logging.WARNING, '', '', []),
        (logging.WARNING, 'data:foo', '', []),
        (logging.WARNING, 'a.com', 'data:foo', []),
    ])
    def test_from_tab(self, web_history, caplog, mock_time,
                      level, url, req_url, expected):
        with caplog.at_level(level):
            web_history.add_from_tab(QUrl(url), QUrl(req_url), 'title')
        assert set(web_history) == set(expected)

    def test_exclude(self, web_history, config_stub):
        """Excluded URLs should be in the history but not completion."""
        config_stub.val.completion.web_history.exclude = ['*.example.org']
        url = QUrl('http://www.example.org/')
        web_history.add_from_tab(url, url, 'title')
        assert list(web_history)
        assert not list(web_history.completion)

    def test_no_immedate_duplicates(self, web_history, mock_time):
        url = QUrl("http://example.com")
        url2 = QUrl("http://example2.com")
        web_history.add_from_tab(QUrl(url), QUrl(url), 'title')
        hist = list(web_history)
        assert hist
        web_history.add_from_tab(QUrl(url), QUrl(url), 'title')
        assert list(web_history) == hist
        web_history.add_from_tab(QUrl(url2), QUrl(url2), 'title')
        assert list(web_history) != hist

    def test_delete_add_tab(self, web_history, mock_time):
        url = QUrl("http://example.com")
        web_history.add_from_tab(QUrl(url), QUrl(url), 'title')
        hist = list(web_history)
        assert hist
        web_history.delete_url(QUrl(url))
        assert len(web_history) == 0
        web_history.add_from_tab(QUrl(url), QUrl(url), 'title')
        assert list(web_history) == hist

    def test_clear_add_tab(self, web_history, mock_time):
        url = QUrl("http://example.com")
        web_history.add_from_tab(QUrl(url), QUrl(url), 'title')
        hist = list(web_history)
        assert hist
        history.history_clear(force=True)
        assert len(web_history) == 0
        web_history.add_from_tab(QUrl(url), QUrl(url), 'title')
        assert list(web_history) == hist


class TestHistoryInterface:

    @pytest.fixture
    def hist_interface(self, web_history):
        # pylint: disable=invalid-name
        QtWebKit = pytest.importorskip('PyQt5.QtWebKit')
        from qutebrowser.browser.webkit import webkithistory
        QWebHistoryInterface = QtWebKit.QWebHistoryInterface
        # pylint: enable=invalid-name
        web_history.add_url(url=QUrl('http://www.example.com/'),
                            title='example')
        interface = webkithistory.WebHistoryInterface(web_history)
        QWebHistoryInterface.setDefaultInterface(interface)
        yield
        QWebHistoryInterface.setDefaultInterface(None)

    def test_history_interface(self, qtbot, webview, hist_interface):
        html = b"<a href='about:blank'>foo</a>"
        url = urlutils.data_url('text/html', html)
        with qtbot.waitSignal(webview.loadFinished):
            webview.load(url)


class TestInit:

    @pytest.fixture
    def cleanup_init(self):
        # prevent test_init from leaking state
        yield
        if history.web_history is not None:
            history.web_history.setParent(None)
            history.web_history = None
        try:
            from PyQt5.QtWebKit import QWebHistoryInterface
            QWebHistoryInterface.setDefaultInterface(None)
        except ImportError:
            pass

    @pytest.mark.parametrize('backend', [usertypes.Backend.QtWebEngine,
                                         usertypes.Backend.QtWebKit])
    def test_init(self, backend, qapp, tmpdir, monkeypatch, cleanup_init):
        if backend == usertypes.Backend.QtWebKit:
            pytest.importorskip('PyQt5.QtWebKitWidgets')
        else:
            assert backend == usertypes.Backend.QtWebEngine

        monkeypatch.setattr(history.objects, 'backend', backend)
        history.init(qapp)
        assert history.web_history.parent() is qapp

        try:
            from PyQt5.QtWebKit import QWebHistoryInterface
        except ImportError:
            QWebHistoryInterface = None

        if backend == usertypes.Backend.QtWebKit:
            default_interface = QWebHistoryInterface.defaultInterface()
            assert default_interface._history is history.web_history
        else:
            assert backend == usertypes.Backend.QtWebEngine
            if QWebHistoryInterface is None:
                default_interface = None
            else:
                default_interface = QWebHistoryInterface.defaultInterface()
            # For this to work, nothing can ever have called
            # setDefaultInterface before (so we need to test webengine before
            # webkit)
            assert default_interface is None


class TestDump:

    def test_debug_dump_history(self, web_history, tmpdir):
        web_history.add_url(QUrl('http://example.com/1'),
                            title="Title1", atime=12345)
        web_history.add_url(QUrl('http://example.com/2'),
                            title="Title2", atime=12346)
        web_history.add_url(QUrl('http://example.com/3'),
                            title="Title3", atime=12347)
        web_history.add_url(QUrl('http://example.com/4'),
                            title="Title4", atime=12348, redirect=True)
        histfile = tmpdir / 'history'
        history.debug_dump_history(str(histfile))
        expected = ['12345 http://example.com/1 Title1',
                    '12346 http://example.com/2 Title2',
                    '12347 http://example.com/3 Title3',
                    '12348-r http://example.com/4 Title4']
        assert histfile.read() == '\n'.join(expected)

    def test_nonexistent(self, web_history, tmpdir):
        histfile = tmpdir / 'nonexistent' / 'history'
        with pytest.raises(cmdutils.CommandError):
            history.debug_dump_history(str(histfile))


class TestRebuild:

    def test_delete(self, web_history, stubs):
        web_history.insert({'url': 'example.com/1', 'title': 'example1',
                            'redirect': False, 'atime': 1})
        web_history.insert({'url': 'example.com/1', 'title': 'example1',
                            'redirect': False, 'atime': 2})
        web_history.insert({'url': 'example.com/2%203', 'title': 'example2',
                            'redirect': False, 'atime': 3})
        web_history.insert({'url': 'example.com/3', 'title': 'example3',
                            'redirect': True, 'atime': 4})
        web_history.insert({'url': 'example.com/2 3', 'title': 'example2',
                            'redirect': False, 'atime': 5})
        web_history.completion.delete_all()

        hist2 = history.WebHistory(progress=stubs.FakeHistoryProgress())
        assert list(hist2.completion) == [
            ('example.com/1', 'example1', 2),
            ('example.com/2 3', 'example2', 5),
        ]

    def test_no_rebuild(self, web_history, stubs):
        """Ensure that completion is not regenerated unless empty."""
        web_history.add_url(QUrl('example.com/1'), redirect=False, atime=1)
        web_history.add_url(QUrl('example.com/2'), redirect=False, atime=2)
        web_history.completion.delete('url', 'example.com/2')

        hist2 = history.WebHistory(progress=stubs.FakeHistoryProgress())
        assert list(hist2.completion) == [('example.com/1', '', 1)]

    def test_user_version(self, web_history, stubs, monkeypatch):
        """Ensure that completion is regenerated if user_version changes."""
        web_history.add_url(QUrl('example.com/1'), redirect=False, atime=1)
        web_history.add_url(QUrl('example.com/2'), redirect=False, atime=2)
        web_history.completion.delete('url', 'example.com/2')

        hist2 = history.WebHistory(progress=stubs.FakeHistoryProgress())
        assert list(hist2.completion) == [('example.com/1', '', 1)]

        monkeypatch.setattr(history, '_USER_VERSION',
                            history._USER_VERSION + 1)
        hist3 = history.WebHistory(progress=stubs.FakeHistoryProgress())
        assert list(hist3.completion) == [
            ('example.com/1', '', 1),
            ('example.com/2', '', 2),
        ]

    def test_force_rebuild(self, web_history, stubs):
        """Ensure that completion is regenerated if we force a rebuild."""
        web_history.add_url(QUrl('example.com/1'), redirect=False, atime=1)
        web_history.add_url(QUrl('example.com/2'), redirect=False, atime=2)
        web_history.completion.delete('url', 'example.com/2')

        hist2 = history.WebHistory(progress=stubs.FakeHistoryProgress())
        assert list(hist2.completion) == [('example.com/1', '', 1)]
        hist2.metainfo['force_rebuild'] = True

        hist3 = history.WebHistory(progress=stubs.FakeHistoryProgress())
        assert list(hist3.completion) == [
            ('example.com/1', '', 1),
            ('example.com/2', '', 2),
        ]
        assert not hist3.metainfo['force_rebuild']

    def test_exclude(self, config_stub, web_history, stubs):
        """Ensure that patterns in completion.web_history.exclude are ignored.

        This setting should only be used for the completion.
        """
        config_stub.val.completion.web_history.exclude = ['*.example.org']
        assert web_history.metainfo['force_rebuild']

        web_history.add_url(QUrl('http://example.com'),
                            redirect=False, atime=1)
        web_history.add_url(QUrl('http://example.org'),
                            redirect=False, atime=2)

        hist2 = history.WebHistory(progress=stubs.FakeHistoryProgress())
        assert list(hist2.completion) == [('http://example.com', '', 1)]

    def test_unrelated_config_change(self, config_stub, web_history):
        config_stub.val.history_gap_interval = 1234
        assert not web_history.metainfo['force_rebuild']

    @pytest.mark.parametrize('patch_threshold', [True, False])
    def test_progress(self, web_history, config_stub, monkeypatch, stubs,
                      patch_threshold):
        web_history.add_url(QUrl('example.com/1'), redirect=False, atime=1)
        web_history.add_url(QUrl('example.com/2'), redirect=False, atime=2)
        web_history.metainfo['force_rebuild'] = True

        if patch_threshold:
            monkeypatch.setattr(history.WebHistory, '_PROGRESS_THRESHOLD', 1)

        progress = stubs.FakeHistoryProgress()
        history.WebHistory(progress=progress)
        assert progress._value == 2
        assert progress._finished
        assert progress._started == patch_threshold


class TestCompletionMetaInfo:

    @pytest.fixture
    def metainfo(self):
        return history.CompletionMetaInfo()

    def test_contains_keyerror(self, metainfo):
        with pytest.raises(KeyError):
            'does_not_exist' in metainfo  # pylint: disable=pointless-statement

    def test_getitem_keyerror(self, metainfo):
        with pytest.raises(KeyError):
            metainfo['does_not_exist']  # pylint: disable=pointless-statement

    def test_setitem_keyerror(self, metainfo):
        with pytest.raises(KeyError):
            metainfo['does_not_exist'] = 42

    def test_contains(self, metainfo):
        assert 'force_rebuild' in metainfo

    def test_modify(self, metainfo):
        assert not metainfo['force_rebuild']
        metainfo['force_rebuild'] = True
        assert metainfo['force_rebuild']


class TestHistoryProgress:

    @pytest.fixture
    def progress(self):
        return history.HistoryProgress()

    def test_no_start(self, progress):
        """Test calling tick/finish without start."""
        progress.tick()
        progress.finish()
        assert progress._progress is None
        assert progress._value == 1

    def test_gui(self, qtbot, progress):
        progress.start("Hello World", 42)
        dialog = progress._progress
        qtbot.add_widget(dialog)
        progress.tick()

        assert dialog.isVisible()
        assert dialog.labelText() == "Hello World"
        assert dialog.minimum() == 0
        assert dialog.maximum() == 42
        assert dialog.value() == 1
        assert dialog.minimumDuration() == 500

        progress.finish()
        assert not dialog.isVisible()
