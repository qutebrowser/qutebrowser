# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Tests for qutebrowser.misc.sessions."""

import logging

import pytest
import yaml
from PyQt5.QtCore import QByteArray, QObject, QPoint, QUrl

from qutebrowser.browser.browsertab import AbstractHistoryItem as Item
from qutebrowser.browser.webkit import tabhistory
from qutebrowser.misc import sessions
from qutebrowser.utils import objreg, qtutils

QWebView = pytest.importorskip('PyQt5.QtWebKitWidgets').QWebView

pytestmark = pytest.mark.qt_log_ignore('QIODevice::read.*: device not open')

webengine_refactoring_xfail = pytest.mark.xfail(
    True, reason='Broke during QtWebEngine refactoring, will be fixed after '
                 'sessions are refactored too.')


@pytest.fixture
def sess_man(tmp_path):
    """Fixture providing a SessionManager."""
    return sessions.SessionManager(base_path=str(tmp_path))


class TestInit:

    @pytest.fixture(autouse=True)
    def cleanup(self, monkeypatch):
        monkeypatch.setattr(sessions, 'session_manager', None)
        yield
        try:
            objreg.delete('session-manager')
        except KeyError:
            pass

    @pytest.mark.parametrize('create_dir', [True, False])
    def test_with_standarddir(self, tmp_path, monkeypatch, create_dir):
        monkeypatch.setattr(sessions.standarddir, 'data',
                            lambda: str(tmp_path))
        session_dir = tmp_path / 'sessions'
        if create_dir:
            session_dir.mkdir()

        sessions.init()

        assert session_dir.exists()
        assert sessions.session_manager._base_path == str(session_dir)


def test_did_not_load(sess_man):
    assert not sess_man.did_load


class TestExists:

    @pytest.mark.parametrize('absolute', [True, False])
    def test_existent(self, tmp_path, absolute):
        session_dir = tmp_path / 'sessions'
        abs_session = tmp_path / 'foo.yml'
        rel_session = session_dir / 'foo.yml'

        session_dir.mkdir()
        abs_session.touch()
        rel_session.touch()

        man = sessions.SessionManager(str(session_dir))

        if absolute:
            name = str(abs_session)
        else:
            name = 'foo'

        assert man.exists(name)

    @pytest.mark.parametrize('absolute', [True, False])
    def test_inexistent(self, tmp_path, absolute):
        man = sessions.SessionManager(str(tmp_path))

        if absolute:
            name = str(tmp_path / 'foo')
        else:
            name = 'foo'

        assert not man.exists(name)


@webengine_refactoring_xfail
class TestSaveTab:

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


@pytest.fixture
def fake_window(tabbed_browser_stubs):
    """Fixture which provides a fake main windows with a tabbedbrowser."""
    win0 = FakeMainWindow(b'fake-geometry-0', win_id=0)
    objreg.register('main-window', win0, scope='window', window=0)
    yield
    objreg.delete('main-window', scope='window', window=0)


class TestSaveAll:

    def test_no_history(self, sess_man):
        # FIXME can this ever actually happen?
        assert not objreg.window_registry
        data = sess_man._save_all()
        assert not data['windows']

    @webengine_refactoring_xfail
    def test_no_active_window(self, sess_man, fake_window, stubs,
                              monkeypatch):
        qapp = stubs.FakeQApplication(active_window=None)
        monkeypatch.setattr(sessions, 'QApplication', qapp)
        sess_man._save_all()


@pytest.mark.parametrize('arg, config, current, expected', [
    ('foo', None, None, 'foo'),
    (sessions.default, 'foo', None, 'foo'),
    (sessions.default, None, 'foo', 'foo'),
    (sessions.default, None, None, 'default'),
])
def test_get_session_name(config_stub, sess_man, arg, config, current,
                          expected):
    config_stub.val.session.default_name = config
    sess_man.current = current
    assert sess_man._get_session_name(arg) == expected


class TestSave:

    @pytest.fixture
    def fake_history(self, stubs, tabbed_browser_stubs, monkeypatch, webview):
        """Fixture which provides a window with a fake history."""
        win = FakeMainWindow(b'fake-geometry-0', win_id=0)
        objreg.register('main-window', win, scope='window', window=0)

        browser = tabbed_browser_stubs[0]
        qapp = stubs.FakeQApplication(active_window=win)
        monkeypatch.setattr(sessions, 'QApplication', qapp)

        def set_data(items):
            history = browser.widgets()[0].page().history()
            stream, _data, user_data = tabhistory.serialize(items)
            qtutils.deserialize_stream(stream, history)
            for i, data in enumerate(user_data):
                history.itemAt(i).setUserData(data)

        yield set_data

        objreg.delete('main-window', scope='window', window=0)
        objreg.delete('tabbed-browser', scope='window', window=0)

    def test_no_state_config(self, sess_man, tmp_path, state_config):
        session_path = tmp_path / 'foo.yml'
        sess_man.save(str(session_path))
        assert 'session' not in state_config['general']

    def test_last_window_session_none(self, caplog, sess_man, tmp_path):
        session_path = tmp_path / 'foo.yml'
        with caplog.at_level(logging.ERROR):
            sess_man.save(str(session_path), last_window=True)

        msg = "last_window_session is None while saving!"
        assert caplog.messages == [msg]
        assert not session_path.exists()

    def test_last_window_session(self, sess_man, tmp_path):
        sess_man.save_last_window_session()
        session_path = tmp_path / 'foo.yml'
        sess_man.save(str(session_path), last_window=True)
        data = session_path.read_text('utf-8')
        assert data == 'windows: []\n'

    @pytest.mark.parametrize('exception', [
        OSError('foo'), UnicodeEncodeError('ascii', '', 0, 2, 'foo'),
        yaml.YAMLError('foo')])
    def test_fake_exception(self, mocker, sess_man, tmp_path, exception):
        mocker.patch('qutebrowser.misc.sessions.yaml.dump',
                     side_effect=exception)

        with pytest.raises(sessions.SessionError, match=str(exception)):
            sess_man.save(str(tmp_path / 'foo.yml'))

        assert not list(tmp_path.glob('*'))

    def test_load_next_time(self, tmp_path, state_config, sess_man):
        session_path = tmp_path / 'foo.yml'
        sess_man.save(str(session_path), load_next_time=True)
        assert state_config['general']['session'] == str(session_path)

    @webengine_refactoring_xfail
    def test_utf_8_invalid(self, tmp_path, sess_man, fake_history):
        """Make sure data containing invalid UTF8 raises SessionError."""
        session_path = tmp_path / 'foo.yml'
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
            # https://github.com/qutebrowser/qutebrowser/issues/728
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


class TestListSessions:

    def test_no_sessions(self, tmp_path):
        sess_man = sessions.SessionManager(str(tmp_path))
        assert not sess_man.list_sessions()

    def test_with_sessions(self, tmp_path):
        (tmp_path / 'foo.yml').touch()
        (tmp_path / 'bar.yml').touch()
        sess_man = sessions.SessionManager(str(tmp_path))
        assert sess_man.list_sessions() == ['bar', 'foo']

    def test_with_other_files(self, tmp_path):
        (tmp_path / 'foo.yml').touch()
        (tmp_path / 'bar.html').touch()
        sess_man = sessions.SessionManager(str(tmp_path))
        assert sess_man.list_sessions() == ['foo']
