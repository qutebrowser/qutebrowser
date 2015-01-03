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

"""Manager for quickmarks.

Note we violate our general QUrl rule by storing url strings in the marks
OrderedDict. This is because we read them from a file at start and write them
to a file on shutdown, so it makes sense to keep them as strings here.
"""

import functools
import collections

from PyQt5.QtCore import pyqtSignal, QStandardPaths, QUrl, QObject

from qutebrowser.utils import message, usertypes, urlutils, standarddir
from qutebrowser.commands import cmdexc, cmdutils
from qutebrowser.config.parsers import line as lineparser


class QuickmarkManager(QObject):

    """Manager for quickmarks.

    Attributes:
        marks: An OrderedDict of all quickmarks.
        _linecp: The LineConfigParser used for the quickmarks.
    """

    changed = pyqtSignal()

    def __init__(self, parent=None):
        """Initialize and read quickmarks."""
        super().__init__(parent)

        self.marks = collections.OrderedDict()

        confdir = standarddir.get(QStandardPaths.ConfigLocation)
        self._linecp = lineparser.LineConfigParser(confdir, 'quickmarks')
        for line in self._linecp:
            try:
                key, url = line.rsplit(maxsplit=1)
            except ValueError:
                message.error(0, "Invalid quickmark '{}'".format(line))
            else:
                self.marks[key] = url

    def save(self):
        """Save the quickmarks to disk."""
        self._linecp.data = [' '.join(tpl) for tpl in self.marks.items()]
        self._linecp.save()

    def prompt_save(self, win_id, url):
        """Prompt for a new quickmark name to be added and add it.

        Args:
            win_id: The current window ID.
            url: The quickmark url as a QUrl.
        """
        if not url.isValid():
            urlutils.invalid_url_error(win_id, url, "save quickmark")
            return
        urlstr = url.toString(QUrl.RemovePassword | QUrl.FullyEncoded)
        message.ask_async(
            win_id, "Add quickmark:", usertypes.PromptMode.text,
            functools.partial(self.quickmark_add, win_id, urlstr))

    @cmdutils.register(instance='quickmark-manager')
    def quickmark_add(self, win_id: {'special': 'win_id'}, url, name):
        """Add a new quickmark.

        Args:
            win_id: The window ID to display the errors in.
            url: The url to add as quickmark.
            name: The name for the new quickmark.
        """
        # We don't raise cmdexc.CommandError here as this can be called async
        # via prompt_save.
        if not name:
            message.error(win_id, "Can't set mark with empty name!")
            return
        if not url:
            message.error(win_id, "Can't set mark with empty URL!")
            return

        def set_mark():
            """Really set the quickmark."""
            self.marks[name] = url
            self.changed.emit()

        if name in self.marks:
            message.confirm_async(
                win_id, "Override existing quickmark?", set_mark, default=True)
        else:
            set_mark()

    @cmdutils.register(instance='quickmark-manager', maxsplit=0,
                       completion=[usertypes.Completion.quickmark_by_name])
    def quickmark_del(self, name):
        """Delete a quickmark.

        Args:
            name: The name of the quickmark to delete.
        """
        try:
            del self.marks[name]
        except KeyError:
            raise cmdexc.CommandError("Quickmark '{}' not found!".format(name))
        else:
            self.changed.emit()

    def get(self, name):
        """Get the URL of the quickmark named name as a QUrl."""
        if name not in self.marks:
            raise cmdexc.CommandError(
                "Quickmark '{}' does not exist!".format(name))
        urlstr = self.marks[name]
        try:
            url = urlutils.fuzzy_url(urlstr)
        except urlutils.FuzzyUrlError:
            raise cmdexc.CommandError(
                "Invalid URL for quickmark {}: {} ({})".format(
                    name, urlstr, url.errorString()))
        return url
