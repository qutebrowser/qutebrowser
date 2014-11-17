# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Functions related to adblocking."""

import io
import os.path
import functools

from PyQt5.QtCore import QStandardPaths

from qutebrowser.config import config
from qutebrowser.utils import objreg, standarddir, log, message
from qutebrowser.commands import cmdutils


class HostBlocker:

    """Manage blocked hosts based from /etc/hosts-like files.

    Attributes:
        blocked_hosts: A set of blocked hosts.
        _in_progress: The DownloadItems which are currently downloading.
        _done: The ByteIOs of successfully downloaded downloads.
        _hosts_file: The path to the blocked-hosts file.

    Class attributes:
        WHITELISTED: Hosts which never should be blocked.
    """

    WHITELISTED = ('localhost', 'localhost.localdomain', 'broadcasthost',
                   'local')

    def __init__(self):
        self.blocked_hosts = set()
        self._in_progress = []
        self._done = []
        data_dir = standarddir.get(QStandardPaths.DataLocation)
        self._hosts_file = os.path.join(data_dir, 'blocked-hosts')
        objreg.get('config').changed.connect(self.on_config_changed)

    def read_hosts(self):
        """Read hosts from the existing blocked-hosts file."""
        self.blocked_hosts = set()
        if os.path.exists(self._hosts_file):
            with open(self._hosts_file, 'r', encoding='utf-8') as f:
                for line in f:
                    self.blocked_hosts.add(line.strip())
        else:
            if config.get('permissions', 'host-block-lists') is not None:
                message.info('last-focused',
                             "Run :adblock-update to get adblock lists.")

    @cmdutils.register(instance='host-blocker')
    def adblock_update(self):
        """Update the adblock block lists."""
        urls = config.get('permissions', 'host-block-lists')
        download_manager = objreg.get('download-manager', scope='window',
                                      window='last-focused')
        if urls is None:
            return
        for url in urls:
            fobj = io.BytesIO()
            fobj.name = 'adblock: ' + url.host()
            download = download_manager.get(url, fileobj=fobj)
            self._in_progress.append(download)
            download.finished.connect(
                functools.partial(self.on_download_finished, download))

    def _merge_files(self):
        """Read and merge host files.

        Return:
            A set of the merged hosts.
        """
        self.blocked_hosts = set()
        line_counts = {}
        for byte_io in self._done:
            line_counts[byte_io.name] = 0
            byte_io.seek(0)
            f = io.TextIOWrapper(byte_io, encoding='utf-8')
            for line in f:
                line_counts[byte_io.name] += 1
                # Remove comments
                try:
                    hash_idx = line.index('#')
                    line = line[:hash_idx]
                except ValueError:
                    pass
                line = line.strip()
                # Skip empty lines
                if not line:
                    continue
                parts = line.split()
                if len(parts) == 1:
                    # "one host per line" format
                    host = parts[0]
                elif len(parts) == 2:
                    # /etc/hosts format
                    host = parts[1]
                else:
                    # FIXME what to do here?
                    raise ValueError("Invalid line '{}'".format(line))
                if host not in self.WHITELISTED:
                    self.blocked_hosts.add(host)
        for name, lines in line_counts.items():
            log.misc.debug("{}: read {} lines".format(name, lines))

    def on_lists_downloaded(self):
        """Install block lists after files have been downloaded."""
        self._merge_files()
        for f in self._done:
            f.close()
        with open(self._hosts_file, 'w', encoding='utf-8') as f:
            for host in sorted(self.blocked_hosts):
                f.write(host + '\n')
            message.info('last-focused', "adblock: Read {} hosts from {} "
                         "sources.".format(len(self.blocked_hosts),
                                           len(self._done)))
        self._done = []

    @config.change_filter('permissions', 'host-block-lists')
    def on_config_changed(self):
        """Update files when the config changed."""
        urls = config.get('permissions', 'host-block-lists')
        if urls is None:
            try:
                os.remove(self._hosts_file)
            except IOError:
                log.misc.exception("Failed to delete hosts file.")
        else:
            self.adblock_update()

    def on_download_finished(self, download):
        """Check if all downloads are finished and if so, trigger reading.

        Arguments:
            download: The finished DownloadItem.
        """
        self._in_progress.remove(download)
        if download.successful:
            self._done.append(download.fileobj)
        if not self._in_progress:
            self.on_lists_downloaded()
