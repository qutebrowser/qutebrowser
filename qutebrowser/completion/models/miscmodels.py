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

"""Misc. CompletionModels."""

from PyQt5.QtCore import Qt, QTimer

from qutebrowser.browser import webview
from qutebrowser.config import config, configdata
from qutebrowser.utils import objreg, log
from qutebrowser.commands import cmdutils
from qutebrowser.completion.models import base


class CommandCompletionModel(base.BaseCompletionModel):

    """A CompletionModel filled with all commands and descriptions."""

    # https://github.com/The-Compiler/qutebrowser/issues/545
    # pylint: disable=abstract-method

    def __init__(self, parent=None):
        super().__init__(parent)
        assert cmdutils.cmd_dict
        cmdlist = []
        for obj in set(cmdutils.cmd_dict.values()):
            if (obj.hide or (obj.debug and not objreg.get('args').debug) or
                    obj.deprecated):
                pass
            else:
                cmdlist.append((obj.name, obj.desc))
        for name, cmd in config.section('aliases').items():
            cmdlist.append((name, "Alias for '{}'".format(cmd)))
        cat = self.new_category("Commands")
        for (name, desc) in sorted(cmdlist):
            self.new_item(cat, name, desc)


class HelpCompletionModel(base.BaseCompletionModel):

    """A CompletionModel filled with help topics."""

    # https://github.com/The-Compiler/qutebrowser/issues/545
    # pylint: disable=abstract-method

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_commands()
        self._init_settings()

    def _init_commands(self):
        """Fill completion with :command entries."""
        assert cmdutils.cmd_dict
        cmdlist = []
        for obj in set(cmdutils.cmd_dict.values()):
            if (obj.hide or (obj.debug and not objreg.get('args').debug) or
                    obj.deprecated):
                pass
            else:
                cmdlist.append((':' + obj.name, obj.desc))
        cat = self.new_category("Commands")
        for (name, desc) in sorted(cmdlist):
            self.new_item(cat, name, desc)

    def _init_settings(self):
        """Fill completion with section->option entries."""
        cat = self.new_category("Settings")
        for sectname, sectdata in configdata.DATA.items():
            for optname in sectdata:
                try:
                    desc = sectdata.descriptions[optname]
                except (KeyError, AttributeError):
                    # Some stuff (especially ValueList items) don't have a
                    # description.
                    desc = ""
                else:
                    desc = desc.splitlines()[0]
                name = '{}->{}'.format(sectname, optname)
                self.new_item(cat, name, desc)


class QuickmarkCompletionModel(base.BaseCompletionModel):

    """A CompletionModel filled with all quickmarks."""

    # https://github.com/The-Compiler/qutebrowser/issues/545
    # pylint: disable=abstract-method

    def __init__(self, parent=None):
        super().__init__(parent)
        cat = self.new_category("Quickmarks")
        quickmarks = objreg.get('quickmark-manager').marks.items()
        for qm_name, qm_url in quickmarks:
            self.new_item(cat, qm_name, qm_url)


class BookmarkCompletionModel(base.BaseCompletionModel):

    """A CompletionModel filled with all bookmarks."""

    # https://github.com/The-Compiler/qutebrowser/issues/545
    # pylint: disable=abstract-method

    def __init__(self, parent=None):
        super().__init__(parent)
        cat = self.new_category("Bookmarks")
        bookmarks = objreg.get('bookmark-manager').marks.items()
        for bm_url, bm_title in bookmarks:
            self.new_item(cat, bm_url, bm_title)


class SessionCompletionModel(base.BaseCompletionModel):

    """A CompletionModel filled with session names."""

    # https://github.com/The-Compiler/qutebrowser/issues/545
    # pylint: disable=abstract-method

    def __init__(self, parent=None):
        super().__init__(parent)
        cat = self.new_category("Sessions")
        try:
            for name in objreg.get('session-manager').list_sessions():
                if not name.startswith('_'):
                    self.new_item(cat, name)
        except OSError:
            log.completion.exception("Failed to list sessions!")

class TabCompletionModel(base.BaseCompletionModel):

    """A model to complete on open tabs in the current window.

    Used for switching tab focus."""

    # https://github.com/The-Compiler/qutebrowser/issues/545
    # pylint: disable=abstract-method

    TIME_COLUMN = 0
    URL_COLUMN = 1
    TEXT_COLUMN = 2

    COLUMN_WIDTHS = (4, 40, 56)
    DUMB_SORT = Qt.DescendingOrder

    def __init__(self, parent=None):
        super().__init__(parent)

        self.columns_to_filter = [self.URL_COLUMN, self.TEXT_COLUMN]

        self._tab_cat = self.new_category("Tabs")

        # XXX: Work with multiple windows.
        from qutebrowser.mainwindow.mainwindow import get_window
        win_id = get_window(False)
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=win_id)
        for i in range(tabbed_browser.count()):
            tab = tabbed_browser.widget(i)
            tab.url_text_changed.connect(self.rebuild_cat)
            tab.shutting_down.connect(self.on_tab_close)
        tabbed_browser.new_tab.connect(self.rebuild_cat)
        self.rebuild_cat()

    def on_tab_close(self):
        QTimer.singleShot(0, self.rebuild_cat)

    def rebuild_cat(self, arg=None):
        """Rebuild completion model from current tabs.

        Very lazy method of keeping the model up to date. We could connect to
        signals for new tab, tab url/title changed, tab close, tab moved and
        make sure we handled background loads too ... but iterating over a
        few/few dozen/few hundred tabs doesn't take very long at all."""

        self._tab_cat.removeRows(0, self._tab_cat.rowCount())

        # XXX: Work with multiple windows.
        # Import this at init time() instead of import time because it causes a
        # circular import ;(
        from qutebrowser.mainwindow.mainwindow import get_window
        win_id = get_window(False)
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=win_id)
        for i in range(tabbed_browser.count()):
            tab = tabbed_browser.widget(i)
            self.new_item(self._tab_cat, str(i+1), tab.url().toDisplayString(), 
                          tabbed_browser.page_title(i))

        if type(arg) == webview.WebView:
            # Called from new_tab
            arg.url_text_changed.connect(self.rebuild_cat)
            arg.shutting_down.connect(self.on_tab_close)
