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

import os
import time

from PyQt5.QtCore import pyqtSlot, QUrl, QTimer

from qutebrowser.commands import cmdutils, cmdexc
from qutebrowser.utils import (utils, objreg, log, usertypes, message,
                               debug, standarddir, qtutils)
from qutebrowser.misc import objects, sql


# increment to indicate that HistoryCompletion must be regenerated
_USER_VERSION = 1


class CompletionHistory(sql.SqlTable):

    """History which only has the newest entry for each URL."""

    def __init__(self, parent=None):
        super().__init__("CompletionHistory", ['url', 'title', 'last_atime'],
                         constraints={'url': 'PRIMARY KEY',
                                      'title': 'NOT NULL',
                                      'last_atime': 'NOT NULL'},
                         parent=parent)
        self.create_index('CompletionHistoryAtimeIndex', 'last_atime')


class WebHistory(sql.SqlTable):

    """The global history of visited pages."""

    def __init__(self, parent=None):
        super().__init__("History", ['url', 'title', 'atime', 'redirect'],
                         constraints={'url': 'NOT NULL',
                                      'title': 'NOT NULL',
                                      'atime': 'NOT NULL',
                                      'redirect': 'NOT NULL'},
                         parent=parent)
        self.completion = CompletionHistory(parent=self)
        if sql.Query('pragma user_version').run().value() < _USER_VERSION:
            self.completion.delete_all()
        if not self.completion:
            # either the table is out-of-date or the user wiped it manually
            self._rebuild_completion()
        self.create_index('HistoryIndex', 'url')
        self.create_index('HistoryAtimeIndex', 'atime')
        self._contains_query = self.contains_query('url')
        self._between_query = sql.Query('SELECT * FROM History '
                                        'where not redirect '
                                        'and not url like "qute://%" '
                                        'and atime > :earliest '
                                        'and atime <= :latest '
                                        'ORDER BY atime desc')

        self._before_query = sql.Query('SELECT * FROM History '
                                       'where not redirect '
                                       'and not url like "qute://%" '
                                       'and atime <= :latest '
                                       'ORDER BY atime desc '
                                       'limit :limit offset :offset')

    def __repr__(self):
        return utils.get_repr(self, length=len(self))

    def __contains__(self, url):
        return self._contains_query.run(val=url).value()

    def _rebuild_completion(self):
        data = {'url': [], 'title': [], 'last_atime': []}
        # select the latest entry for each url
        q = sql.Query('SELECT url, title, max(atime) AS atime FROM History '
                      'WHERE NOT redirect GROUP BY url ORDER BY atime asc')
        for entry in q.run():
            data['url'].append(self._format_completion_url(QUrl(entry.url)))
            data['title'].append(entry.title)
            data['last_atime'].append(entry.atime)
        self.completion.insert_batch(data, replace=True)
        sql.Query('pragma user_version = {}'.format(_USER_VERSION)).run()

    def get_recent(self):
        """Get the most recent history entries."""
        return self.select(sort_by='atime', sort_order='desc', limit=100)

    def entries_between(self, earliest, latest):
        """Iterate non-redirect, non-qute entries between two timestamps.

        Args:
            earliest: Omit timestamps earlier than this.
            latest: Omit timestamps later than this.
        """
        self._between_query.run(earliest=earliest, latest=latest)
        return iter(self._between_query)

    def entries_before(self, latest, limit, offset):
        """Iterate non-redirect, non-qute entries occurring before a timestamp.

        Args:
            latest: Omit timestamps more recent than this.
            limit: Max number of entries to include.
            offset: Number of entries to skip.
        """
        self._before_query.run(latest=latest, limit=limit, offset=offset)
        return iter(self._before_query)

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
        self.completion.delete_all()

    def delete_url(self, url):
        """Remove all history entries with the given url.

        Args:
            url: URL string to delete.
        """
        qurl = QUrl(url)
        qtutils.ensure_valid(qurl)
        self.delete('url', self._format_url(qurl))
        self.completion.delete('url', self._format_completion_url(qurl))

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
        if not url.isValid():
            log.misc.warning("Ignoring invalid URL being added to history")
            return

        if 'no-sql-history' in objreg.get('args').debug_flags:
            return

        atime = int(atime) if (atime is not None) else int(time.time())

        try:
            self.insert({'url': self._format_url(url),
                        'title': title,
                        'atime': atime,
                        'redirect': redirect})
            if not redirect:
                self.completion.insert({
                    'url': self._format_completion_url(url),
                    'title': title,
                    'last_atime': atime
                }, replace=True)
        except sql.SqlError as e:
            if e.environmental:
                message.error("Failed to write history: {}".format(
                    e.error.databaseText()))
            else:
                raise

    def _parse_entry(self, line):
        """Parse a history line like '12345 http://example.com title'."""
        if not line or line.startswith('#'):
            return None
        data = line.split(maxsplit=2)
        if len(data) == 2:
            atime, url = data
            title = ""
        elif len(data) == 3:
            atime, url, title = data
        else:
            raise ValueError("2 or 3 fields expected")

        # http://xn--pple-43d.com/ with
        # https://bugreports.qt.io/browse/QTBUG-60364
        if url in ['http://.com/', 'https://.com/',
                   'http://www..com/', 'https://www..com/']:
            return None

        url = QUrl(url)
        if not url.isValid():
            raise ValueError("Invalid URL: {}".format(url.errorString()))

        # https://github.com/qutebrowser/qutebrowser/issues/2646
        if url.scheme() == 'data':
            return None

        # https://github.com/qutebrowser/qutebrowser/issues/670
        atime = atime.lstrip('\0')

        if '-' in atime:
            atime, flags = atime.split('-')
        else:
            flags = ''

        if not set(flags).issubset('r'):
            raise ValueError("Invalid flags {!r}".format(flags))

        redirect = 'r' in flags
        return (url, title, int(atime), redirect)

    def import_txt(self):
        """Import a history text file into sqlite if it exists.

        In older versions of qutebrowser, history was stored in a text format.
        This converts that file into the new sqlite format and moves it to a
        backup location.
        """
        path = os.path.join(standarddir.data(), 'history')
        if not os.path.isfile(path):
            return

        def action():
            with debug.log_time(log.init, 'Import old history file to sqlite'):
                try:
                    self._read(path)
                except ValueError as ex:
                    message.error('Failed to import history: {}'.format(ex))
                else:
                    self._write_backup(path)

        # delay to give message time to appear before locking down for import
        message.info('Converting {} to sqlite...'.format(path))
        QTimer.singleShot(100, action)

    def _read(self, path):
        """Import a text file into the sql database."""
        with open(path, 'r', encoding='utf-8') as f:
            data = {'url': [], 'title': [], 'atime': [], 'redirect': []}
            completion_data = {'url': [], 'title': [], 'last_atime': []}
            for (i, line) in enumerate(f):
                try:
                    parsed = self._parse_entry(line.strip())
                    if parsed is None:
                        continue
                    url, title, atime, redirect = parsed
                    data['url'].append(self._format_url(url))
                    data['title'].append(title)
                    data['atime'].append(atime)
                    data['redirect'].append(redirect)
                    if not redirect:
                        completion_data['url'].append(
                            self._format_completion_url(url))
                        completion_data['title'].append(title)
                        completion_data['last_atime'].append(atime)
                except ValueError as ex:
                    raise ValueError('Failed to parse line #{} of {}: "{}"'
                                     .format(i, path, ex))
        self.insert_batch(data)
        self.completion.insert_batch(completion_data, replace=True)

    def _write_backup(self, path):
        bak = path + '.bak'
        message.info('History import complete. Appending {} to {}'
                     .format(path, bak))
        with open(path, 'r', encoding='utf-8') as infile:
            with open(bak, 'a', encoding='utf-8') as outfile:
                for line in infile:
                    outfile.write('\n' + line)
        os.remove(path)

    def _format_url(self, url):
        return url.toString(QUrl.RemovePassword | QUrl.FullyEncoded)

    def _format_completion_url(self, url):
        return url.toString(QUrl.RemovePassword)

    @cmdutils.register(instance='web-history', debug=True)
    def debug_dump_history(self, dest):
        """Dump the history to a file in the old pre-SQL format.

        Args:
            dest: Where to write the file to.
        """
        dest = os.path.expanduser(dest)

        lines = ('{}{} {} {}'
                 .format(int(x.atime), '-r' * x.redirect, x.url, x.title)
                 for x in self.select(sort_by='atime', sort_order='asc'))

        try:
            with open(dest, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            message.info("Dumped history to {}".format(dest))
        except OSError as e:
            raise cmdexc.CommandError('Could not write history: {}', e)


def init(parent=None):
    """Initialize the web history.

    Args:
        parent: The parent to use for WebHistory.
    """
    history = WebHistory(parent=parent)
    objreg.register('web-history', history)

    if objects.backend == usertypes.Backend.QtWebKit:  # pragma: no cover
        from qutebrowser.browser.webkit import webkithistory
        webkithistory.init(history)
