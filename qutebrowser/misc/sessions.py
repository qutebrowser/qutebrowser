# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Management of sessions - saved tabs/windows."""

import os
import os.path
import itertools
import urllib

import sip
from PyQt5.QtCore import QUrl, QObject, QPoint, QTimer
from PyQt5.QtWidgets import QApplication
import yaml

from qutebrowser.utils import (standarddir, objreg, qtutils, log, message,
                               utils)
from qutebrowser.commands import cmdexc, cmdutils
from qutebrowser.config import config, configfiles
from qutebrowser.completion.models import miscmodels
from qutebrowser.mainwindow import mainwindow


default = object()  # Sentinel value


def init(parent=None):
    """Initialize sessions.

    Args:
        parent: The parent to use for the SessionManager.
    """
    base_path = os.path.join(standarddir.data(), 'sessions')
    try:
        os.mkdir(base_path)
    except FileExistsError:
        pass

    session_manager = SessionManager(base_path, parent)
    objreg.register('session-manager', session_manager)


class SessionError(Exception):

    """Exception raised when a session failed to load/save."""


class SessionNotFoundError(SessionError):

    """Exception raised when a session to be loaded was not found."""


class TabHistoryItem:

    """A single item in the tab history.

    Attributes:
        url: The QUrl of this item.
        original_url: The QUrl of this item which was originally requested.
        title: The title as string of this item.
        active: Whether this item is the item currently navigated to.
        user_data: The user data for this item.
    """

    def __init__(self, url, title, *, original_url=None, active=False,
                 user_data=None):
        self.url = url
        if original_url is None:
            self.original_url = url
        else:
            self.original_url = original_url
        self.title = title
        self.active = active
        self.user_data = user_data

    def __repr__(self):
        return utils.get_repr(self, constructor=True, url=self.url,
                              original_url=self.original_url, title=self.title,
                              active=self.active, user_data=self.user_data)


class SessionManager(QObject):

    """Manager for sessions.

    Attributes:
        _base_path: The path to store sessions under.
        _last_window_session: The session data of the last window which was
                              closed.
        _current: The name of the currently loaded session, or None.
        did_load: Set when a session was loaded.
    """

    def __init__(self, base_path, parent=None):
        super().__init__(parent)
        self._current = None
        self._base_path = base_path
        self._last_window_session = None
        self.did_load = False

    def _get_session_path(self, name, check_exists=False):
        """Get the session path based on a session name or absolute path.

        Args:
            name: The name of the session.
            check_exists: Whether it should also be checked if the session
                          exists.
        """
        path = os.path.expanduser(name)
        if os.path.isabs(path) and ((not check_exists) or
                                    os.path.exists(path)):
            return path
        else:
            path = os.path.join(self._base_path, name + '.yml')
            if check_exists and not os.path.exists(path):
                raise SessionNotFoundError(path)
            else:
                return path

    def exists(self, name):
        """Check if a named session exists."""
        try:
            self._get_session_path(name, check_exists=True)
        except SessionNotFoundError:
            return False
        else:
            return True

    def _save_tab_item(self, tab, idx, item):
        """Save a single history item in a tab.

        Args:
            tab: The tab to save.
            idx: The index of the current history item.
            item: The history item.

        Return:
            A dict with the saved data for this item.
        """
        data = {
            'url': bytes(item.url().toEncoded()).decode('ascii'),
        }

        if item.title():
            data['title'] = item.title()
        else:
            # https://github.com/qutebrowser/qutebrowser/issues/879
            if tab.history.current_idx() == idx:
                data['title'] = tab.title()
            else:
                data['title'] = data['url']

        if item.originalUrl() != item.url():
            encoded = item.originalUrl().toEncoded()
            data['original-url'] = bytes(encoded).decode('ascii')

        if tab.history.current_idx() == idx:
            data['active'] = True

        try:
            user_data = item.userData()
        except AttributeError:
            # QtWebEngine
            user_data = None

        if tab.history.current_idx() == idx:
            pos = tab.scroller.pos_px()
            data['zoom'] = tab.zoom.factor()
            data['scroll-pos'] = {'x': pos.x(), 'y': pos.y()}
        elif user_data is not None:
            if 'zoom' in user_data:
                data['zoom'] = user_data['zoom']
            if 'scroll-pos' in user_data:
                pos = user_data['scroll-pos']
                data['scroll-pos'] = {'x': pos.x(), 'y': pos.y()}

        data['pinned'] = tab.data.pinned

        return data

    def _save_tab(self, tab, active):
        """Get a dict with data for a single tab.

        Args:
            tab: The WebView to save.
            active: Whether the tab is currently active.
        """
        data = {'history': []}
        if active:
            data['active'] = True
        for idx, item in enumerate(tab.history):
            qtutils.ensure_valid(item)
            item_data = self._save_tab_item(tab, idx, item)
            if item.url().scheme() == 'qute' and item.url().host() == 'back':
                # don't add qute://back to the session file
                if item_data.get('active', False) and data['history']:
                    # mark entry before qute://back as active
                    data['history'][-1]['active'] = True
            else:
                data['history'].append(item_data)
        return data

    def _save_all(self, *, only_window=None, with_private=False):
        """Get a dict with data for all windows/tabs."""
        data = {'windows': []}
        if only_window is not None:
            winlist = [only_window]
        else:
            winlist = objreg.window_registry

        for win_id in sorted(winlist):
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=win_id)
            main_window = objreg.get('main-window', scope='window',
                                     window=win_id)

            # We could be in the middle of destroying a window here
            if sip.isdeleted(main_window):
                continue

            if tabbed_browser.private and not with_private:
                continue

            win_data = {}
            active_window = QApplication.instance().activeWindow()
            if getattr(active_window, 'win_id', None) == win_id:
                win_data['active'] = True
            win_data['geometry'] = bytes(main_window.saveGeometry())
            win_data['tabs'] = []
            if tabbed_browser.private:
                win_data['private'] = True
            for i, tab in enumerate(tabbed_browser.widgets()):
                active = i == tabbed_browser.widget.currentIndex()
                win_data['tabs'].append(self._save_tab(tab, active))
            data['windows'].append(win_data)
        return data

    def _get_session_name(self, name):
        """Helper for save to get the name to save the session to.

        Args:
            name: The name of the session to save, or the 'default' sentinel
                  object.
        """
        if name is default:
            name = config.val.session.default_name
            if name is None:
                if self._current is not None:
                    name = self._current
                else:
                    name = 'default'
        return name

    def save(self, name, last_window=False, load_next_time=False,
             only_window=None, with_private=False):
        """Save a named session.

        Args:
            name: The name of the session to save, or the 'default' sentinel
                  object.
            last_window: If set, saves the saved self._last_window_session
                         instead of the currently open state.
            load_next_time: If set, prepares this session to be load next time.
            only_window: If set, only tabs in the specified window is saved.
            with_private: Include private windows.

        Return:
            The name of the saved session.
        """
        name = self._get_session_name(name)
        path = self._get_session_path(name)

        log.sessions.debug("Saving session {} to {}...".format(name, path))
        if last_window:
            data = self._last_window_session
            if data is None:
                log.sessions.error("last_window_session is None while saving!")
                return None
        else:
            data = self._save_all(only_window=only_window,
                                  with_private=with_private)
        log.sessions.vdebug("Saving data: {}".format(data))
        try:
            with qtutils.savefile_open(path) as f:
                utils.yaml_dump(data, f)
        except (OSError, UnicodeEncodeError, yaml.YAMLError) as e:
            raise SessionError(e)

        if load_next_time:
            configfiles.state['general']['session'] = name
        return name

    def save_autosave(self):
        """Save the autosave session."""
        try:
            self.save('_autosave')
        except SessionError as e:
            log.sessions.error("Failed to save autosave session: {}".format(e))

    def delete_autosave(self):
        """Delete the autosave session."""
        try:
            self.delete('_autosave')
        except SessionNotFoundError:
            # Exiting before the first load finished
            pass
        except SessionError as e:
            log.sessions.error("Failed to delete autosave session: {}"
                               .format(e))

    def save_last_window_session(self):
        """Temporarily save the session for the last closed window."""
        self._last_window_session = self._save_all()

    def _load_tab(self, new_tab, data):
        """Load yaml data into a newly opened tab."""
        entries = []
        lazy_load = []
        # use len(data['history'])
        # -> dropwhile empty if not session.lazy_session
        lazy_index = len(data['history'])
        gen = itertools.chain(
            itertools.takewhile(lambda _: not lazy_load,
                                enumerate(data['history'])),
            enumerate(lazy_load),
            itertools.dropwhile(lambda i: i[0] < lazy_index,
                                enumerate(data['history'])))

        for i, histentry in gen:
            user_data = {}

            if 'zoom' in data:
                # The zoom was accidentally stored in 'data' instead of per-tab
                # earlier.
                # See https://github.com/qutebrowser/qutebrowser/issues/728
                user_data['zoom'] = data['zoom']
            elif 'zoom' in histentry:
                user_data['zoom'] = histentry['zoom']

            if 'scroll-pos' in data:
                # The scroll position was accidentally stored in 'data' instead
                # of per-tab earlier.
                # See https://github.com/qutebrowser/qutebrowser/issues/728
                pos = data['scroll-pos']
                user_data['scroll-pos'] = QPoint(pos['x'], pos['y'])
            elif 'scroll-pos' in histentry:
                pos = histentry['scroll-pos']
                user_data['scroll-pos'] = QPoint(pos['x'], pos['y'])

            if 'pinned' in histentry:
                new_tab.data.pinned = histentry['pinned']

            if (config.val.session.lazy_restore and
                    histentry.get('active', False) and
                    not histentry['url'].startswith('qute://back')):
                # remove "active" mark and insert back page marked as active
                lazy_index = i + 1
                lazy_load.append({
                    'title': histentry['title'],
                    'url':
                        'qute://back#' +
                        urllib.parse.quote(histentry['title']),
                    'active': True
                })
                histentry['active'] = False

            active = histentry.get('active', False)
            url = QUrl.fromEncoded(histentry['url'].encode('ascii'))
            if 'original-url' in histentry:
                orig_url = QUrl.fromEncoded(
                    histentry['original-url'].encode('ascii'))
            else:
                orig_url = url
            entry = TabHistoryItem(url=url, original_url=orig_url,
                                   title=histentry['title'], active=active,
                                   user_data=user_data)
            entries.append(entry)
            if active:
                new_tab.title_changed.emit(histentry['title'])

        try:
            new_tab.history.load_items(entries)
        except ValueError as e:
            raise SessionError(e)

    def load(self, name, temp=False):
        """Load a named session.

        Args:
            name: The name of the session to load.
            temp: If given, don't set the current session.
        """
        path = self._get_session_path(name, check_exists=True)
        try:
            with open(path, encoding='utf-8') as f:
                data = utils.yaml_load(f)
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
            raise SessionError(e)

        log.sessions.debug("Loading session {} from {}...".format(name, path))
        for win in data['windows']:
            window = mainwindow.MainWindow(geometry=win['geometry'],
                                           private=win.get('private', None))
            window.show()
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=window.win_id)
            tab_to_focus = None
            for i, tab in enumerate(win['tabs']):
                new_tab = tabbed_browser.tabopen(background=False)
                self._load_tab(new_tab, tab)
                if tab.get('active', False):
                    tab_to_focus = i
                if new_tab.data.pinned:
                    tabbed_browser.widget.set_tab_pinned(new_tab,
                                                         new_tab.data.pinned)
            if tab_to_focus is not None:
                tabbed_browser.widget.setCurrentIndex(tab_to_focus)
            if win.get('active', False):
                QTimer.singleShot(0, tabbed_browser.widget.activateWindow)

        if data['windows']:
            self.did_load = True
        if not name.startswith('_') and not temp:
            self._current = name

    def delete(self, name):
        """Delete a session."""
        path = self._get_session_path(name, check_exists=True)
        try:
            os.remove(path)
        except OSError as e:
            raise SessionError(e)

    def list_sessions(self):
        """Get a list of all session names."""
        sessions = []
        for filename in os.listdir(self._base_path):
            base, ext = os.path.splitext(filename)
            if ext == '.yml':
                sessions.append(base)
        return sorted(sessions)

    @cmdutils.register(instance='session-manager')
    @cmdutils.argument('name', completion=miscmodels.session)
    def session_load(self, name, clear=False, temp=False, force=False,
                     delete=False):
        """Load a session.

        Args:
            name: The name of the session.
            clear: Close all existing windows.
            temp: Don't set the current session for :session-save.
            force: Force loading internal sessions (starting with an
                   underline).
            delete: Delete the saved session once it has loaded.
        """
        if name.startswith('_') and not force:
            raise cmdexc.CommandError("{} is an internal session, use --force "
                                      "to load anyways.".format(name))
        old_windows = list(objreg.window_registry.values())
        try:
            self.load(name, temp=temp)
        except SessionNotFoundError:
            raise cmdexc.CommandError("Session {} not found!".format(name))
        except SessionError as e:
            raise cmdexc.CommandError("Error while loading session: {}"
                                      .format(e))
        else:
            if clear:
                for win in old_windows:
                    win.close()
            if delete:
                try:
                    self.delete(name)
                except SessionError as e:
                    log.sessions.exception("Error while deleting session!")
                    raise cmdexc.CommandError(
                        "Error while deleting session: {}"
                        .format(e))
                else:
                    log.sessions.debug(
                        "Loaded & deleted session {}.".format(name))

    @cmdutils.register(instance='session-manager')
    @cmdutils.argument('name', completion=miscmodels.session)
    @cmdutils.argument('win_id', win_id=True)
    @cmdutils.argument('with_private', flag='p')
    def session_save(self, name: str = default, current=False, quiet=False,
                     force=False, only_active_window=False, with_private=False,
                     win_id=None):
        """Save a session.

        Args:
            name: The name of the session. If not given, the session configured
                  in session.default_name is saved.
            current: Save the current session instead of the default.
            quiet: Don't show confirmation message.
            force: Force saving internal sessions (starting with an underline).
            only_active_window: Saves only tabs of the currently active window.
            with_private: Include private windows.
        """
        if name is not default and name.startswith('_') and not force:
            raise cmdexc.CommandError("{} is an internal session, use --force "
                                      "to save anyways.".format(name))
        if current:
            if self._current is None:
                raise cmdexc.CommandError("No session loaded currently!")
            name = self._current
            assert not name.startswith('_')
        try:
            if only_active_window:
                name = self.save(name, only_window=win_id,
                                 with_private=True)
            else:
                name = self.save(name, with_private=with_private)
        except SessionError as e:
            raise cmdexc.CommandError("Error while saving session: {}"
                                      .format(e))
        else:
            if quiet:
                log.sessions.debug("Saved session {}.".format(name))
            else:
                message.info("Saved session {}.".format(name))

    @cmdutils.register(instance='session-manager')
    @cmdutils.argument('name', completion=miscmodels.session)
    def session_delete(self, name, force=False):
        """Delete a session.

        Args:
            name: The name of the session.
            force: Force deleting internal sessions (starting with an
                   underline).
        """
        if name.startswith('_') and not force:
            raise cmdexc.CommandError("{} is an internal session, use --force "
                                      "to delete anyways.".format(name))
        try:
            self.delete(name)
        except SessionNotFoundError:
            raise cmdexc.CommandError("Session {} not found!".format(name))
        except SessionError as e:
            log.sessions.exception("Error while deleting session!")
            raise cmdexc.CommandError("Error while deleting session: {}"
                                      .format(e))
        else:
            log.sessions.debug("Deleted session {}.".format(name))
