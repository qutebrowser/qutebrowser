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

"""QtWebEngine specific code for downloads."""

import re
import os.path
import urllib
import functools

from PyQt5.QtCore import pyqtSlot, Qt
# pylint: disable=no-name-in-module,import-error,useless-suppression
from PyQt5.QtWebEngineWidgets import QWebEngineDownloadItem
# pylint: enable=no-name-in-module,import-error,useless-suppression

from qutebrowser.browser import downloads
from qutebrowser.utils import debug, usertypes, message, log


class DownloadItem(downloads.AbstractDownloadItem):

    """A wrapper over a QWebEngineDownloadItem.

    Attributes:
        _qt_item: The wrapped item.
    """

    def __init__(self, qt_item, parent=None):
        super().__init__(parent)
        self._qt_item = qt_item
        qt_item.downloadProgress.connect(self.stats.on_download_progress)
        qt_item.stateChanged.connect(self._on_state_changed)

    @pyqtSlot(QWebEngineDownloadItem.DownloadState)
    def _on_state_changed(self, state):
        state_name = debug.qenum_key(QWebEngineDownloadItem, state)
        log.downloads.debug("State for {!r} changed to {}".format(
            self, state_name))

        if state == QWebEngineDownloadItem.DownloadRequested:
            pass
        elif state == QWebEngineDownloadItem.DownloadInProgress:
            pass
        elif state == QWebEngineDownloadItem.DownloadCompleted:
            log.downloads.debug("Download {} finished".format(self.basename))
            self.successful = True
            self.done = True
            self.finished.emit()
            self.stats.finish()
        elif state == QWebEngineDownloadItem.DownloadCancelled:
            self.successful = False
            self.done = True
            self.cancelled.emit()
            self.stats.finish()
        elif state == QWebEngineDownloadItem.DownloadInterrupted:
            self.successful = False
            self.done = True
            # https://bugreports.qt.io/browse/QTBUG-56839
            self.error.emit("Download failed")
            self.stats.finish()
        else:
            raise ValueError("_on_state_changed was called with unknown state "
                             "{}".format(state_name))

    def _do_die(self):
        self._qt_item.downloadProgress.disconnect()
        self._qt_item.cancel()

    def _do_cancel(self):
        self._qt_item.cancel()

    def retry(self):
        # https://bugreports.qt.io/browse/QTBUG-56840
        raise downloads.UnsupportedOperationError

    def _get_open_filename(self):
        return self._filename

    def _set_fileobj(self, fileobj):
        raise downloads.UnsupportedOperationError

    def _set_tempfile(self, fileobj):
        self._set_filename(fileobj.name, force_overwrite=True,
                           remember_directory=False)

    def _ensure_can_set_filename(self, filename):
        state = self._qt_item.state()
        if state != QWebEngineDownloadItem.DownloadRequested:
            state_name = debug.qenum_key(QWebEngineDownloadItem, state)
            raise ValueError("Trying to set filename {} on {!r} which is "
                             "state {} (not in requested state)!".format(
                                 filename, self, state_name))

    def _ask_confirm_question(self, title, msg):
        no_action = functools.partial(self.cancel, remove_data=False)
        question = usertypes.Question()
        question.title = title
        question.text = msg
        question.mode = usertypes.PromptMode.yesno
        question.answered_yes.connect(self._after_set_filename)
        question.answered_no.connect(no_action)
        question.cancelled.connect(no_action)
        self.cancelled.connect(question.abort)
        self.error.connect(question.abort)
        message.global_bridge.ask(question, blocking=True)

    def _after_set_filename(self):
        self._qt_item.setPath(self._filename)
        self._qt_item.accept()


def _get_suggested_filename(path):
    """Convert a path we got from chromium to a suggested filename.

    Chromium thinks we want to download stuff to ~/Download, so even if we
    don't, we get downloads with a suffix like (1) for files existing there.

    We simply strip the suffix off via regex.

    See https://bugreports.qt.io/browse/QTBUG-56978
    """
    filename = os.path.basename(path)
    filename = re.sub(r'\([0-9]+\)$', '', filename)
    filename = urllib.parse.unquote(filename)
    return filename


class DownloadManager(downloads.AbstractDownloadManager):

    """Manager for currently running downloads."""

    def install(self, profile):
        """Set up the download manager on a QWebEngineProfile."""
        profile.downloadRequested.connect(self.handle_download,
                                          Qt.DirectConnection)

    @pyqtSlot(QWebEngineDownloadItem)
    def handle_download(self, qt_item):
        """Start a download coming from a QWebEngineProfile."""
        suggested_filename = _get_suggested_filename(qt_item.path())

        download = DownloadItem(qt_item)
        self._init_item(download, auto_remove=False,
                        suggested_filename=suggested_filename)

        filename = downloads.immediate_download_path()
        if filename is not None:
            # User doesn't want to be asked, so just use the download_dir
            target = downloads.FileDownloadTarget(filename)
            download.set_target(target)
            return

        # Ask the user for a filename - needs to be blocking!
        question = downloads.get_filename_question(
            suggested_filename=suggested_filename, url=qt_item.url(),
            parent=self)
        self._init_filename_question(question, download)

        message.global_bridge.ask(question, blocking=True)
        # The filename is set via the question.answered signal, connected in
        # _init_filename_question.
