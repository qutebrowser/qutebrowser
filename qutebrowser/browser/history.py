# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Simple history which gets written to disk."""

import time

from PyQt5.QtCore import pyqtSlot, QUrl

from qutebrowser.commands import cmdutils
from qutebrowser.utils import utils, objreg, log, qtutils, usertypes, message
from qutebrowser.misc import objects, sql


class Entry:

    """A single entry in the web history.

    Attributes:
        atime: The time the page was accessed.
        url: The URL which was accessed as QUrl.
        redirect: If True, don't show this entry in completion
    """

    def __init__(self, atime, url, title, redirect=False):
        self.atime = float(atime)
        self.url = url
        self.title = title
        self.redirect = redirect
        qtutils.ensure_valid(url)

    def __repr__(self):
        return utils.get_repr(self, constructor=True, atime=self.atime,
                              url=self.url_str(), title=self.title,
                              redirect=self.redirect)

    def __str__(self):
        atime = str(int(self.atime))
        if self.redirect:
            atime += '-r'  # redirect flag
        elems = [atime, self.url_str()]
        if self.title:
            elems.append(self.title)
        return ' '.join(elems)

    def __eq__(self, other):
        return (self.atime == other.atime and
                self.title == other.title and
                self.url == other.url and
                self.redirect == other.redirect)

    def url_str(self):
        """Get the URL as a lossless string."""
        return self.url.toString(QUrl.FullyEncoded | QUrl.RemovePassword)


class WebHistory(sql.SqlTable):

    """The global history of visited pages."""

    def __init__(self, parent=None):
        super().__init__("History", ['url', 'title', 'atime', 'redirect'],
                         parent=parent)

    def __repr__(self):
        return utils.get_repr(self, length=len(self))

    def __contains__(self, url):
        return self.contains('url', url)

    def _add_entry(self, entry):
        """Add an entry to the in-memory database."""
        self.insert([entry.url_str(), entry.title, int(entry.atime),
                     entry.redirect])

    def get_recent(self):
        """Get the most recent history entries."""
        return self.select(sort_by='atime', sort_order='desc', limit=100)

    def entries_between(self, earliest, latest):
        """Iterate non-redirect, non-qute entries between two timestamps.

        Args:
            earliest: Omit timestamps earlier than this.
            latest: Omit timestamps later than this.
        """
        result = sql.run_query('SELECT * FROM History '
                               'where not redirect '
                               'and not url like "qute://%" '
                               'and atime > {} '
                               'and atime <= {} '
                               'ORDER BY atime desc'
                               .format(earliest, latest))
        while result.next():
            rec = result.record()
            yield self.Entry(*[rec.value(i) for i in range(rec.count())])

    def entries_before(self, latest, limit, offset):
        """Iterate non-redirect, non-qute entries occuring before a timestamp.

        Args:
            latest: Omit timestamps more recent than this.
            limit: Max number of entries to include.
            offset: Number of entries to skip.
        """
        result = sql.run_query('SELECT * FROM History '
                               'where not redirect '
                               'and not url like "qute://%" '
                               'and atime <= {} '
                               'ORDER BY atime desc '
                               'limit {} offset {}'
                               .format(latest, limit, offset))
        while result.next():
            rec = result.record()
            yield self.Entry(*[rec.value(i) for i in range(rec.count())])

    @cmdutils.register(name='history-clear', instance='web-history')
    def clear(self, force=False):
        """Clear all browsing history.

        Note this only clears the global history
        (e.g. `~/.local/share/qutebrowser/history` on Linux) but not cookies,
        the back/forward history of a tab, cache or other persistent data.

        Args:
            force: Don't ask for confirmation.
        """
        if force:
            self._do_clear()
        else:
            message.confirm_async(self._do_clear, title="Clear all browsing "
                                "history?")

    def _do_clear(self):
        self.delete_all()

    @pyqtSlot(QUrl, QUrl, str)
    def add_from_tab(self, url, requested_url, title):
        """Add a new history entry as slot, called from a BrowserTab."""
        if url.scheme() == 'data' or requested_url.scheme() == 'data':
            return
        if url.isEmpty():
            # things set via setHtml
            return

        no_formatting = QUrl.UrlFormattingOption(0)
        if (requested_url.isValid() and
                not requested_url.matches(url, no_formatting)):
            # If the url of the page is different than the url of the link
            # originally clicked, save them both.
            self.add_url(requested_url, title, redirect=True)
        self.add_url(url, title)

    def add_url(self, url, title="", *, redirect=False, atime=None):
        """Called via add_from_tab when a URL should be added to the history.

        Args:
            url: A url (as QUrl) to add to the history.
            redirect: Whether the entry was redirected to another URL
                      (hidden in completion)
            atime: Override the atime used to add the entry
        """
        if not url.isValid():  # pragma: no cover
            # the no cover pragma is a WORKAROUND for this not being covered in
            # old Qt versions.
            log.misc.warning("Ignoring invalid URL being added to history")
            return

        if atime is None:
            atime = time.time()
        entry = Entry(atime, url, title, redirect=redirect)
        self._add_entry(entry)

    def _parse_entry(self, line):
        """Parse a history line like '12345 http://example.com title'."""
        data = line.split(maxsplit=2)
        if len(data) == 2:
            atime, url = data
            title = ""
        elif len(data) == 3:
            atime, url, title = data
        else:
            raise ValueError("2 or 3 fields expected")

        url = QUrl(url)
        if not url.isValid():
            raise ValueError("Invalid URL: {}".format(url.errorString()))

        # https://github.com/qutebrowser/qutebrowser/issues/670
        atime = atime.lstrip('\0')

        if '-' in atime:
            atime, flags = atime.split('-')
        else:
            flags = ''

        if not set(flags).issubset('r'):
            raise ValueError("Invalid flags {!r}".format(flags))

        redirect = 'r' in flags

        return (url, title, float(atime), bool(redirect))

    def read(self, path):
        """Import a text file into the sql database."""
        with open(path, 'r', encoding='utf-8') as f:
            rows = []
            for (i, line) in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = self._parse_entry(line.strip())
                    rows.append(row)
                except ValueError:
                    raise Exception('Failed to parse line #{} of {}: "{}"'
                                    .format(i, path, line))
        self.insert_batch(rows)


def init(parent=None):
    """Initialize the web history.

    Args:
        parent: The parent to use for WebHistory.
    """
    history = WebHistory(parent=parent)
    objreg.register('web-history', history)

    if objects.backend == usertypes.Backend.QtWebKit:
        from qutebrowser.browser.webkit import webkithistory
        webkithistory.init(history)
