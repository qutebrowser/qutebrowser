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

from qutebrowser.config import config, configdata
from qutebrowser.utils import objreg, log
from qutebrowser.commands import cmdutils
from qutebrowser.completion.models import completionmodel, listcategory


def command():
    """A CompletionModel filled with non-hidden commands and descriptions."""
    model = completionmodel.CompletionModel(column_widths=(20, 60, 20))
    cmdlist = _get_cmd_completions(include_aliases=True, include_hidden=False)
    model.add_category(listcategory.ListCategory("Commands", cmdlist))
    return model


def helptopic():
    """A CompletionModel filled with help topics."""
    model = completionmodel.CompletionModel()

    cmdlist = _get_cmd_completions(include_aliases=False, include_hidden=True,
                                   prefix=':')
    settings = []
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
            settings.append((name, desc))

    model.add_category(listcategory.ListCategory("Commands", cmdlist))
    model.add_category(listcategory.ListCategory("Settings", sorted(settings)))
    return model


def quickmark():
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
                                                 delete_func=delete))
    return model


def bookmark():
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
                                                 delete_func=delete))
    return model


def session():
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


def buffer():
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


def bind(key):
    """A CompletionModel filled with all bindable commands and descriptions.

    Args:
        key: the key being bound.
    """
    model = completionmodel.CompletionModel(column_widths=(20, 60, 20))
    cmd_text = objreg.get('key-config').get_bindings_for('normal').get(key)

    if cmd_text:
        cmd_name = cmd_text.split(' ')[0]
        cmd = cmdutils.cmd_dict.get(cmd_name)
        data = [(cmd_text, cmd.desc, key)]
        model.add_category(listcategory.ListCategory("Current", data))

    cmdlist = _get_cmd_completions(include_hidden=True, include_aliases=True)
    model.add_category(listcategory.ListCategory("Commands", cmdlist))
    return model


def _get_cmd_completions(include_hidden, include_aliases, prefix=''):
    """Get a list of completions info for commands, sorted by name.

    Args:
        include_hidden: True to include commands annotated with hide=True.
        include_aliases: True to include command aliases.
        prefix: String to append to the command name.

    Return: A list of tuples of form (name, description, bindings).
    """
    assert cmdutils.cmd_dict
    cmdlist = []
    cmd_to_keys = objreg.get('key-config').get_reverse_bindings_for('normal')
    for obj in set(cmdutils.cmd_dict.values()):
        hide_debug = obj.debug and not objreg.get('args').debug
        hide_hidden = obj.hide and not include_hidden
        if not (hide_debug or hide_hidden or obj.deprecated):
            bindings = ', '.join(cmd_to_keys.get(obj.name, []))
            cmdlist.append((prefix + obj.name, obj.desc, bindings))

    if include_aliases:
        for name, cmd in config.section('aliases').items():
            bindings = ', '.join(cmd_to_keys.get(name, []))
            cmdlist.append((name, "Alias for '{}'".format(cmd), bindings))

    return sorted(cmdlist)
