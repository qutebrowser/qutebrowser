# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from qutebrowser.config import config, configdata
from qutebrowser.utils import objreg, log
from qutebrowser.commands import cmdutils
from qutebrowser.completion.models import base


class CommandCompletionModel(base.BaseCompletionModel):

    """A CompletionModel filled with all commands and descriptions."""

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
            for optname in sectdata.keys():
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

    # pylint: disable=abstract-method

    def __init__(self, parent=None):
        super().__init__(parent)
        cat = self.new_category("Quickmarks")
        quickmarks = objreg.get('quickmark-manager').marks.items()
        for qm_name, qm_url in quickmarks:
            self.new_item(cat, qm_name, qm_url)


class BookmarkCompletionModel(base.BaseCompletionModel):

    """A CompletionModel filled with all bookmarks."""

    # pylint: disable=abstract-method

    def __init__(self, parent=None):
        super().__init__(parent)
        cat = self.new_category("Bookmarks")
        bookmarks = objreg.get('bookmark-manager').marks.items()
        for bm_url, bm_title in bookmarks:
            self.new_item(cat, bm_url, bm_title)


class SessionCompletionModel(base.BaseCompletionModel):

    """A CompletionModel filled with session names."""

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
