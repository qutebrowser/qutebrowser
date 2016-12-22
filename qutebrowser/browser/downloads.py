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
import functools
import tempfile

import sip
from PyQt5.QtCore import (pyqtSlot, pyqtSignal, Qt, QObject, QUrl, QModelIndex,
                          QTimer, QAbstractListModel)
from PyQt5.QtGui import QDesktopServices

from qutebrowser.commands import cmdexc, cmdutils
from qutebrowser.config import config
from qutebrowser.utils import (usertypes, standarddir, utils, message, log,
                               qtutils)
from qutebrowser.misc import guiprocess


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


class UnsupportedOperationError(Exception):

    """Raised when an operation is not supported with the given backend."""


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


def immediate_download_path(prompt_download_directory=None):
    """Try to get an immediate download path without asking the user.

    If that's possible, we return a path immediately. If not, None is returned.

    Args:
        prompt_download_directory: If this is something else than None, it
                                   will overwrite the
                                   storage->prompt-download-directory setting.
    """
    if prompt_download_directory is None:
        prompt_download_directory = config.get('storage',
                                               'prompt-download-directory')

    if not prompt_download_directory:
        return download_dir()


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


def get_filename_question(*, suggested_filename, url, parent=None):
    """Get a Question object for a download-path.

    Args:
        suggested_filename: The "default"-name that is pre-entered as path.
        url: The URL the download originated from.
        parent: The parent of the question (a QObject).
    """
    encoding = sys.getfilesystemencoding()
    suggested_filename = utils.force_encoding(suggested_filename, encoding)

    q = usertypes.Question(parent)
    q.title = "Save file to:"
    q.text = "Please enter a location for <b>{}</b>".format(
        html.escape(url.toDisplayString()))
    q.mode = usertypes.PromptMode.text
    q.completed.connect(q.deleteLater)
    q.default = _path_suggestion(suggested_filename)
    return q


class NoFilenameError(Exception):

    """Raised when we can't find out a filename in DownloadTarget."""


# Where a download should be saved
class _DownloadTarget:

    """Abstract base class for different download targets."""

    def __init__(self):
        raise NotImplementedError

    def suggested_filename(self):
        """Get the suggested filename for this download target."""
        raise NotImplementedError


class FileDownloadTarget(_DownloadTarget):

    """Save the download to the given file.

    Attributes:
        filename: Filename where the download should be saved.
    """

    def __init__(self, filename):
        # pylint: disable=super-init-not-called
        self.filename = filename

    def suggested_filename(self):
        return os.path.basename(self.filename)


class FileObjDownloadTarget(_DownloadTarget):

    """Save the download to the given file-like object.

    Attributes:
        fileobj: File-like object where the download should be written to.
    """

    def __init__(self, fileobj):
        # pylint: disable=super-init-not-called
        self.fileobj = fileobj

    def suggested_filename(self):
        try:
            return self.fileobj.name
        except AttributeError:
            raise NoFilenameError


class OpenFileDownloadTarget(_DownloadTarget):

    """Save the download in a temp dir and directly open it.

    Attributes:
        cmdline: The command to use as string. A `{}` is expanded to the
                 filename. None means to use the system's default application.
                 If no `{}` is found, the filename is appended to the cmdline.
    """

    def __init__(self, cmdline=None):
        # pylint: disable=super-init-not-called
        self.cmdline = cmdline

    def suggested_filename(self):
        raise NoFilenameError


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
        if bytes_total in [0, -1]:  # QtWebEngine, QtWebKit
            bytes_total = None
        self.done = bytes_done
        self.total = bytes_total


class AbstractDownloadItem(QObject):

    """Shared QtNetwork/QtWebEngine part of a download item.

    Attributes:
        done: Whether the download is finished.
        stats: A DownloadItemStats object.
        index: The index of the download in the view.
        successful: Whether the download has completed successfully.
        error_msg: The current error message, or None
        fileobj: The file object to download the file to.
        raw_headers: The headers sent by the server.
        _filename: The filename of the download.
        _dead: Whether the Download has _die()'d.

    Signals:
        data_changed: The downloads metadata changed.
        finished: The download was finished.
        cancelled: The download was cancelled.
        error: An error with the download occurred.
               arg: The error message as string.
        remove_requested: Emitted when the removal of this download was
                          requested.
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

    def _do_die(self):
        """Do cleanup steps after a download has died."""
        raise NotImplementedError

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
        self._do_die()
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
                     application or `default-open-dispatcher` if set. If no
                     `{}` is found, the filename is appended to the cmdline.
        """
        assert self.successful
        filename = self._get_open_filename()
        if filename is None:  # pragma: no cover
            log.downloads.error("No filename to open the download!")
            return

        # the default program to open downloads with - will be empty string
        # if we want to use the default
        override = config.get('general', 'default-open-dispatcher')

        # precedence order: cmdline > default-open-dispatcher > openUrl

        if cmdline is None and not override:
            log.downloads.debug("Opening {} with the system application"
                                .format(filename))
            url = QUrl.fromLocalFile(filename)
            QDesktopServices.openUrl(url)
            return

        if cmdline is None and override:
            cmdline = override

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

    def _ask_confirm_question(self, title, msg):
        """Ask a confirmation question for the download."""
        raise NotImplementedError

    def _set_fileobj(self, fileobj, *, autoclose=True):
        """Set a file object to save the download to.

        Not supported by QtWebEngine.

        Args:
            fileobj: The file object to download to.
            autoclose: Close the file object automatically when it's done.
        """
        raise NotImplementedError

    def _set_tempfile(self, fileobj):
        """Set a temporary file when opening the download."""
        raise NotImplementedError

    def _set_filename(self, filename, *, force_overwrite=False,
                      remember_directory=True):
        """Set the filename to save the download to.

        Args:
            filename: The full filename to save the download to.
                      None: special value to stop the download.
            force_overwrite: Force overwriting existing files.
            remember_directory: If True, remember the directory for future
                                downloads.
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
        if remember_directory:
            last_used_directory = os.path.dirname(self._filename)

        log.downloads.debug("Setting filename to {}".format(filename))
        if force_overwrite:
            self._after_set_filename()
        elif os.path.isfile(self._filename):
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
            target: The DownloadTarget for this download.
        """
        if isinstance(target, FileObjDownloadTarget):
            self._set_fileobj(target.fileobj, autoclose=False)
        elif isinstance(target, FileDownloadTarget):
            self._set_filename(target.filename)
        elif isinstance(target, OpenFileDownloadTarget):
            try:
                fobj = temp_download_manager.get_tmpfile(self.basename)
            except OSError as exc:
                msg = "Download error: {}".format(exc)
                message.error(msg)
                self.cancel()
                return
            self.finished.connect(
                functools.partial(self._open_if_successful, target.cmdline))
            self._set_tempfile(fobj)
        else:  # pragma: no cover
            raise ValueError("Unsupported download target: {}".format(target))


class AbstractDownloadManager(QObject):

    """Backend-independent download manager code.

    Attributes:
        downloads: A list of active DownloadItems.
        _networkmanager: A NetworkManager for generic downloads.

    Signals:
        begin_remove_row: Emitted before downloads are removed.
        end_remove_row: Emitted after downloads are removed.
        begin_insert_row: Emitted before downloads are inserted.
        end_insert_row: Emitted after downloads are inserted.
        data_changed: Emitted when the data of the model changed.
                      The argument is the index of the changed download
    """

    begin_remove_row = pyqtSignal(int)
    end_remove_row = pyqtSignal()
    begin_insert_row = pyqtSignal(int)
    end_insert_row = pyqtSignal()
    data_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.downloads = []
        self._update_timer = usertypes.Timer(self, 'download-update')
        self._update_timer.timeout.connect(self._update_gui)
        self._update_timer.setInterval(_REFRESH_INTERVAL)

    def __repr__(self):
        return utils.get_repr(self, downloads=len(self.downloads))

    @pyqtSlot()
    def _update_gui(self):
        """Periodical GUI update of all items."""
        assert self.downloads
        for dl in self.downloads:
            dl.stats.update_speed()
        self.data_changed.emit(-1)

    def _init_item(self, download, auto_remove, suggested_filename):
        """Initialize a newly created DownloadItem."""
        download.cancelled.connect(download.remove)
        download.remove_requested.connect(functools.partial(
            self._remove_item, download))

        delay = config.get('ui', 'remove-finished-downloads')
        if delay > -1:
            download.finished.connect(
                lambda: QTimer.singleShot(delay, download.remove))
        elif auto_remove:
            download.finished.connect(download.remove)

        download.data_changed.connect(
            functools.partial(self._on_data_changed, download))
        download.error.connect(self._on_error)
        download.basename = suggested_filename
        idx = len(self.downloads)
        download.index = idx + 1  # "Human readable" index
        self.begin_insert_row.emit(idx)
        self.downloads.append(download)
        self.end_insert_row.emit()

        if not self._update_timer.isActive():
            self._update_timer.start()

    @pyqtSlot(AbstractDownloadItem)
    def _on_data_changed(self, download):
        """Emit data_changed signal when download data changed."""
        try:
            idx = self.downloads.index(download)
        except ValueError:
            # download has been deleted in the meantime
            return
        self.data_changed.emit(idx)

    @pyqtSlot(str)
    def _on_error(self, msg):
        """Display error message on download errors."""
        message.error("Download error: {}".format(msg))

    @pyqtSlot(AbstractDownloadItem)
    def _remove_item(self, download):
        """Remove a given download."""
        if sip.isdeleted(self):
            # https://github.com/The-Compiler/qutebrowser/issues/1242
            return
        try:
            idx = self.downloads.index(download)
        except ValueError:
            # already removed
            return
        self.begin_remove_row.emit(idx)
        del self.downloads[idx]
        self.end_remove_row.emit()
        download.deleteLater()
        self._update_indexes()
        if not self.downloads:
            self._update_timer.stop()
        log.downloads.debug("Removed download {}".format(download))

    def _update_indexes(self):
        """Update indexes of all DownloadItems."""
        for i, d in enumerate(self.downloads, 1):
            d.index = i
        self.data_changed.emit(-1)

    def _init_filename_question(self, question, download):
        """Set up an existing filename question with a download."""
        question.mode = usertypes.PromptMode.download
        question.answered.connect(download.set_target)
        question.cancelled.connect(download.cancel)
        download.cancelled.connect(question.abort)
        download.error.connect(question.abort)


class DownloadModel(QAbstractListModel):

    """A list model showing downloads."""

    def __init__(self, qtnetwork_manager, webengine_manager=None, parent=None):
        super().__init__(parent)
        self._qtnetwork_manager = qtnetwork_manager
        self._webengine_manager = webengine_manager

        qtnetwork_manager.data_changed.connect(
            functools.partial(self._on_data_changed, webengine=False))
        qtnetwork_manager.begin_insert_row.connect(
            functools.partial(self._on_begin_insert_row, webengine=False))
        qtnetwork_manager.begin_remove_row.connect(
            functools.partial(self._on_begin_remove_row, webengine=False))
        qtnetwork_manager.end_insert_row.connect(self.endInsertRows)
        qtnetwork_manager.end_remove_row.connect(self.endRemoveRows)

        if webengine_manager is not None:
            webengine_manager.data_changed.connect(
                functools.partial(self._on_data_changed, webengine=True))
            webengine_manager.begin_insert_row.connect(
                functools.partial(self._on_begin_insert_row, webengine=True))
            webengine_manager.begin_remove_row.connect(
                functools.partial(self._on_begin_remove_row, webengine=True))
            webengine_manager.end_insert_row.connect(self.endInsertRows)
            webengine_manager.end_remove_row.connect(self.endRemoveRows)

    def _all_downloads(self):
        """Combine downloads from both downloaders."""
        if self._webengine_manager is None:
            return self._qtnetwork_manager.downloads[:]
        else:
            return (self._qtnetwork_manager.downloads +
                    self._webengine_manager.downloads)

    def __len__(self):
        return len(self._all_downloads())

    def __iter__(self):
        return iter(self._all_downloads())

    def __getitem__(self, idx):
        return self._all_downloads()[idx]

    def _on_begin_insert_row(self, idx, webengine=False):
        log.downloads.debug("_on_begin_insert_row with idx {}, "
                            "webengine {}".format(idx, webengine))
        if idx == -1:
            self.beginInsertRows(QModelIndex(), 0, -1)
            return

        assert idx >= 0, idx
        if webengine:
            idx += len(self._qtnetwork_manager.downloads)
        self.beginInsertRows(QModelIndex(), idx, idx)

    def _on_begin_remove_row(self, idx, webengine=False):
        log.downloads.debug("_on_begin_remove_row with idx {}, "
                            "webengine {}".format(idx, webengine))
        if idx == -1:
            self.beginRemoveRows(QModelIndex(), 0, -1)
            return

        assert idx >= 0, idx
        if webengine:
            idx += len(self._qtnetwork_manager.downloads)
        self.beginRemoveRows(QModelIndex(), idx, idx)

    def _on_data_changed(self, idx, *, webengine):
        """Called when a downloader's data changed.

        Args:
            start: The first changed index as int.
            end: The last changed index as int, or -1 for all indices.
            webengine: If given, the QtNetwork download length is added to the
                      index.
        """
        if idx == -1:
            start_index = self.index(0, 0)
            end_index = self.last_index()
        else:
            if webengine:
                idx += len(self._qtnetwork_manager.downloads)
            start_index = self.index(idx, 0)
            end_index = self.index(idx, 0)
            qtutils.ensure_valid(start_index)
            qtutils.ensure_valid(end_index)
        self.dataChanged.emit(start_index, end_index)

    def _raise_no_download(self, count):
        """Raise an exception that the download doesn't exist.

        Args:
            count: The index of the download
        """
        if not count:
            raise cmdexc.CommandError("There's no download!")
        raise cmdexc.CommandError("There's no download {}!".format(count))

    @cmdutils.register(instance='download-model', scope='window')
    @cmdutils.argument('count', count=True)
    def download_cancel(self, all_=False, count=0):
        """Cancel the last/[count]th download.

        Args:
            all_: Cancel all running downloads
            count: The index of the download to cancel.
        """
        downloads = self._all_downloads()
        if all_:
            for download in downloads:
                if not download.done:
                    download.cancel()
        else:
            try:
                download = downloads[count - 1]
            except IndexError:
                self._raise_no_download(count)
            if download.done:
                if not count:
                    count = len(self)
                raise cmdexc.CommandError("Download {} is already done!"
                                        .format(count))
            download.cancel()

    @cmdutils.register(instance='download-model', scope='window')
    @cmdutils.argument('count', count=True)
    def download_delete(self, count=0):
        """Delete the last/[count]th download from disk.

        Args:
            count: The index of the download to delete.
        """
        try:
            download = self[count - 1]
        except IndexError:
            self._raise_no_download(count)
        if not download.successful:
            if not count:
                count = len(self)
            raise cmdexc.CommandError("Download {} is not done!".format(count))
        download.delete()
        download.remove()
        log.downloads.debug("deleted download {}".format(download))

    @cmdutils.register(instance='download-model', scope='window', maxsplit=0)
    @cmdutils.argument('count', count=True)
    def download_open(self, cmdline: str=None, count=0):
        """Open the last/[count]th download.

        If no specific command is given, this will use the system's default
        application to open the file.

        Args:
            cmdline: The command which should be used to open the file. A `{}`
                     is expanded to the temporary file name. If no `{}` is
                     present, the filename is automatically appended to the
                     cmdline.
            count: The index of the download to open.
        """
        try:
            download = self[count - 1]
        except IndexError:
            self._raise_no_download(count)
        if not download.successful:
            if not count:
                count = len(self)
            raise cmdexc.CommandError("Download {} is not done!".format(count))
        download.open_file(cmdline)

    @cmdutils.register(instance='download-model', scope='window')
    @cmdutils.argument('count', count=True)
    def download_retry(self, count=0):
        """Retry the first failed/[count]th download.

        Args:
            count: The index of the download to retry.
        """
        if count:
            try:
                download = self[count - 1]
            except IndexError:
                self._raise_no_download(count)
            if download.successful or not download.done:
                raise cmdexc.CommandError("Download {} did not fail!".format(
                    count))
        else:
            to_retry = [d for d in self if d.done and not d.successful]
            if not to_retry:
                raise cmdexc.CommandError("No failed downloads!")
            else:
                download = to_retry[0]
        download.retry()

    def can_clear(self):
        """Check if there are finished downloads to clear."""
        return any(download.done for download in self)

    @cmdutils.register(instance='download-model', scope='window')
    def download_clear(self):
        """Remove all finished downloads from the list."""
        for download in self:
            if download.done:
                download.remove()

    @cmdutils.register(instance='download-model', scope='window')
    @cmdutils.argument('count', count=True)
    def download_remove(self, all_=False, count=0):
        """Remove the last/[count]th download from the list.

        Args:
            all_: Remove all finished downloads.
            count: The index of the download to remove.
        """
        if all_:
            self.download_clear()
        else:
            try:
                download = self[count - 1]
            except IndexError:
                self._raise_no_download(count)
            if not download.done:
                if not count:
                    count = len(self)
                raise cmdexc.CommandError("Download {} is not done!"
                                          .format(count))
            download.remove()

    def running_downloads(self):
        """Return the amount of still running downloads.

        Return:
            The number of unfinished downloads.
        """
        return sum(1 for download in self if not download.done)

    def last_index(self):
        """Get the last index in the model.

        Return:
            A (possibly invalid) QModelIndex.
        """
        idx = self.index(self.rowCount() - 1)
        return idx

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        """Simple constant header."""
        if (section == 0 and orientation == Qt.Horizontal and
                role == Qt.DisplayRole):
            return "Downloads"
        else:
            return ""

    def data(self, index, role):
        """Download data from DownloadManager."""
        if not index.isValid():
            return None

        if index.parent().isValid() or index.column() != 0:
            return None

        item = self[index.row()]
        if role == Qt.DisplayRole:
            data = str(item)
        elif role == Qt.ForegroundRole:
            data = item.get_status_color('fg')
        elif role == Qt.BackgroundRole:
            data = item.get_status_color('bg')
        elif role == ModelRole.item:
            data = item
        elif role == Qt.ToolTipRole:
            if item.error_msg is None:
                data = None
            else:
                return item.error_msg
        else:
            data = None
        return data

    def flags(self, index):
        """Override flags so items aren't selectable.

        The default would be Qt.ItemIsEnabled | Qt.ItemIsSelectable.
        """
        if not index.isValid():
            return Qt.ItemFlags()
        return Qt.ItemIsEnabled | Qt.ItemNeverHasChildren

    def rowCount(self, parent=QModelIndex()):
        """Get count of active downloads."""
        if parent.isValid():
            # We don't have children
            return 0
        return len(self)


class TempDownloadManager:

    """Manager to handle temporary download files.

    The downloads are downloaded to a temporary location and then openened with
    the system standard application. The temporary files are deleted when
    qutebrowser is shutdown.

    Attributes:
        files: A list of NamedTemporaryFiles of downloaded items.
    """

    def __init__(self):
        self.files = []
        self._tmpdir = None

    def cleanup(self):
        """Clean up any temporary files."""
        if self._tmpdir is not None:
            try:
                self._tmpdir.cleanup()
            except OSError:
                log.misc.exception("Failed to clean up temporary download "
                                   "directory")
            self._tmpdir = None

    def _get_tmpdir(self):
        """Return the temporary directory that is used for downloads.

        The directory is created lazily on first access.

        Return:
            The tempfile.TemporaryDirectory that is used.
        """
        if self._tmpdir is None:
            self._tmpdir = tempfile.TemporaryDirectory(
                prefix='qutebrowser-downloads-')
        return self._tmpdir

    def get_tmpfile(self, suggested_name):
        """Return a temporary file in the temporary downloads directory.

        The files are kept as long as qutebrowser is running and automatically
        cleaned up at program exit.

        Args:
            suggested_name: str of the "suggested"/original filename. Used as a
                            suffix, so any file extenions are preserved.

        Return:
            A tempfile.NamedTemporaryFile that should be used to save the file.
        """
        tmpdir = self._get_tmpdir()
        encoding = sys.getfilesystemencoding()
        suggested_name = utils.force_encoding(suggested_name, encoding)
        # Make sure that the filename is not too long
        suggested_name = utils.elide_filename(suggested_name, 50)
        fobj = tempfile.NamedTemporaryFile(dir=tmpdir.name, delete=False,
                                           suffix=suggested_name)
        self.files.append(fobj)
        return fobj


temp_download_manager = TempDownloadManager()
