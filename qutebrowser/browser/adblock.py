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

"""Functions related to ad blocking."""

import io
import os.path
import functools
import posixpath
import zipfile

from qutebrowser.config import config
from qutebrowser.utils import objreg, standarddir, log, message
from qutebrowser.commands import cmdutils, cmdexc


def guess_zip_filename(zf):
    """Guess which file to use inside a zip file.

    Args:
        zf: A ZipFile instance.
    """
    files = zf.namelist()
    if len(files) == 1:
        return files[0]
    else:
        for e in files:
            if posixpath.splitext(e)[0].lower() == 'hosts':
                return e
    raise FileNotFoundError("No hosts file found in zip")


def get_fileobj(byte_io):
    """Get an usable file object to read the hosts file from."""
    byte_io.seek(0)  # rewind downloaded file
    if zipfile.is_zipfile(byte_io):
        byte_io.seek(0)  # rewind what zipfile.is_zipfile did
        zf = zipfile.ZipFile(byte_io)
        filename = guess_zip_filename(zf)
        byte_io = zf.open(filename, mode='r')
    else:
        byte_io.seek(0)  # rewind what zipfile.is_zipfile did
    return io.TextIOWrapper(byte_io, encoding='utf-8')


class FakeDownload:

    """A download stub to use on_download_finished with local files."""

    def __init__(self, fileobj):
        self.basename = os.path.basename(fileobj.name)
        self.fileobj = fileobj
        self.successful = True


class HostBlocker:

    """Manage blocked hosts based from /etc/hosts-like files.

    Attributes:
        blocked_hosts: A set of blocked hosts.
        _in_progress: The DownloadItems which are currently downloading.
        _done_count: How many files have been read successfully.
        _hosts_file: The path to the blocked-hosts file.

    Class attributes:
        WHITELISTED: Hosts which never should be blocked.
    """

    WHITELISTED = ('localhost', 'localhost.localdomain', 'broadcasthost',
                   'local')

    def __init__(self):
        self.blocked_hosts = set()
        self._in_progress = []
        self._done_count = 0
        data_dir = standarddir.data()
        if data_dir is None:
            self._hosts_file = None
        else:
            self._hosts_file = os.path.join(data_dir, 'blocked-hosts')
        objreg.get('config').changed.connect(self.on_config_changed)

    def read_hosts(self):
        """Read hosts from the existing blocked-hosts file."""
        self.blocked_hosts = set()
        if self._hosts_file is None:
            return
        if os.path.exists(self._hosts_file):
            try:
                with open(self._hosts_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        self.blocked_hosts.add(line.strip())
            except OSError:
                log.misc.exception("Failed to read host blocklist!")
        else:
            args = objreg.get('args')
            if (config.get('content', 'host-block-lists') is not None and
                    args.basedir is None):
                message.info('current',
                             "Run :adblock-update to get adblock lists.")

    @cmdutils.register(instance='host-blocker', win_id='win_id')
    def adblock_update(self, win_id):
        """Update the adblock block lists."""
        if self._hosts_file is None:
            raise cmdexc.CommandError("No data storage is configured!")
        self.blocked_hosts = set()
        self._done_count = 0
        urls = config.get('content', 'host-block-lists')
        download_manager = objreg.get('download-manager', scope='window',
                                      window='last-focused')
        if urls is None:
            return
        for url in urls:
            if url.scheme() == 'file':
                try:
                    fileobj = open(url.path(), 'rb')
                except OSError as e:
                    message.error(win_id, "adblock: Error while reading {}: "
                                  "{}".format(url.path(), e.strerror))
                    continue
                download = FakeDownload(fileobj)
                self._in_progress.append(download)
                self.on_download_finished(download)
            else:
                fobj = io.BytesIO()
                fobj.name = 'adblock: ' + url.host()
                download = download_manager.get(url, fileobj=fobj,
                                                auto_remove=True)
                self._in_progress.append(download)
                download.finished.connect(
                    functools.partial(self.on_download_finished, download))

    def _merge_file(self, byte_io):
        """Read and merge host files.

        Args:
            byte_io: The BytesIO object of the completed download.

        Return:
            A set of the merged hosts.
        """
        error_count = 0
        line_count = 0
        try:
            f = get_fileobj(byte_io)
        except (OSError, UnicodeDecodeError, zipfile.BadZipFile,
                zipfile.LargeZipFile) as e:
            message.error('current', "adblock: Error while reading {}: {} - "
                          "{}".format(byte_io.name, e.__class__.__name__, e))
            return
        for line in f:
            line_count += 1
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
                error_count += 1
                continue
            if host not in self.WHITELISTED:
                self.blocked_hosts.add(host)
        log.misc.debug("{}: read {} lines".format(byte_io.name, line_count))
        if error_count > 0:
            message.error('current', "adblock: {} read errors for {}".format(
                error_count, byte_io.name))

    def on_lists_downloaded(self):
        """Install block lists after files have been downloaded."""
        with open(self._hosts_file, 'w', encoding='utf-8') as f:
            for host in sorted(self.blocked_hosts):
                f.write(host + '\n')
            message.info('current', "adblock: Read {} hosts from {} sources."
                         .format(len(self.blocked_hosts), self._done_count))

    @config.change_filter('content', 'host-block-lists')
    def on_config_changed(self):
        """Update files when the config changed."""
        urls = config.get('content', 'host-block-lists')
        if urls is None:
            try:
                os.remove(self._hosts_file)
            except OSError:
                log.misc.exception("Failed to delete hosts file.")

    def on_download_finished(self, download):
        """Check if all downloads are finished and if so, trigger reading.

        Arguments:
            download: The finished DownloadItem.
        """
        self._in_progress.remove(download)
        if download.successful:
            self._done_count += 1
            try:
                self._merge_file(download.fileobj)
            finally:
                download.fileobj.close()
        if not self._in_progress:
            try:
                self.on_lists_downloaded()
            except OSError:
                log.misc.exception("Failed to write host block list!")
