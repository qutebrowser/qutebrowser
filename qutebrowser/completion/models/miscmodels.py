# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Functions that return miscellaneous completion models."""

from qutebrowser.config import configdata
from qutebrowser.utils import objreg, log
from qutebrowser.completion.models import completionmodel, listcategory, util


def command(*, info):
    """A CompletionModel filled with non-hidden commands and descriptions."""
    model = completionmodel.CompletionModel(column_widths=(20, 60, 20))
    cmdlist = util.get_cmd_completions(info, include_aliases=True,
                                       include_hidden=False)
    model.add_category(listcategory.ListCategory("Commands", cmdlist))
    return model


def helptopic(*, info):
    """A CompletionModel filled with help topics."""
    model = completionmodel.CompletionModel()

    cmdlist = util.get_cmd_completions(info, include_aliases=False,
                                       include_hidden=True, prefix=':')
    settings = ((opt.name, opt.description)
                for opt in configdata.DATA.values())

    model.add_category(listcategory.ListCategory("Commands", cmdlist))
    model.add_category(listcategory.ListCategory("Settings", settings))
    return model


def quickmark(*, info=None):  # pylint: disable=unused-argument
    """A CompletionModel filled with all quickmarks."""
    def delete(data):
        """Delete a quickmark from the completion menu."""
        name = data[0]
        quickmark_manager = objreg.get('quickmark-manager')
        log.completion.debug('Deleting quickmark {}'.format(name))
        quickmark_manager.delete(name)

    model = completionmodel.CompletionModel(column_widths=(30, 70, 0))
    marks = objreg.get('quickmark-manager').marks.items()
    model.add_category(listcategory.ListCategory('Quickmarks', marks,
                                                 delete_func=delete,
                                                 sort=False))
    return model


def bookmark(*, info=None):  # pylint: disable=unused-argument
    """A CompletionModel filled with all bookmarks."""
    def delete(data):
        """Delete a bookmark from the completion menu."""
        urlstr = data[0]
        log.completion.debug('Deleting bookmark {}'.format(urlstr))
        bookmark_manager = objreg.get('bookmark-manager')
        bookmark_manager.delete(urlstr)

    model = completionmodel.CompletionModel(column_widths=(30, 70, 0))
    marks = objreg.get('bookmark-manager').marks.items()
    model.add_category(listcategory.ListCategory('Bookmarks', marks,
                                                 delete_func=delete,
                                                 sort=False))
    return model


def session(*, info=None):  # pylint: disable=unused-argument
    """A CompletionModel filled with session names."""
    model = completionmodel.CompletionModel()
    try:
        manager = objreg.get('session-manager')
        sessions = ((name,) for name in manager.list_sessions()
                    if not name.startswith('_'))
        model.add_category(listcategory.ListCategory("Sessions", sessions))
    except OSError:
        log.completion.exception("Failed to list sessions!")
    return model


def buffer(*, info=None):  # pylint: disable=unused-argument
    """A model to complete on open tabs across all windows.

    Used for switching the buffer command.
    """
    def delete_buffer(data):
        """Close the selected tab."""
        win_id, tab_index = data[0].split('/')
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=int(win_id))
        tabbed_browser.on_tab_close_requested(int(tab_index) - 1)

    model = completionmodel.CompletionModel(column_widths=(6, 40, 54))

    for win_id in objreg.window_registry:
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=win_id)
        if tabbed_browser.shutting_down:
            continue
        tabs = []
        for idx in range(tabbed_browser.count()):
            tab = tabbed_browser.widget(idx)
            tabs.append(("{}/{}".format(win_id, idx + 1),
                         tab.url().toDisplayString(),
                         tabbed_browser.page_title(idx)))
        cat = listcategory.ListCategory("{}".format(win_id), tabs,
            delete_func=delete_buffer)
        model.add_category(cat)

    return model
