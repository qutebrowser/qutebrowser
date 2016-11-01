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

"""Shared QtWebKit/QtWebEngine code for downloads."""

import sys
import shlex
import html
import os.path
import collections

from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt, QObject, QUrl
from PyQt5.QtGui import QDesktopServices

from qutebrowser.config import config
from qutebrowser.utils import usertypes, standarddir, utils, message, log
from qutebrowser.misc import guiprocess


_DownloadPath = collections.namedtuple('_DownloadPath', ['filename',
                                                         'question'])


ModelRole = usertypes.enum('ModelRole', ['item'], start=Qt.UserRole,
                           is_int=True)


# Remember the last used directory
last_used_directory = None


# All REFRESH_INTERVAL milliseconds, speeds will be recalculated and downloads
# redrawn.
_REFRESH_INTERVAL = 500


class UnsupportedAttribute:

    """Class which is used to create attributes which are not supported.

    This is used for attributes like "fileobj" for downloads which are not
    supported with QtWebengine.
    """

    pass


def download_dir():
    """Get the download directory to use."""
    directory = config.get('storage', 'download-directory')
    remember_dir = config.get('storage', 'remember-download-directory')

    if remember_dir and last_used_directory is not None:
        return last_used_directory
    elif directory is None:
        return standarddir.download()
    else:
        return directory


def _path_suggestion(filename):
    """Get the suggested file path.

    Args:
        filename: The filename to use if included in the suggestion.
    """
    suggestion = config.get('completion', 'download-path-suggestion')
    if suggestion == 'path':
        # add trailing '/' if not present
        return os.path.join(download_dir(), '')
    elif suggestion == 'filename':
        return filename
    elif suggestion == 'both':
        return os.path.join(download_dir(), filename)
    else:  # pragma: no cover
        raise ValueError("Invalid suggestion value {}!".format(suggestion))


def create_full_filename(basename, filename):
    """Create a full filename based on the given basename and filename.

    Args:
        basename: The basename to use if filename is a directory.
        filename: The path to a folder or file where you want to save.

    Return:
        The full absolute path, or None if filename creation was not possible.
    """
    # Remove chars which can't be encoded in the filename encoding.
    # See https://github.com/The-Compiler/qutebrowser/issues/427
    encoding = sys.getfilesystemencoding()
    filename = utils.force_encoding(filename, encoding)
    basename = utils.force_encoding(basename, encoding)
    if os.path.isabs(filename) and os.path.isdir(filename):
        # We got an absolute directory from the user, so we save it under
        # the default filename in that directory.
        return os.path.join(filename, basename)
    elif os.path.isabs(filename):
        # We got an absolute filename from the user, so we save it under
        # that filename.
        return filename
    return None


def ask_for_filename(suggested_filename, *, url, parent=None,
                     prompt_download_directory=None):
    """Prepare a question for a download-path.

    If a filename can be determined directly, it is returned instead.

    Returns a (filename, question)-namedtuple, in which one component is
    None. filename is a string, question is a usertypes.Question. The
    question has a special .ask() method that takes no arguments for
    convenience, as this function does not yet ask the question, it
    only prepares it.

    Args:
        suggested_filename: The "default"-name that is pre-entered as path.
        url: The URL the download originated from.
        parent: The parent of the question (a QObject).
        prompt_download_directory: If this is something else than None, it
                                   will overwrite the
                                   storage->prompt-download-directory setting.
    """
    if prompt_download_directory is None:
        prompt_download_directory = config.get('storage',
                                               'prompt-download-directory')

    if not prompt_download_directory:
        return _DownloadPath(filename=download_dir(), question=None)

    encoding = sys.getfilesystemencoding()
    suggested_filename = utils.force_encoding(suggested_filename, encoding)

    q = usertypes.Question(parent)
    q.title = "Save file to:"
    q.text = "Please enter a location for <b>{}</b>".format(
        html.escape(url.toDisplayString()))
    q.mode = usertypes.PromptMode.text
    q.completed.connect(q.deleteLater)
    q.default = _path_suggestion(suggested_filename)

    q.ask = lambda: message.global_bridge.ask(q, blocking=False)
    return _DownloadPath(filename=None, question=q)


class DownloadItemStats(QObject):

    """Statistics (bytes done, total bytes, time, etc.) about a download.

    Class attributes:
        SPEED_AVG_WINDOW: How many seconds of speed data to average to
                          estimate the remaining time.

    Attributes:
        done: How many bytes there are already downloaded.
        total: The total count of bytes.  None if the total is unknown.
        speed: The current download speed, in bytes per second.
        _speed_avg: A rolling average of speeds.
        _last_done: The count of bytes which where downloaded when calculating
                    the speed the last time.
    """

    SPEED_AVG_WINDOW = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self.total = None
        self.done = 0
        self.speed = 0
        self._last_done = 0
        samples = int(self.SPEED_AVG_WINDOW * (1000 / _REFRESH_INTERVAL))
        self._speed_avg = collections.deque(maxlen=samples)

    def update_speed(self):
        """Recalculate the current download speed.

        The caller needs to guarantee this is called all _REFRESH_INTERVAL ms.
        """
        if self.done is None:
            # this can happen for very fast downloads, e.g. when actually
            # opening a file
            return
        delta = self.done - self._last_done
        self.speed = delta * 1000 / _REFRESH_INTERVAL
        self._speed_avg.append(self.speed)
        self._last_done = self.done

    def finish(self):
        """Set the download stats as finished."""
        self.done = self.total

    def percentage(self):
        """The current download percentage, or None if unknown."""
        if self.done == self.total:
            return 100
        elif self.total == 0 or self.total is None:
            return None
        else:
            return 100 * self.done / self.total

    def remaining_time(self):
        """The remaining download time in seconds, or None."""
        if self.total is None or not self._speed_avg:
            # No average yet or we don't know the total size.
            return None
        remaining_bytes = self.total - self.done
        avg = sum(self._speed_avg) / len(self._speed_avg)
        if avg == 0:
            # Download stalled
            return None
        else:
            return remaining_bytes / avg

    @pyqtSlot('qint64', 'qint64')
    def on_download_progress(self, bytes_done, bytes_total):
        """Update local variables when the download progress changed.

        Args:
            bytes_done: How many bytes are downloaded.
            bytes_total: How many bytes there are to download in total.
        """
        if bytes_total == -1:
            bytes_total = None
        self.done = bytes_done
        self.total = bytes_total


class AbstractDownloadItem(QObject):

    """Shared QtNetwork/QtWebEngine part of a download item.

    FIXME
    """

    data_changed = pyqtSignal()
    finished = pyqtSignal()
    error = pyqtSignal(str)
    cancelled = pyqtSignal()
    remove_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.done = False
        self.stats = DownloadItemStats(self)
        self.index = 0
        self.error_msg = None
        self.basename = '???'
        self.successful = False

        self.autoclose = UnsupportedAttribute()
        self.fileobj = UnsupportedAttribute()
        self.raw_headers = UnsupportedAttribute()

        self._filename = None
        self._dead = False

    def __repr__(self):
        return utils.get_repr(self, basename=self.basename)

    def __str__(self):
        """Get the download as a string.

        Example: foo.pdf [699.2kB/s|0.34|16%|4.253/25.124]
        """
        speed = utils.format_size(self.stats.speed, suffix='B/s')
        down = utils.format_size(self.stats.done, suffix='B')
        perc = self.stats.percentage()
        remaining = self.stats.remaining_time()
        if self.error_msg is None:
            errmsg = ""
        else:
            errmsg = " - {}".format(self.error_msg)
        if all(e is None for e in [perc, remaining, self.stats.total]):
            return ('{index}: {name} [{speed:>10}|{down}]{errmsg}'.format(
                index=self.index, name=self.basename, speed=speed,
                down=down, errmsg=errmsg))
        perc = round(perc)
        if remaining is None:
            remaining = '?'
        else:
            remaining = utils.format_seconds(remaining)
        total = utils.format_size(self.stats.total, suffix='B')
        if self.done:
            return ('{index}: {name} [{perc:>2}%|{total}]{errmsg}'.format(
                index=self.index, name=self.basename, perc=perc,
                total=total, errmsg=errmsg))
        else:
            return ('{index}: {name} [{speed:>10}|{remaining:>5}|{perc:>2}%|'
                    '{down}/{total}]{errmsg}'.format(
                        index=self.index, name=self.basename, speed=speed,
                        remaining=remaining, perc=perc, down=down,
                        total=total, errmsg=errmsg))

    def _die(self, msg):
        """Abort the download and emit an error."""
        assert not self.successful
        # Prevent actions if calling _die() twice.
        #
        # For QtWebKit, this might happen if the error handler correctly
        # connects, and the error occurs in _init_reply between
        # reply.error.connect and the reply.error() check. In this case, the
        # connected error handlers will be called twice, once via the direct
        # error.emit() and once here in _die(). The stacks look like this then:
        #
        #   <networkmanager error.emit> -> on_reply_error -> _die ->
        #   self.error.emit()
        #
        # and
        #
        #   [_init_reply -> <single shot timer> ->] <lambda in _init_reply> ->
        #   self.error.emit()
        #
        # which may lead to duplicate error messages (and failing tests)
        if self._dead:
            return
        self._dead = True
        self.error_msg = msg
        self.stats.finish()
        self.error.emit(msg)
        self.done = True
        self.data_changed.emit()

    def get_status_color(self, position):
        """Choose an appropriate color for presenting the download's status.

        Args:
            position: The color type requested, can be 'fg' or 'bg'.
        """
        # pylint: disable=bad-config-call
        # WORKAROUND for https://bitbucket.org/logilab/astroid/issue/104/
        assert position in ["fg", "bg"]
        start = config.get('colors', 'downloads.{}.start'.format(position))
        stop = config.get('colors', 'downloads.{}.stop'.format(position))
        system = config.get('colors', 'downloads.{}.system'.format(position))
        error = config.get('colors', 'downloads.{}.error'.format(position))
        if self.error_msg is not None:
            assert not self.successful
            return error
        elif self.stats.percentage() is None:
            return start
        else:
            return utils.interpolate_color(start, stop,
                                           self.stats.percentage(), system)

    def _do_cancel(self):
        """Actual cancel implementation."""
        raise NotImplementedError

    @pyqtSlot()
    def cancel(self, *, remove_data=True):
        """Cancel the download.

        Args:
            remove_data: Whether to remove the downloaded data.
        """
        self._do_cancel()
        log.downloads.debug("cancelled")
        self.cancelled.emit()
        if remove_data:
            self.delete()
        self.done = True
        self.finished.emit()
        self.data_changed.emit()

    @pyqtSlot()
    def remove(self):
        """Remove the download from the model."""
        self.remove_requested.emit()

    def delete(self):
        """Delete the downloaded file."""
        try:
            if self._filename is not None and os.path.exists(self._filename):
                os.remove(self._filename)
                log.downloads.debug("Deleted {}".format(self._filename))
            else:
                log.downloads.debug("Not deleting {}".format(self._filename))
        except OSError:
            log.downloads.exception("Failed to remove partial file")

    @pyqtSlot()
    def retry(self):
        """Retry a failed download."""
        raise NotImplementedError

    def _get_open_filename(self):
        """Get the filename to open a download.

        Returns None if no suitable filename was found.
        """
        raise NotImplementedError

    @pyqtSlot()
    def open_file(self, cmdline=None):
        """Open the downloaded file.

        Args:
            cmdline: The command to use as string. A `{}` is expanded to the
                     filename. None means to use the system's default
                     application. If no `{}` is found, the filename is appended
                     to the cmdline.
        """
        assert self.successful
        filename = self._get_open_filename()
        if filename is None:  # pragma: no cover
            log.downloads.error("No filename to open the download!")
            return

        if cmdline is None:
            log.downloads.debug("Opening {} with the system application"
                                .format(filename))
            url = QUrl.fromLocalFile(filename)
            QDesktopServices.openUrl(url)
            return

        cmd, *args = shlex.split(cmdline)
        args = [arg.replace('{}', filename) for arg in args]
        if '{}' not in cmdline:
            args.append(filename)
        log.downloads.debug("Opening {} with {}"
                            .format(filename, [cmd] + args))
        proc = guiprocess.GUIProcess(what='download')
        proc.start_detached(cmd, args)

    def _ensure_can_set_filename(self, filename):
        """Make sure we can still set a filename."""
        raise NotImplementedError

    def _after_set_filename(self):
        """Finish initialization based on self._filename."""
        raise NotImplementedError

    def set_filename(self, filename):
        """Set the filename to save the download to.

        Args:
            filename: The full filename to save the download to.
                      None: special value to stop the download.
        """
        global last_used_directory
        filename = os.path.expanduser(filename)
        self._ensure_can_set_filename(filename)

        self._filename = create_full_filename(self.basename, filename)
        if self._filename is None:
            # We only got a filename (without directory) or a relative path
            # from the user, so we append that to the default directory and
            # try again.
            self._filename = create_full_filename(
                self.basename, os.path.join(download_dir(), filename))

        # At this point, we have a misconfigured XDG_DOWNLOAD_DIR, as
        # download_dir() + filename is still no absolute path.
        # The config value is checked for "absoluteness", but
        # ~/.config/user-dirs.dirs may be misconfigured and a non-absolute path
        # may be set for XDG_DOWNLOAD_DIR
        if self._filename is None:
            message.error(
                "XDG_DOWNLOAD_DIR points to a relative path - please check"
                " your ~/.config/user-dirs.dirs. The download is saved in"
                " your home directory.",
            )
            # fall back to $HOME as download_dir
            self._filename = create_full_filename(self.basename,
                                                  os.path.expanduser('~'))

        self.basename = os.path.basename(self._filename)
        last_used_directory = os.path.dirname(self._filename)

        log.downloads.debug("Setting filename to {}".format(filename))
        if os.path.isfile(self._filename):
            # The file already exists, so ask the user if it should be
            # overwritten.
            txt = "<b>{}</b> already exists. Overwrite?".format(
                html.escape(self._filename))
            self._ask_confirm_question("Overwrite existing file?", txt)
        # FIFO, device node, etc. Make sure we want to do this
        elif (os.path.exists(self._filename) and
              not os.path.isdir(self._filename)):
            txt = ("<b>{}</b> already exists and is a special file. Write to "
                   "it anyways?".format(html.escape(self._filename)))
            self._ask_confirm_question("Overwrite special file?", txt)
        else:
            self._after_set_filename()

    def _open_if_successful(self, cmdline):
        """Open the downloaded file, but only if it was successful.

        Args:
            cmdline: Passed to DownloadItem.open_file().
        """
        if not self.successful:
            log.downloads.debug("{} finished but not successful, not opening!"
                                .format(self))
            return
        self.open_file(cmdline)

    def set_target(self, target):
        """Set the target for a given download.

        Args:
            target: The usertypes.DownloadTarget for this download.
        """
        raise NotImplementedError


class AbstractDownloadManager(QObject):

    """Backend-independent download manager code.

    Attributes:
        downloads: A list of active DownloadItems.
        questions: A list of Question objects to not GC them.
        _networkmanager: A NetworkManager for generic downloads.
        _win_id: The window ID the DownloadManager runs in.

    Signals:
        begin_remove_rows: Emitted before downloads are removed.
        end_remove_rows: Emitted after downloads are removed.
        begin_insert_rows: Emitted before downloads are inserted.
        end_insert_rows: Emitted after downloads are inserted.
        data_changed: Emitted when the data of the model changed.
                      The arguments are int indices to the downloads.
    """
