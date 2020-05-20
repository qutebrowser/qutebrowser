# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from PyQt5.QtCore import pyqtSlot, Qt, QUrl, QObject
from PyQt5.QtWebEngineWidgets import QWebEngineDownloadItem

from qutebrowser.browser import downloads, pdfjs
from qutebrowser.utils import debug, usertypes, message, log, qtutils


class DownloadItem(downloads.AbstractDownloadItem):

    """A wrapper over a QWebEngineDownloadItem.

    Attributes:
        _qt_item: The wrapped item.
    """

    def __init__(self, qt_item: QWebEngineDownloadItem,
                 parent: QObject = None) -> None:
        super().__init__(parent)
        self._qt_item = qt_item
        qt_item.downloadProgress.connect(  # type: ignore[attr-defined]
            self.stats.on_download_progress)
        qt_item.stateChanged.connect(  # type: ignore[attr-defined]
            self._on_state_changed)

        # Ensure wrapped qt_item is deleted manually when the wrapper object
        # is deleted. See https://github.com/qutebrowser/qutebrowser/issues/3373
        self.destroyed.connect(self._qt_item.deleteLater)

    def _is_page_download(self):
        """Check if this item is a page (i.e. mhtml) download."""
        return (self._qt_item.savePageFormat() !=
                QWebEngineDownloadItem.UnknownSaveFormat)

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
            if self._is_page_download():
                # Same logging as QtWebKit mhtml downloads.
                log.downloads.debug("File successfully written.")
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
            # https://bugreports.qt.io/browse/QTBUG-56839
            try:
                reason = self._qt_item.interruptReasonString()
            except AttributeError:
                # Qt < 5.9
                reason = "Download failed"
            self._die(reason)
        else:
            raise ValueError("_on_state_changed was called with unknown state "
                             "{}".format(state_name))

    def _do_die(self):
        progress_signal = self._qt_item.downloadProgress
        progress_signal.disconnect()  # type: ignore[attr-defined]
        if self._qt_item.state() != QWebEngineDownloadItem.DownloadInterrupted:
            self._qt_item.cancel()

    def _do_cancel(self):
        self._qt_item.cancel()

    def retry(self):
        state = self._qt_item.state()
        if state != QWebEngineDownloadItem.DownloadInterrupted:
            log.downloads.warning(
                "Trying to retry download in state {}".format(
                    debug.qenum_key(QWebEngineDownloadItem, state)))
            return

        try:
            self._qt_item.resume()
        except AttributeError:
            raise downloads.UnsupportedOperationError(
                "Retrying downloads is unsupported with QtWebEngine on "
                "Qt/PyQt < 5.10")

    def _get_open_filename(self):
        return self._filename

    def url(self) -> QUrl:
        return self._qt_item.url()

    def _set_fileobj(self, fileobj, *, autoclose=True):
        raise downloads.UnsupportedOperationError

    def _set_tempfile(self, fileobj):
        fileobj.close()
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
        question.url = 'file://{}'.format(self._filename)
        question.mode = usertypes.PromptMode.yesno
        question.answered_yes.connect(self._after_set_filename)
        question.answered_no.connect(no_action)
        question.cancelled.connect(no_action)
        self.cancelled.connect(question.abort)
        self.error.connect(question.abort)
        message.global_bridge.ask(question, blocking=True)

    def _ask_create_parent_question(self, title, msg,
                                    force_overwrite, remember_directory):
        assert self._filename is not None
        no_action = functools.partial(self.cancel, remove_data=False)
        question = usertypes.Question()
        question.title = title
        question.text = msg
        question.url = 'file://{}'.format(os.path.dirname(self._filename))
        question.mode = usertypes.PromptMode.yesno
        question.answered_yes.connect(lambda:
                                      self._after_create_parent_question(
                                          force_overwrite, remember_directory))
        question.answered_no.connect(no_action)
        question.cancelled.connect(no_action)
        self.cancelled.connect(question.abort)
        self.error.connect(question.abort)
        message.global_bridge.ask(question, blocking=True)

    def _after_set_filename(self):
        assert self._filename is not None

        dirname, basename = os.path.split(self._filename)
        try:
            # Qt 5.14
            self._qt_item.setDownloadDirectory(dirname)
            self._qt_item.setDownloadFileName(basename)
        except AttributeError:
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

    suffix_re = re.compile(r"""
      \ ?  # Optional space between filename and suffix
      (
        # Numerical suffix
        \([0-9]+\)
      |
        # ISO-8601 suffix
        # https://cs.chromium.org/chromium/src/base/time/time_to_iso8601.cc
        \ -\ \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d{3}Z
      )
      (?=\.|$)  # Begin of extension, or filename without extension
    """, re.VERBOSE)

    filename = suffix_re.sub('', filename)
    if not qtutils.version_check('5.9', compiled=False):
        # https://bugreports.qt.io/browse/QTBUG-58155
        filename = urllib.parse.unquote(filename)
        # Doing basename a *second* time because there could be a %2F in
        # there...
        filename = os.path.basename(filename)
    return filename


class DownloadManager(downloads.AbstractDownloadManager):

    """Manager for currently running downloads.

    Attributes:
        _mhtml_target: DownloadTarget for the next MHTML download.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mhtml_target = None

    def install(self, profile):
        """Set up the download manager on a QWebEngineProfile."""
        profile.downloadRequested.connect(self.handle_download,
                                          Qt.DirectConnection)

    @pyqtSlot(QWebEngineDownloadItem)
    def handle_download(self, qt_item):
        """Start a download coming from a QWebEngineProfile."""
        suggested_filename = _get_suggested_filename(qt_item.path())
        use_pdfjs = pdfjs.should_use_pdfjs(qt_item.mimeType(), qt_item.url())

        download = DownloadItem(qt_item)
        self._init_item(download, auto_remove=use_pdfjs,
                        suggested_filename=suggested_filename)

        if self._mhtml_target is not None:
            download.set_target(self._mhtml_target)
            self._mhtml_target = None
            return
        if use_pdfjs:
            download.set_target(downloads.PDFJSDownloadTarget())
            return

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

    def get_mhtml(self, tab, target):
        """Download the given tab as mhtml to the given target."""
        assert tab.backend == usertypes.Backend.QtWebEngine
        assert self._mhtml_target is None, self._mhtml_target
        self._mhtml_target = target
        tab.action.save_page()
