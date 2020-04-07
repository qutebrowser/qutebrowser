# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# Copyright 2015-2018 Antoni Boucher <bouanto@zoho.com>
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

"""Managers for bookmarks and quickmarks.

Note we violate our general QUrl rule by storing url strings in the marks
OrderedDict. This is because we read them from a file at start and write them
to a file on shutdown, so it makes sense to keep them as strings here.
"""

import os
import os.path
import html
import functools
import collections
import typing

from PyQt5.QtCore import pyqtSignal, QUrl, QObject

from qutebrowser.utils import (message, usertypes, qtutils, urlutils,
                               standarddir, objreg, log)
from qutebrowser.api import cmdutils
from qutebrowser.misc import lineparser


class Error(Exception):

    """Base class for all errors in this module."""


class InvalidUrlError(Error):

    """Exception emitted when a URL is invalid."""


class DoesNotExistError(Error):

    """Exception emitted when a given URL does not exist."""


class AlreadyExistsError(Error):

    """Exception emitted when a given URL does already exist."""


class UrlMarkManager(QObject):

    """Base class for BookmarkManager and QuickmarkManager.

    Attributes:
        marks: An OrderedDict of all quickmarks/bookmarks.
        _lineparser: The LineParser used for the marks

    Signals:
        changed: Emitted when anything changed.
    """

    changed = pyqtSignal()

    def __init__(self, parent=None):
        """Initialize and read quickmarks."""
        super().__init__(parent)

        self.marks = collections.OrderedDict(
        )  # type: typing.MutableMapping[str, str]

        self._init_lineparser()
        for line in self._lineparser:
            if not line.strip() or line.startswith('#'):
                # Ignore empty or whitespace-only lines and comments.
                continue
            self._parse_line(line)
        self._init_savemanager(objreg.get('save-manager'))

    def _init_lineparser(self):
        raise NotImplementedError

    def _parse_line(self, line):
        raise NotImplementedError

    def _init_savemanager(self, _save_manager):
        raise NotImplementedError

    def save(self):
        """Save the marks to disk."""
        self._lineparser.data = [' '.join(tpl) for tpl in self.marks.items()]
        self._lineparser.save()

    def delete(self, key):
        """Delete a quickmark/bookmark.

        Args:
            key: The key to delete (name for quickmarks, URL for bookmarks.)
        """
        del self.marks[key]
        self.changed.emit()


class QuickmarkManager(UrlMarkManager):

    """Manager for quickmarks.

    The primary key for quickmarks is their *name*, this means:

        - self.marks maps names to URLs.
        - changed gets emitted with the name as first argument and the URL as
          second argument.
    """

    def _init_lineparser(self):
        self._lineparser = lineparser.LineParser(
            standarddir.config(), 'quickmarks', parent=self)

    def _init_savemanager(self, save_manager):
        filename = os.path.join(standarddir.config(), 'quickmarks')
        save_manager.add_saveable('quickmark-manager', self.save, self.changed,
                                  filename=filename)

    def _parse_line(self, line):
        try:
            key, url = line.rsplit(maxsplit=1)
        except ValueError:
            message.error("Invalid quickmark '{}'".format(line))
        else:
            self.marks[key] = url

    def prompt_save(self, url):
        """Prompt for a new quickmark name to be added and add it.

        Args:
            url: The quickmark url as a QUrl.
        """
        if not url.isValid():
            urlutils.invalid_url_error(url, "save quickmark")
            return
        urlstr = url.toString(QUrl.RemovePassword | QUrl.FullyEncoded)
        message.ask_async(
            "Add quickmark:", usertypes.PromptMode.text,
            functools.partial(self.quickmark_add, urlstr),
            text="Please enter a quickmark name for<br/><b>{}</b>".format(
                html.escape(url.toDisplayString())), url=urlstr)

    @cmdutils.register(instance='quickmark-manager')
    def quickmark_add(self, url, name):
        """Add a new quickmark.

        You can view all saved quickmarks on the
        link:qute://bookmarks[bookmarks page].

        Args:
            url: The url to add as quickmark.
            name: The name for the new quickmark.
        """
        # We don't raise cmdutils.CommandError here as this can be called async
        # via prompt_save.
        if not name:
            message.error("Can't set mark with empty name!")
            return
        if not url:
            message.error("Can't set mark with empty URL!")
            return

        def set_mark():
            """Really set the quickmark."""
            self.marks[name] = url
            self.changed.emit()
            log.misc.debug("Added quickmark {} for {}".format(name, url))

        if name in self.marks:
            message.confirm_async(
                title="Override existing quickmark?",
                yes_action=set_mark, default=True, url=url)
        else:
            set_mark()

    def get_by_qurl(self, url):
        """Look up a quickmark by QUrl, returning its name.

        Takes O(n) time, where n is the number of quickmarks.
        Use a name instead where possible.
        """
        qtutils.ensure_valid(url)
        urlstr = url.toString(QUrl.RemovePassword | QUrl.FullyEncoded)

        try:
            index = list(self.marks.values()).index(urlstr)
            key = list(self.marks.keys())[index]
        except ValueError:
            raise DoesNotExistError(
                "Quickmark for '{}' not found!".format(urlstr))
        return key

    def get(self, name):
        """Get the URL of the quickmark named name as a QUrl."""
        if name not in self.marks:
            raise DoesNotExistError(
                "Quickmark '{}' does not exist!".format(name))
        urlstr = self.marks[name]
        try:
            url = urlutils.fuzzy_url(urlstr, do_search=False)
        except urlutils.InvalidUrlError as e:
            raise InvalidUrlError(
                "Invalid URL for quickmark {}: {}".format(name, str(e)))
        return url


class BookmarkManager(UrlMarkManager):

    """Manager for bookmarks.

    The primary key for bookmarks is their *url*, this means:

        - self.marks maps URLs to titles.
        - changed gets emitted with the URL as first argument and the title as
          second argument.
    """

    def _init_lineparser(self):
        bookmarks_directory = os.path.join(standarddir.config(), 'bookmarks')
        os.makedirs(bookmarks_directory, exist_ok=True)

        bookmarks_subdir = os.path.join('bookmarks', 'urls')
        self._lineparser = lineparser.LineParser(
            standarddir.config(), bookmarks_subdir, parent=self)

    def _init_savemanager(self, save_manager):
        filename = os.path.join(standarddir.config(), 'bookmarks', 'urls')
        save_manager.add_saveable('bookmark-manager', self.save, self.changed,
                                  filename=filename)

    def _parse_line(self, line):
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            self.marks[parts[0]] = parts[1]
        elif len(parts) == 1:
            self.marks[parts[0]] = ''

    def add(self, url, title, *, toggle=False):
        """Add a new bookmark.

        Args:
            url: The url to add as bookmark.
            title: The title for the new bookmark.
            toggle: remove the bookmark instead of raising an error if it
                    already exists.

        Return:
            True if the bookmark was added, and False if it was
            removed (only possible if toggle is True).
        """
        if not url.isValid():
            errstr = urlutils.get_errstring(url)
            raise InvalidUrlError(errstr)

        urlstr = url.toString(QUrl.RemovePassword | QUrl.FullyEncoded)

        if urlstr in self.marks:
            if toggle:
                self.delete(urlstr)
                return False
            else:
                raise AlreadyExistsError("Bookmark already exists!")
        else:
            self.marks[urlstr] = title
            self.changed.emit()
            return True
