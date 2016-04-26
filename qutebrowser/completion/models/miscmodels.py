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

from PyQt5.QtCore import Qt, QTimer, pyqtSlot

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

    """A model to complete on open tabs across all windows.

    Used for switching the buffer command."""

    # https://github.com/The-Compiler/qutebrowser/issues/545
    # pylint: disable=abstract-method

    #IDX_COLUMN = 0
    URL_COLUMN = 1
    TEXT_COLUMN = 2

    COLUMN_WIDTHS = (6, 40, 54)
    DUMB_SORT = Qt.DescendingOrder

    def __init__(self, parent=None):
        super().__init__(parent)

        self.columns_to_filter = [self.URL_COLUMN, self.TEXT_COLUMN]

        for win_id in objreg.window_registry:
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=win_id)
            for i in range(tabbed_browser.count()):
                tab = tabbed_browser.widget(i)
                tab.url_text_changed.connect(self.rebuild)
                tab.shutting_down.connect(self.delayed_rebuild)
            tabbed_browser.new_tab.connect(self.on_new_tab)
        objreg.get("app").new_window.connect(self.on_new_window)
        self.rebuild()

    def on_new_window(self, window):
        """Add hooks to new windows."""
        window.tabbed_browser.new_tab.connect(self.on_new_tab)

    @pyqtSlot(webview.WebView)
    def on_new_tab(self, tab):
        """Add hooks to new tabs."""
        tab.url_text_changed.connect(self.rebuild)
        tab.shutting_down.connect(self.delayed_rebuild)
        self.rebuild()

    @pyqtSlot()
    def delayed_rebuild(self):
        """Fire a rebuild indirectly so widgets get a chance to update."""
        QTimer.singleShot(0, self.rebuild)

    @pyqtSlot()
    def rebuild(self):
        """Rebuild completion model from current tabs.

        Very lazy method of keeping the model up to date. We could connect to
        signals for new tab, tab url/title changed, tab close, tab moved and
        make sure we handled background loads too ... but iterating over a
        few/few dozen/few hundred tabs doesn't take very long at all.
        """
        self.removeRows(0, self.rowCount())
        for win_id in objreg.window_registry:
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=win_id)
            if tabbed_browser.shutting_down:
                continue
            c = self.new_category("{}".format(win_id))
            for i in range(tabbed_browser.count()):
                tab = tabbed_browser.widget(i)
                self.new_item(c, "{}/{}".format(win_id, i+1),
                              tab.url().toDisplayString(),
                              tabbed_browser.page_title(i))
