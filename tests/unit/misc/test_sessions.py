# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for qutebrowser.misc.sessions."""

import os
import textwrap
import logging

import pytest
import yaml
from PyQt5.QtCore import QUrl, QPoint, QByteArray, QObject
from PyQt5.QtWebKitWidgets import QWebView

from qutebrowser.misc import sessions
from qutebrowser.utils import objreg, qtutils
from qutebrowser.browser.webkit import tabhistory
from qutebrowser.browser.webkit.tabhistory import TabHistoryItem as Item
from qutebrowser.commands import cmdexc


pytestmark = pytest.mark.qt_log_ignore('QIODevice::read.*: device not open',
                                       extend=True)

webengine_refactoring_xfail = pytest.mark.xfail(
    True, reason='Broke during QtWebEngine refactoring, will be fixed after '
                 'sessions are refactored too.')


@pytest.fixture
def sess_man():
    """Fixture providing a SessionManager with no session dir."""
    return sessions.SessionManager(base_path=None)


class TestInit:

    @pytest.yield_fixture(autouse=True)
    def cleanup(self):
        yield
        objreg.delete('session-manager')

    def test_no_standarddir(self, monkeypatch):
        monkeypatch.setattr('qutebrowser.misc.sessions.standarddir.data',
                            lambda: None)
        sessions.init()
        manager = objreg.get('session-manager')
        assert manager._base_path is None

    @pytest.mark.parametrize('create_dir', [True, False])
    def test_with_standarddir(self, tmpdir, monkeypatch, create_dir):
        monkeypatch.setattr('qutebrowser.misc.sessions.standarddir.data',
                            lambda: str(tmpdir))
        session_dir = tmpdir / 'sessions'
        if create_dir:
            session_dir.ensure(dir=True)

        sessions.init()
        manager = objreg.get('session-manager')

        assert session_dir.exists()
        assert manager._base_path == str(session_dir)


def test_did_not_load(sess_man):
    assert not sess_man.did_load


class TestExists:

    @pytest.mark.parametrize('absolute', [True, False])
    def test_existent(self, tmpdir, absolute):
        session_dir = tmpdir / 'sessions'
        abs_session = tmpdir / 'foo.yml'
        rel_session = session_dir / 'foo.yml'

        session_dir.ensure(dir=True)
        abs_session.ensure()
        rel_session.ensure()

        man = sessions.SessionManager(str(session_dir))

        if absolute:
            name = str(abs_session)
        else:
            name = 'foo'

        assert man.exists(name)

    @pytest.mark.parametrize('absolute', [True, False])
    def test_inexistent(self, tmpdir, absolute):
        man = sessions.SessionManager(str(tmpdir))

        if absolute:
            name = str(tmpdir / 'foo')
        else:
            name = 'foo'

        assert not man.exists(name)

    @pytest.mark.parametrize('absolute', [True, False])
    def test_no_datadir(self, sess_man, tmpdir, absolute):
        abs_session = tmpdir / 'foo.yml'
        abs_session.ensure()

        if absolute:
            assert sess_man.exists(str(abs_session))
        else:
            assert not sess_man.exists('foo')


class HistTester:

    """Helper object for the hist_tester fixture.

    Makes it possible to use tabhistory.TabHistoryItem objects to easily load
    data into a QWebHistory, does some basic checks, and provides the
    serialized history.

    Attributes:
        sess_man: The SessionManager which is used.
        webview: The WebView where the history is loaded to.
    """

    def __init__(self, webview):
        self.sess_man = sessions.SessionManager(base_path=None)
        self.webview = webview

    def get(self, items):
        """Get the serialized history for the given items.

        Args:
            items: A list of TabHistoryItems.

        Return:
            A list of serialized items, as dicts.
        """
        history = self.webview.page().history()

        stream, _data, user_data = tabhistory.serialize(items)
        qtutils.deserialize_stream(stream, history)
        for i, data in enumerate(user_data):
            history.itemAt(i).setUserData(data)

        d = self.sess_man._save_tab(self.webview, active=True)
        new_history = d['history']
        assert len(new_history) == len(items)
        return new_history

    def get_single(self, item):
        """Convenience method to use get() with a single item."""
        ret = self.get([item])
        assert len(ret) == 1
        return ret[0]


@webengine_refactoring_xfail
class TestSaveTab:

    @pytest.fixture
    def hist_tester(self, webview):
        """Helper to test saving of history."""
        return HistTester(webview)

    @pytest.mark.parametrize('is_active', [True, False])
    def test_active(self, sess_man, webview, is_active):
        data = sess_man._save_tab(webview, is_active)
        if is_active:
            assert data['active']
        else:
            assert 'active' not in data

    def test_no_history(self, sess_man, webview):
        data = sess_man._save_tab(webview, active=False)
        assert not data['history']

    def test_single_item(self, hist_tester):
        item = Item(url=QUrl('http://www.qutebrowser.org/'),
                    title='Test title',
                    active=True)
        expected = {
            'url': 'http://www.qutebrowser.org/',
            'title': 'Test title',
            'active': True,
            'scroll-pos': {'x': 0, 'y': 0},
            'zoom': 1.0
        }

        hist = hist_tester.get_single(item)
        assert hist == expected

    def test_original_url(self, hist_tester):
        """Test with an original-url which differs from the URL."""
        item = Item(url=QUrl('http://www.example.com/'),
                    original_url=QUrl('http://www.example.org/'),
                    title='Test title',
                    active=True)

        hist = hist_tester.get_single(item)

        assert hist['url'] == 'http://www.example.com/'
        assert hist['original-url'] == 'http://www.example.org/'

    def test_multiple_items(self, hist_tester):
        items = [
            Item(url=QUrl('http://www.qutebrowser.org/'), title='test 1'),
            Item(url=QUrl('http://www.example.com/'), title='test 2',
                 active=True),
            Item(url=QUrl('http://www.example.org/'), title='test 3'),
        ]

        expected = [
            {
                'url': 'http://www.qutebrowser.org/',
                'title': 'test 1',
            },
            {
                'url': 'http://www.example.com/',
                'title': 'test 2',
                'active': True,
                'scroll-pos': {'x': 0, 'y': 0},
                'zoom': 1.0
            },
            {
                'url': 'http://www.example.org/',
                'title': 'test 3',
            },
        ]

        hist = hist_tester.get(items)
        assert hist == expected

    @pytest.mark.parametrize('factor', [-1.0, 0.0, 1.5])
    def test_zoom(self, hist_tester, factor):
        """Test zoom."""
        items = [
            Item(url=QUrl('http://www.example.com/'), title='Test title',
                 active=True),
            Item(url=QUrl('http://www.example.com/'), title='Test title',
                 user_data={'zoom': factor}),
        ]
        hist_tester.webview.setZoomFactor(factor)
        hist = hist_tester.get(items)
        assert hist[0]['zoom'] == factor
        assert hist[1]['zoom'] == factor

    @pytest.mark.parametrize('pos_x, pos_y', [
        (0.0, 0.0), (1.0, 1.0), (0.0, 1.0), (1.0, 0.0),
    ])
    def test_scroll_current(self, hist_tester, pos_x, pos_y):
        """Test scroll position on the current URL."""
        items = [
            Item(url=QUrl('http://www.example.com/'), title='Test title',
                 active=True),
            Item(url=QUrl('http://www.example.com/'), title='Test title',
                 user_data={'scroll-pos': QPoint(pos_x, pos_y)}),
        ]
        frame = hist_tester.webview.page().mainFrame()

        text = '{}\n'.format('x' * 100) * 100
        frame.setHtml('<html><body>{}</body></html>'.format(text))
        frame.setScrollPosition(QPoint(pos_x, pos_y))

        hist = hist_tester.get(items)
        assert hist[0]['scroll-pos'] == {'x': pos_x, 'y': pos_y}
        assert hist[1]['scroll-pos'] == {'x': pos_x, 'y': pos_y}


class FakeMainWindow(QObject):

    """Helper class for the fake_main_window fixture.

    A fake MainWindow which provides a saveGeometry method.

    Needs to be a QObject so sip.isdeleted works.
    """

    def __init__(self, geometry, win_id, parent=None):
        super().__init__(parent)
        self._geometry = QByteArray(geometry)
        self.win_id = win_id

    def saveGeometry(self):
        return self._geometry


class FakeTabbedBrowser:

    """A fake tabbed-browser which contains some widgets."""

    def __init__(self, widgets):
        self._widgets = widgets

    def widgets(self):
        return self._widgets

    def currentIndex(self):
        return 1


@pytest.yield_fixture
def fake_windows(win_registry, stubs, monkeypatch, qtbot):
    """Fixture which provides two fake main windows and tabbedbrowsers."""
    win_registry.add_window(1)
    win0 = FakeMainWindow(b'fake-geometry-0', win_id=0)
    win1 = FakeMainWindow(b'fake-geometry-1', win_id=1)
    objreg.register('main-window', win0, scope='window', window=0)
    objreg.register('main-window', win1, scope='window', window=1)

    webview0 = QWebView()
    qtbot.add_widget(webview0)
    webview1 = QWebView()
    qtbot.add_widget(webview1)
    webview2 = QWebView()
    qtbot.add_widget(webview2)
    webview3 = QWebView()
    qtbot.add_widget(webview3)

    browser0 = FakeTabbedBrowser([webview0, webview1])
    browser1 = FakeTabbedBrowser([webview2, webview3])
    objreg.register('tabbed-browser', browser0, scope='window', window=0)
    objreg.register('tabbed-browser', browser1, scope='window', window=1)

    qapp = stubs.FakeQApplication(active_window=win0)
    monkeypatch.setattr('qutebrowser.misc.sessions.QApplication', qapp)

    yield browser0, browser1

    objreg.delete('main-window', scope='window', window=0)
    objreg.delete('main-window', scope='window', window=1)
    objreg.delete('tabbed-browser', scope='window', window=0)
    objreg.delete('tabbed-browser', scope='window', window=1)


class TestSaveAll:

    def test_no_history(self, sess_man):
        assert not objreg.window_registry
        data = sess_man._save_all()
        assert not data['windows']

    @webengine_refactoring_xfail
    def test_normal(self, fake_windows, sess_man):
        """Test with some windows and tabs set up."""
        data = sess_man._save_all()

        win1 = {
            'active': True,
            'geometry': b'fake-geometry-0',
            'tabs': [
                {'history': []},
                {'active': True, 'history': []},
            ],
        }
        win2 = {
            'geometry': b'fake-geometry-1',
            'tabs': [
                {'history': []},
                {'active': True, 'history': []},
            ],
        }
        expected = {'windows': [win1, win2]}
        assert data == expected

    @webengine_refactoring_xfail
    def test_no_active_window(self, sess_man, fake_windows, stubs,
                              monkeypatch):
        qapp = stubs.FakeQApplication(active_window=None)
        monkeypatch.setattr('qutebrowser.misc.sessions.QApplication', qapp)
        sess_man._save_all()


@pytest.mark.parametrize('arg, config, current, expected', [
    ('foo', None, None, 'foo'),
    (sessions.default, 'foo', None, 'foo'),
    (sessions.default, None, 'foo', 'foo'),
    (sessions.default, None, None, 'default'),
])
def test_get_session_name(config_stub, sess_man, arg, config, current,
                          expected):
    config_stub.data = {'general': {'session-default-name': config}}
    sess_man._current = current
    assert sess_man._get_session_name(arg) == expected


class TestSave:

    @pytest.yield_fixture
    def state_config(self):
        state = {'general': {}}
        objreg.register('state-config', state)
        yield state
        objreg.delete('state-config')

    @pytest.yield_fixture
    def fake_history(self, win_registry, stubs, monkeypatch, webview):
        """Fixture which provides a window with a fake history."""
        win = FakeMainWindow(b'fake-geometry-0', win_id=0)
        objreg.register('main-window', win, scope='window', window=0)
        browser = FakeTabbedBrowser([webview])

        objreg.register('tabbed-browser', browser, scope='window', window=0)
        qapp = stubs.FakeQApplication(active_window=win)
        monkeypatch.setattr('qutebrowser.misc.sessions.QApplication', qapp)

        def set_data(items):
            history = browser.widgets()[0].page().history()
            stream, _data, user_data = tabhistory.serialize(items)
            qtutils.deserialize_stream(stream, history)
            for i, data in enumerate(user_data):
                history.itemAt(i).setUserData(data)

        yield set_data

        objreg.delete('main-window', scope='window', window=0)
        objreg.delete('tabbed-browser', scope='window', window=0)

    def test_no_config_storage(self, sess_man):
        with pytest.raises(sessions.SessionError) as excinfo:
            sess_man.save('foo')
        assert str(excinfo.value) == "No data storage configured."

    def test_simple_dump(self, sess_man, tmpdir):
        session_path = tmpdir / 'foo.yml'
        name = sess_man.save(str(session_path))

        assert name == str(session_path)
        data = session_path.read_text('utf-8')
        assert data == 'windows: []\n'

    def test_update_completion_signal(self, sess_man, tmpdir, qtbot):
        session_path = tmpdir / 'foo.yml'
        with qtbot.waitSignal(sess_man.update_completion):
            sess_man.save(str(session_path))

    def test_no_state_config(self, sess_man, tmpdir, state_config):
        session_path = tmpdir / 'foo.yml'
        sess_man.save(str(session_path))
        assert 'session' not in state_config['general']

    def test_last_window_session_none(self, caplog, sess_man, tmpdir):
        session_path = tmpdir / 'foo.yml'
        with caplog.at_level(logging.ERROR):
            sess_man.save(str(session_path), last_window=True)

        assert len(caplog.records) == 1
        msg = "last_window_session is None while saving!"
        assert caplog.records[0].msg == msg
        assert not session_path.exists()

    def test_last_window_session(self, sess_man, tmpdir):
        sess_man.save_last_window_session()
        session_path = tmpdir / 'foo.yml'
        sess_man.save(str(session_path), last_window=True)
        data = session_path.read_text('utf-8')
        assert data == 'windows: []\n'

    @pytest.mark.parametrize('exception', [
        OSError('foo'), UnicodeEncodeError('ascii', '', 0, 2, 'foo'),
        yaml.YAMLError('foo')])
    def test_fake_exception(self, mocker, sess_man, tmpdir, exception):
        mocker.patch('qutebrowser.misc.sessions.yaml.dump',
                     side_effect=exception)

        with pytest.raises(sessions.SessionError) as excinfo:
            sess_man.save(str(tmpdir / 'foo.yml'))

        assert str(excinfo.value) == str(exception)
        assert not tmpdir.listdir()

    def test_directory(self, sess_man, tmpdir):
        """Test with a directory given as session file."""
        with pytest.raises(sessions.SessionError) as excinfo:
            sess_man.save(str(tmpdir))

        assert str(excinfo.value) in ["Filename refers to a directory",
                                      "Commit failed!"]
        assert not tmpdir.listdir()

    def test_load_next_time(self, tmpdir, state_config, sess_man):
        session_path = tmpdir / 'foo.yml'
        sess_man.save(str(session_path), load_next_time=True)
        assert state_config['general']['session'] == str(session_path)

    @webengine_refactoring_xfail
    def test_utf_8_valid(self, tmpdir, sess_man, fake_history):
        """Make sure data containing valid UTF8 gets saved correctly."""
        session_path = tmpdir / 'foo.yml'
        fake_history([Item(QUrl('http://www.qutebrowser.org/'), 'foo☃bar',
                           active=True)])

        sess_man.save(str(session_path))

        data = session_path.read_text('utf-8')
        assert 'title: foo☃bar' in data

    @webengine_refactoring_xfail
    def test_utf_8_invalid(self, tmpdir, sess_man, fake_history):
        """Make sure data containing invalid UTF8 raises SessionError."""
        session_path = tmpdir / 'foo.yml'
        fake_history([Item(QUrl('http://www.qutebrowser.org/'), '\ud800',
                           active=True)])

        try:
            sess_man.save(str(session_path))
        except sessions.SessionError:
            # This seems to happen on some systems only?!
            pass
        else:
            data = session_path.read_text('utf-8')
            assert r'title: "\uD800"' in data

    def _set_data(self, browser, tab_id, items):
        """Helper function for test_long_output."""
        history = browser.widgets()[tab_id].page().history()
        stream, _data, user_data = tabhistory.serialize(items)
        qtutils.deserialize_stream(stream, history)
        for i, data in enumerate(user_data):
            history.itemAt(i).setUserData(data)

    @pytest.mark.skipif(
        os.name == 'nt', reason="Test segfaults on Windows, see "
        "https://github.com/The-Compiler/qutebrowser/issues/895")
    @webengine_refactoring_xfail
    def test_long_output(self, fake_windows, tmpdir, sess_man):
        session_path = tmpdir / 'foo.yml'

        items1 = [
            Item(QUrl('http://www.qutebrowser.org/'), 'test title 1'),
            Item(QUrl('http://www.example.org/'), 'test title 2',
                 original_url=QUrl('http://www.example.com/'), active=True),
        ]
        items2 = [
            Item(QUrl('http://www.example.com/?q=foo+bar'), 'test title 3'),
            Item(QUrl('http://www.example.com/?q=test%20foo'), 'test title 4',
                 active=True),
        ]
        items3 = []
        items4 = [
            Item(QUrl('http://www.github.com/The-Compiler/qutebrowser'),
                 'test title 5', active=True),
        ]

        self._set_data(fake_windows[0], 0, items1)
        self._set_data(fake_windows[0], 1, items2)
        self._set_data(fake_windows[1], 0, items3)
        self._set_data(fake_windows[1], 1, items4)

        expected = """
            windows:
            - active: true
              geometry: !!binary |
                ZmFrZS1nZW9tZXRyeS0w
              tabs:
              - history:
                - title: test title 1
                  url: http://www.qutebrowser.org/
                - active: true
                  original-url: http://www.example.com/
                  scroll-pos:
                    x: 0
                    y: 0
                  title: test title 2
                  url: http://www.example.org/
                  zoom: 1.0
              - active: true
                history:
                - title: test title 3
                  url: http://www.example.com/?q=foo+bar
                - active: true
                  scroll-pos:
                    x: 0
                    y: 0
                  title: test title 4
                  url: http://www.example.com/?q=test%20foo
                  zoom: 1.0
            - geometry: !!binary |
                ZmFrZS1nZW9tZXRyeS0x
              tabs:
              - history: []
              - active: true
                history:
                - active: true
                  scroll-pos:
                    x: 0
                    y: 0
                  title: test title 5
                  url: http://www.github.com/The-Compiler/qutebrowser
                  zoom: 1.0
        """

        sess_man.save(str(session_path))
        data = session_path.read_text('utf-8')
        assert data == textwrap.dedent(expected.strip('\n'))


class FakeWebView:

    """A QWebView fake which provides a "page" with a load_history method.

    Attributes:
        loaded_history: The history which has been loaded by load_history, or
                        None.
        raise_error: The exception to raise on load_history, or None.
    """

    def __init__(self):
        self.loaded_history = None
        self.raise_error = None

    def page(self):
        return self

    def load_history(self, data):
        self.loaded_history = data
        if self.raise_error is not None:
            raise self.raise_error  # pylint: disable=raising-bad-type


@pytest.fixture
def fake_webview():
    return FakeWebView()


@webengine_refactoring_xfail
class TestLoadTab:

    def test_no_history(self, sess_man, fake_webview):
        sess_man._load_tab(fake_webview, {'history': []})
        assert fake_webview.loaded_history == []

    def test_load_fail(self, sess_man, fake_webview):
        fake_webview.raise_error = ValueError
        with pytest.raises(sessions.SessionError):
            sess_man._load_tab(fake_webview, {'history': []})

    @pytest.mark.parametrize('key, val, expected', [
        ('zoom', 1.23, 1.23),
        ('scroll-pos', {'x': 23, 'y': 42}, QPoint(23, 42)),
    ])
    @pytest.mark.parametrize('in_main_data', [True, False])
    def test_user_data(self, sess_man, fake_webview, key, val, expected,
                       in_main_data):

        item = {'url': 'http://www.example.com/', 'title': 'foo'}

        if in_main_data:
            # This information got saved in the main data instead of saving it
            # per item - make sure the old format can still be read
            # https://github.com/The-Compiler/qutebrowser/issues/728
            d = {'history': [item], key: val}
        else:
            item[key] = val
            d = {'history': [item]}

        sess_man._load_tab(fake_webview, d)
        assert len(fake_webview.loaded_history) == 1
        assert fake_webview.loaded_history[0].user_data[key] == expected

    @pytest.mark.parametrize('original_url', ['http://example.org/', None])
    def test_urls(self, sess_man, fake_webview, original_url):
        url = 'http://www.example.com/'
        item = {'url': url, 'title': 'foo'}

        if original_url is None:
            expected = QUrl(url)
        else:
            item['original-url'] = original_url
            expected = QUrl(original_url)

        d = {'history': [item]}

        sess_man._load_tab(fake_webview, d)
        assert len(fake_webview.loaded_history) == 1
        loaded_item = fake_webview.loaded_history[0]
        assert loaded_item.url == QUrl(url)
        assert loaded_item.original_url == expected


class TestDelete:

    def test_existing(self, sess_man, tmpdir):
        sess = tmpdir / 'foo.yml'
        sess.ensure()
        sess_man.delete(str(sess))
        assert not tmpdir.listdir()

    def test_update_completion_signal(self, sess_man, qtbot, tmpdir):
        sess = tmpdir / 'foo.yml'
        sess.ensure()

        with qtbot.waitSignal(sess_man.update_completion):
            sess_man.delete(str(sess))

    def test_not_existing(self, sess_man, qtbot, tmpdir):
        sess = tmpdir / 'foo.yml'

        with pytest.raises(sessions.SessionError):
            sess_man.delete(str(sess))


class TestListSessions:

    def test_no_base_path(self, sess_man):
        assert not sess_man.list_sessions()

    def test_no_sessions(self, tmpdir):
        sess_man = sessions.SessionManager(str(tmpdir))
        assert not sess_man.list_sessions()

    def test_with_sessions(self, tmpdir):
        (tmpdir / 'foo.yml').ensure()
        (tmpdir / 'bar.yml').ensure()
        sess_man = sessions.SessionManager(str(tmpdir))
        assert sorted(sess_man.list_sessions()) == ['bar', 'foo']

    def test_with_other_files(self, tmpdir):
        (tmpdir / 'foo.yml').ensure()
        (tmpdir / 'bar.html').ensure()
        sess_man = sessions.SessionManager(str(tmpdir))
        assert sess_man.list_sessions() == ['foo']


class TestSessionSave:

    @webengine_refactoring_xfail
    def test_normal_save(self, sess_man, tmpdir, fake_windows):
        sess_file = tmpdir / 'foo.yml'
        sess_man.session_save(0, str(sess_file), quiet=True)
        assert sess_file.read_text('utf-8').startswith('windows:')

    def test_internal_without_force(self, tmpdir):
        sess_man = sessions.SessionManager(str(tmpdir))
        with pytest.raises(cmdexc.CommandError) as excinfo:
            sess_man.session_save(0, '_foo')

        expected_text = ("_foo is an internal session, use --force to "
                         "save anyways.")
        assert str(excinfo.value) == expected_text
        assert not (tmpdir / '_foo.yml').exists()

    @webengine_refactoring_xfail
    def test_internal_with_force(self, tmpdir, fake_windows):
        sess_man = sessions.SessionManager(str(tmpdir))
        sess_man.session_save(0, '_foo', force=True, quiet=True)
        assert (tmpdir / '_foo.yml').exists()

    def test_current_unset(self, tmpdir):
        sess_man = sessions.SessionManager(str(tmpdir))

        with pytest.raises(cmdexc.CommandError) as excinfo:
            sess_man.session_save(0, current=True)

        assert str(excinfo.value) == "No session loaded currently!"

    @webengine_refactoring_xfail
    def test_current_set(self, tmpdir, fake_windows):
        sess_man = sessions.SessionManager(str(tmpdir))
        sess_man._current = 'foo'
        sess_man.session_save(0, current=True, quiet=True)
        assert (tmpdir / 'foo.yml').exists()

    def test_saving_error(self, sess_man, tmpdir):
        with pytest.raises(cmdexc.CommandError) as excinfo:
            sess_man.session_save(0, str(tmpdir))

        assert str(excinfo.value).startswith('Error while saving session: ')

    @webengine_refactoring_xfail
    def test_message(self, sess_man, tmpdir, message_mock, fake_windows):
        message_mock.patch('qutebrowser.misc.sessions.message')
        sess_path = str(tmpdir / 'foo.yml')
        sess_man.session_save(0, sess_path)
        expected_text = 'Saved session {}.'.format(sess_path)
        assert message_mock.getmsg(immediate=True).text == expected_text

    @webengine_refactoring_xfail
    def test_message_quiet(self, sess_man, tmpdir, message_mock, fake_windows):
        message_mock.patch('qutebrowser.misc.sessions.message')
        sess_path = str(tmpdir / 'foo.yml')
        sess_man.session_save(0, sess_path, quiet=True)
        assert not message_mock.messages


class TestSessionDelete:

    def test_internal_without_force(self, tmpdir):
        sess_man = sessions.SessionManager(str(tmpdir))
        sess_file = tmpdir / '_foo.yml'
        sess_file.ensure()

        with pytest.raises(cmdexc.CommandError) as excinfo:
            sess_man.session_delete('_foo')

        expected_text = ("_foo is an internal session, use --force to "
                         "delete anyways.")
        assert str(excinfo.value) == expected_text
        assert sess_file.exists()

    def test_internal_with_force(self, tmpdir):
        sess_man = sessions.SessionManager(str(tmpdir))
        sess_file = tmpdir / '_foo.yml'
        sess_file.ensure()
        sess_man.session_delete('_foo', force=True)
        assert not tmpdir.listdir()

    def test_normal_delete(self, tmpdir):
        sess_man = sessions.SessionManager(str(tmpdir))
        sess_file = tmpdir / 'foo.yml'
        sess_file.ensure()
        sess_man.session_delete('foo')
        assert not tmpdir.listdir()

    def test_session_not_found(self, tmpdir):
        sess_man = sessions.SessionManager(str(tmpdir))

        with pytest.raises(cmdexc.CommandError) as excinfo:
            sess_man.session_delete('foo')

        assert str(excinfo.value) == "Session foo not found!"

    @pytest.mark.posix
    def test_deletion_error(self, caplog, tmpdir):
        sess_man = sessions.SessionManager(str(tmpdir))
        (tmpdir / 'foo.yml').ensure()
        tmpdir.chmod(0o555)  # unwritable

        with pytest.raises(cmdexc.CommandError) as excinfo:
            with caplog.at_level(logging.ERROR):
                sess_man.session_delete('foo')

        assert str(excinfo.value).startswith('Error while deleting session: ')
        assert len(caplog.records) == 1
        assert caplog.records[0].message == 'Error while deleting session!'
