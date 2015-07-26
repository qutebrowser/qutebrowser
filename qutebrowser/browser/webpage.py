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

"""The main browser widgets."""

import functools

from PyQt5.QtCore import (pyqtSlot, pyqtSignal, PYQT_VERSION, Qt, QUrl, QPoint,
                          QTimer)
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtNetwork import QNetworkReply, QNetworkRequest
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtPrintSupport import QPrintDialog
from PyQt5.QtWebKitWidgets import QWebPage

from qutebrowser.config import config
from qutebrowser.browser import http, tabhistory
from qutebrowser.browser.network import networkmanager
from qutebrowser.utils import (message, usertypes, log, jinja, qtutils, utils,
                               objreg, debug)


class BrowserPage(QWebPage):

    """Our own QWebPage with advanced features.

    Attributes:
        error_occurred: Whether an error occurred while loading.
        open_target: Where to open the next navigation request.
                     ("normal", "tab", "tab_bg")
        _hint_target: Override for open_target while hinting, or None.
        _extension_handlers: Mapping of QWebPage extensions to their handlers.
        _networkmanager: The NetworkManager used.
        _win_id: The window ID this BrowserPage is associated with.
        _ignore_load_started: Whether to ignore the next loadStarted signal.
        _is_shutting_down: Whether the page is currently shutting down.

    Signals:
        shutting_down: Emitted when the page is currently shutting down.
        reloading: Emitted before a web page reloads.
                   arg: The URL which gets reloaded.
    """

    shutting_down = pyqtSignal()
    reloading = pyqtSignal(QUrl)

    def __init__(self, win_id, tab_id, parent=None):
        super().__init__(parent)
        self._win_id = win_id
        self._is_shutting_down = False
        self._extension_handlers = {
            QWebPage.ErrorPageExtension: self._handle_errorpage,
            QWebPage.ChooseMultipleFilesExtension: self._handle_multiple_files,
        }
        self._ignore_load_started = False
        self.error_occurred = False
        self.open_target = usertypes.ClickTarget.normal
        self._hint_target = None
        self._networkmanager = networkmanager.NetworkManager(
            win_id, tab_id, self)
        self.setNetworkAccessManager(self._networkmanager)
        self.setForwardUnsupportedContent(True)
        self.reloading.connect(self._networkmanager.clear_rejected_ssl_errors)
        self.printRequested.connect(self.on_print_requested)
        self.downloadRequested.connect(self.on_download_requested)
        self.unsupportedContent.connect(self.on_unsupported_content)
        self.loadStarted.connect(self.on_load_started)
        self.featurePermissionRequested.connect(
            self.on_feature_permission_requested)
        self.saveFrameStateRequested.connect(
            self.on_save_frame_state_requested)
        self.restoreFrameStateRequested.connect(
            self.on_restore_frame_state_requested)

    if PYQT_VERSION > 0x050300:
        # WORKAROUND (remove this when we bump the requirements to 5.3.1)
        # We can't override javaScriptPrompt with older PyQt-versions because
        # of a bug in PyQt.
        # See http://www.riverbankcomputing.com/pipermail/pyqt/2014-June/034385.html

        def javaScriptPrompt(self, _frame, msg, default):
            """Override javaScriptPrompt to use the statusbar."""
            if (self._is_shutting_down or
                    config.get('content', 'ignore-javascript-prompt')):
                return (False, "")
            answer = self._ask("js: {}".format(msg), usertypes.PromptMode.text,
                               default)
            if answer is None:
                return (False, "")
            else:
                return (True, answer)

    def _handle_errorpage(self, info, errpage):
        """Display an error page if needed.

        Loosely based on Helpviewer/HelpBrowserWV.py from eric5
        (line 260 @ 5d937eb378dd)

        Args:
            info: The QWebPage.ErrorPageExtensionOption instance.
            errpage: The QWebPage.ErrorPageExtensionReturn instance, where the
                     error page will get written to.

        Return:
            False if no error page should be displayed, True otherwise.
        """
        ignored_errors = [
            (QWebPage.QtNetwork, QNetworkReply.OperationCanceledError),
            (QWebPage.WebKit, 203),  # "Loading is handled by the media engine"
        ]
        errpage.baseUrl = info.url
        urlstr = info.url.toDisplayString()
        if (info.domain, info.error) == (QWebPage.QtNetwork,
                                         QNetworkReply.ProtocolUnknownError):
            # For some reason, we get a segfault when we use
            # QDesktopServices::openUrl with info.url directly - however it
            # works when we construct a copy of it.
            url = QUrl(info.url)
            msg = "Open external application for {}-link?\nURL: {}".format(
                url.scheme(), url.toDisplayString())
            message.confirm_async(
                self._win_id, msg,
                functools.partial(QDesktopServices.openUrl, url))
            return True
        elif (info.domain, info.error) in ignored_errors:
            log.webview.debug("Ignored error on {}: {} (error domain: {}, "
                              "error code: {})".format(
                                  urlstr, info.errorString, info.domain,
                                  info.error))
            return False
        else:
            error_str = info.errorString
            if error_str == networkmanager.HOSTBLOCK_ERROR_STRING:
                # We don't set error_occurred in this case.
                error_str = "Request blocked by host blocker."
                main_frame = info.frame.page().mainFrame()
                if info.frame != main_frame:
                    # Content in an iframe -> Hide the frame so it doesn't use
                    # any space. We can't hide the frame's documentElement
                    # directly though.
                    for elem in main_frame.documentElement().findAll('iframe'):
                        if QUrl(elem.attribute('src')) == info.url:
                            elem.setAttribute('style', 'display: none')
                    return False
            else:
                self._ignore_load_started = True
                self.error_occurred = True
            log.webview.error("Error while loading {}: {}".format(
                urlstr, error_str))
            log.webview.debug("Error domain: {}, error code: {}".format(
                info.domain, info.error))
            title = "Error loading page: {}".format(urlstr)
            template = jinja.env.get_template('error.html')
            # pylint: disable=no-member
            # https://bitbucket.org/logilab/pylint/issue/490/
            html = template.render(
                title=title, url=urlstr, error=error_str, icon='')
            errpage.content = html.encode('utf-8')
            errpage.encoding = 'utf-8'
            return True

    def _handle_multiple_files(self, info, files):
        """Handle uploading of multiple files.

        Loosely based on Helpviewer/HelpBrowserWV.py from eric5.

        Args:
            info: The ChooseMultipleFilesExtensionOption instance.
            files: The ChooseMultipleFilesExtensionReturn instance to write
                   return values to.

        Return:
            True on success, the superclass return value on failure.
        """
        suggested_file = ""
        if info.suggestedFileNames:
            suggested_file = info.suggestedFileNames[0]
        files.fileNames, _ = QFileDialog.getOpenFileNames(None, None,
                                                          suggested_file)
        return True

    def _ask(self, text, mode, default=None):
        """Ask a blocking question in the statusbar.

        Args:
            text: The text to display to the user.
            mode: A PromptMode.
            default: The default value to display.

        Return:
            The answer the user gave or None if the prompt was cancelled.
        """
        q = usertypes.Question()
        q.text = text
        q.mode = mode
        q.default = default
        self.loadStarted.connect(q.abort)
        self.shutting_down.connect(q.abort)
        bridge = objreg.get('message-bridge', scope='window',
                            window=self._win_id)
        bridge.ask(q, blocking=True)
        q.deleteLater()
        return q.answer

    def shutdown(self):
        """Prepare the web page for being deleted."""
        self._is_shutting_down = True
        self.shutting_down.emit()
        download_manager = objreg.get('download-manager', scope='window',
                                      window=self._win_id)
        nam = self.networkAccessManager()
        if download_manager.has_downloads_with_nam(nam):
            nam.setParent(download_manager)
        else:
            nam.shutdown()

    def load_history(self, entries):
        """Load the history from a list of TabHistoryItem objects."""
        stream, _data, user_data = tabhistory.serialize(entries)
        history = self.history()
        qtutils.deserialize_stream(stream, history)
        for i, data in enumerate(user_data):
            history.itemAt(i).setUserData(data)
        cur_data = history.currentItem().userData()
        if cur_data is not None:
            frame = self.mainFrame()
            if 'zoom' in cur_data:
                frame.page().view().zoom_perc(cur_data['zoom'] * 100)
            if ('scroll-pos' in cur_data and
                    frame.scrollPosition() == QPoint(0, 0)):
                QTimer.singleShot(0, functools.partial(
                    frame.setScrollPosition, cur_data['scroll-pos']))

    def display_content(self, reply, mimetype):
        """Display a QNetworkReply with an explicitly set mimetype."""
        self.mainFrame().setContent(reply.readAll(), mimetype, reply.url())
        reply.deleteLater()

    def on_print_requested(self, frame):
        """Handle printing when requested via javascript."""
        if not qtutils.check_print_compat():
            message.error(self._win_id, "Printing on Qt < 5.3.0 on Windows is "
                          "broken, please upgrade!", immediately=True)
            return
        printdiag = QPrintDialog()
        printdiag.setAttribute(Qt.WA_DeleteOnClose)
        printdiag.open(lambda: frame.print(printdiag.printer()))

    @pyqtSlot('QNetworkRequest')
    def on_download_requested(self, request):
        """Called when the user wants to download a link.

        We need to construct a copy of the QNetworkRequest here as the
        download_manager needs it async and we'd get a segfault otherwise as
        soon as the user has entered the filename, as Qt seems to delete it
        after this slot returns.
        """
        req = QNetworkRequest(request)
        download_manager = objreg.get('download-manager', scope='window',
                                      window=self._win_id)
        download_manager.get_request(req, page=self)

    @pyqtSlot('QNetworkReply')
    def on_unsupported_content(self, reply):
        """Handle an unsupportedContent signal.

        Most likely this will mean we need to download the reply, but we
        correct for some common errors the server do.

        At some point we might want to implement the MIME Sniffing standard
        here: http://mimesniff.spec.whatwg.org/
        """
        inline, suggested_filename = http.parse_content_disposition(reply)
        download_manager = objreg.get('download-manager', scope='window',
                                      window=self._win_id)
        if not inline:
            # Content-Disposition: attachment -> force download
            download_manager.fetch(reply,
                                   suggested_filename=suggested_filename)
            return
        mimetype, _rest = http.parse_content_type(reply)
        if mimetype == 'image/jpg':
            # Some servers (e.g. the LinkedIn CDN) send a non-standard
            # image/jpg (instead of image/jpeg, defined in RFC 1341 section
            # 7.5). If this is the case, we force displaying with a corrected
            # mimetype.
            if reply.isFinished():
                self.display_content(reply, 'image/jpeg')
            else:
                reply.finished.connect(functools.partial(
                    self.display_content, reply, 'image/jpeg'))
        else:
            # Unknown mimetype, so download anyways.
            download_manager.fetch(reply,
                                   suggested_filename=suggested_filename)

    @pyqtSlot()
    def on_load_started(self):
        """Reset error_occurred when loading of a new page started."""
        if self._ignore_load_started:
            self._ignore_load_started = False
        else:
            self.error_occurred = False

    @pyqtSlot('QWebFrame', 'QWebPage::Feature')
    def on_feature_permission_requested(self, frame, feature):
        """Ask the user for approval for geolocation/notifications."""
        options = {
            QWebPage.Notifications: ('content', 'notifications'),
            QWebPage.Geolocation: ('content', 'geolocation'),
        }
        config_val = config.get(*options[feature])
        if config_val == 'ask':
            bridge = objreg.get('message-bridge', scope='window',
                                window=self._win_id)
            q = usertypes.Question(bridge)
            q.mode = usertypes.PromptMode.yesno

            msgs = {
                QWebPage.Notifications: 'show notifications',
                QWebPage.Geolocation: 'access your location',
            }

            host = frame.url().host()
            if host:
                q.text = "Allow the website at {} to {}?".format(
                    frame.url().host(), msgs[feature])
            else:
                q.text = "Allow the website to {}?".format(msgs[feature])

            yes_action = functools.partial(
                self.setFeaturePermission, frame, feature,
                QWebPage.PermissionGrantedByUser)
            q.answered_yes.connect(yes_action)

            no_action = functools.partial(
                self.setFeaturePermission, frame, feature,
                QWebPage.PermissionDeniedByUser)
            q.answered_no.connect(no_action)
            q.cancelled.connect(no_action)

            q.completed.connect(q.deleteLater)

            self.featurePermissionRequestCanceled.connect(functools.partial(
                self.on_feature_permission_cancelled, q, frame, feature))
            self.loadStarted.connect(q.abort)

            bridge.ask(q, blocking=False)
        elif config_val:
            self.setFeaturePermission(frame, feature,
                                      QWebPage.PermissionGrantedByUser)
        else:
            self.setFeaturePermission(frame, feature,
                                      QWebPage.PermissionDeniedByUser)

    def on_feature_permission_cancelled(self, question, frame, feature,
                                        cancelled_frame, cancelled_feature):
        """Slot invoked when a feature permission request was cancelled.

        To be used with functools.partial.
        """
        if frame is cancelled_frame and feature == cancelled_feature:
            try:
                question.abort()
            except RuntimeError:
                # The question could already be deleted, e.g. because it was
                # aborted after a loadStarted signal.
                pass

    def on_save_frame_state_requested(self, frame, item):
        """Save scroll position and zoom in history.

        Args:
            frame: The QWebFrame which gets saved.
            item: The QWebHistoryItem to be saved.
        """
        try:
            if frame != self.mainFrame():
                return
        except RuntimeError:
            # With Qt 5.2.1 (Ubuntu Trusty) we get this when closing a tab:
            #     RuntimeError: wrapped C/C++ object of type BrowserPage has
            #     been deleted
            # Since the information here isn't that important for closing web
            # views anyways, we ignore this error.
            return
        data = {
            'zoom': frame.zoomFactor(),
            'scroll-pos': frame.scrollPosition(),
        }
        item.setUserData(data)

    def on_restore_frame_state_requested(self, frame):
        """Restore scroll position and zoom from history.

        Args:
            frame: The QWebFrame which gets restored.
        """
        if frame != self.mainFrame():
            return
        data = self.history().currentItem().userData()
        if data is None:
            return
        if 'zoom' in data:
            frame.page().view().zoom_perc(data['zoom'] * 100)
        if 'scroll-pos' in data and frame.scrollPosition() == QPoint(0, 0):
            frame.setScrollPosition(data['scroll-pos'])

    @pyqtSlot(str)
    def on_start_hinting(self, hint_target):
        """Emitted before a hinting-click takes place.

        Args:
            hint_target: A ClickTarget member to set self._hint_target to.
        """
        log.webview.debug("Setting force target to {}".format(hint_target))
        self._hint_target = hint_target

    @pyqtSlot()
    def on_stop_hinting(self):
        """Emitted when hinting is finished."""
        log.webview.debug("Finishing hinting.")
        self._hint_target = None

    def userAgentForUrl(self, url):
        """Override QWebPage::userAgentForUrl to customize the user agent."""
        ua = config.get('network', 'user-agent')
        if ua is None:
            return super().userAgentForUrl(url)
        else:
            return ua

    def supportsExtension(self, ext):
        """Override QWebPage::supportsExtension to provide error pages.

        Args:
            ext: The extension to check for.

        Return:
            True if the extension can be handled, False otherwise.
        """
        return ext in self._extension_handlers

    # WORKAROUND for:
    # http://www.riverbankcomputing.com/pipermail/pyqt/2014-August/034722.html
    @utils.prevent_exceptions(False, PYQT_VERSION < 0x50302)
    def extension(self, ext, opt, out):
        """Override QWebPage::extension to provide error pages.

        Args:
            ext: The extension.
            opt: Extension options instance.
            out: Extension output instance.

        Return:
            Handler return value.
        """
        try:
            handler = self._extension_handlers[ext]
        except KeyError:
            log.webview.warning("Extension {} not supported!".format(ext))
            return super().extension(ext, opt, out)
        return handler(opt, out)

    def javaScriptAlert(self, frame, msg):
        """Override javaScriptAlert to use the statusbar."""
        log.js.debug("alert: {}".format(msg))
        if config.get('ui', 'modal-js-dialog'):
            return super().javaScriptAlert(frame, msg)

        if (self._is_shutting_down or
                config.get('content', 'ignore-javascript-alert')):
            return
        self._ask("[js alert] {}".format(msg), usertypes.PromptMode.alert)

    def javaScriptConfirm(self, frame, msg):
        """Override javaScriptConfirm to use the statusbar."""
        log.js.debug("confirm: {}".format(msg))
        if config.get('ui', 'modal-js-dialog'):
            return super().javaScriptConfirm(frame, msg)

        if self._is_shutting_down:
            return False
        ans = self._ask("[js confirm] {}".format(msg),
                        usertypes.PromptMode.yesno)
        return bool(ans)

    def javaScriptConsoleMessage(self, msg, line, source):
        """Override javaScriptConsoleMessage to use debug log."""
        if config.get('general', 'log-javascript-console'):
            log.js.debug("[{}:{}] {}".format(source, line, msg))

    def chooseFile(self, _frame, suggested_file):
        """Override QWebPage's chooseFile to be able to chose a file to upload.

        Args:
            frame: The parent QWebFrame.
            suggested_file: A suggested filename.
        """
        filename, _ = QFileDialog.getOpenFileName(None, None, suggested_file)
        return filename

    def shouldInterruptJavaScript(self):
        """Override shouldInterruptJavaScript to use the statusbar."""
        answer = self._ask("Interrupt long-running javascript?",
                           usertypes.PromptMode.yesno)
        if answer is None:
            answer = True
        return answer

    def acceptNavigationRequest(self, _frame, request, typ):
        """Override acceptNavigationRequest to handle clicked links.

        Setting linkDelegationPolicy to DelegateAllLinks and using a slot bound
        to linkClicked won't work correctly, because when in a frameset, we
        have no idea in which frame the link should be opened.

        Checks if it should open it in a tab (middle-click or control) or not,
        and then opens the URL.

        Args:
            _frame: QWebFrame (target frame)
            request: QNetworkRequest
            typ: QWebPage::NavigationType
        """
        url = request.url()
        urlstr = url.toDisplayString()
        if typ == QWebPage.NavigationTypeReload:
            self.reloading.emit(url)
        if typ != QWebPage.NavigationTypeLinkClicked:
            return True
        if not url.isValid():
            message.error(self._win_id, "Invalid link {} clicked!".format(
                urlstr))
            log.webview.debug(url.errorString())
            self.open_target = usertypes.ClickTarget.normal
            return False
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=self._win_id)
        log.webview.debug("acceptNavigationRequest, url {}, type {}, hint "
                          "target {}, open_target {}".format(
                              urlstr, debug.qenum_key(QWebPage, typ),
                              self._hint_target, self.open_target))
        if self._hint_target is not None:
            target = self._hint_target
        else:
            target = self.open_target
        self.open_target = usertypes.ClickTarget.normal
        if target == usertypes.ClickTarget.tab:
            tabbed_browser.tabopen(url, False)
            return False
        elif target == usertypes.ClickTarget.tab_bg:
            tabbed_browser.tabopen(url, True)
            return False
        elif target == usertypes.ClickTarget.window:
            from qutebrowser.mainwindow import mainwindow
            window = mainwindow.MainWindow()
            window.show()
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=window.win_id)
            tabbed_browser.tabopen(url, False)
            return False
        else:
            return True
