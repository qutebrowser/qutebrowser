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

"""The main browser widgets."""

import sip
from PyQt5.QtCore import (QCoreApplication, pyqtSignal, pyqtSlot, PYQT_VERSION,
                          Qt)
from PyQt5.QtNetwork import QNetworkReply
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtPrintSupport import QPrintDialog
from PyQt5.QtWebKitWidgets import QWebPage

import qutebrowser.utils.message as message
import qutebrowser.utils.url as urlutils
import qutebrowser.config.config as config
import qutebrowser.utils.log as log
from qutebrowser.utils.misc import read_file, check_print_compat
from qutebrowser.utils.usertypes import PromptMode


class BrowserPage(QWebPage):

    """Our own QWebPage with advanced features.

    Attributes:
        _extension_handlers: Mapping of QWebPage extensions to their handlers.
        network_access_manager: The QNetworkAccessManager used.

    Signals:
        start_download: Emitted when a file should be downloaded.
    """

    start_download = pyqtSignal('QNetworkReply*')

    def __init__(self, parent=None):
        super().__init__(parent)
        self._extension_handlers = {
            QWebPage.ErrorPageExtension: self._handle_errorpage,
            QWebPage.ChooseMultipleFilesExtension: self._handle_multiple_files,
        }
        self.setNetworkAccessManager(
            QCoreApplication.instance().networkmanager)
        self.setForwardUnsupportedContent(True)
        self.printRequested.connect(self.on_print_requested)
        self.downloadRequested.connect(self.on_download_requested)

        if PYQT_VERSION > 0x050300:
            # This breaks in <= 5.3.0, but in anything later it hopefully
            # works.
            # FIXME confirm this as soon as 5.3.1 is out!
            # pylint: disable=invalid-name
            self.javaScriptPrompt = self._javascript_prompt

    def _javascript_prompt(self, _frame, msg, default):
        """Override javaScriptPrompt to use the statusbar.

        We use this approach and override the method conditionally in __init__
        because overriding javaScriptPrompt was broken in 5.3.0.

        http://www.riverbankcomputing.com/pipermail/pyqt/2014-June/034385.html
        """
        answer = message.modular_question(
            "js: {}".format(msg), PromptMode.text, default)
        if answer is None:
            return (False, "")
        else:
            return (True, answer)

    def _handle_errorpage(self, opt, out):
        """Display an error page if needed.

        Loosly based on Helpviewer/HelpBrowserWV.py from eric5
        (line 260 @ 5d937eb378dd)

        Args:
            opt: The QWebPage.ErrorPageExtensionOption instance.
            out: The QWebPage.ErrorPageExtensionReturn instance to write return
                 values to.

        Return:
            False if no error page should be displayed, True otherwise.
        """
        ignored_errors = [
            (QWebPage.QtNetwork, QNetworkReply.OperationCanceledError),
            (QWebPage.WebKit, 203),  # "Loading is handled by the media engine"
        ]
        info = sip.cast(opt, QWebPage.ErrorPageExtensionOption)
        errpage = sip.cast(out, QWebPage.ErrorPageExtensionReturn)
        errpage.baseUrl = info.url
        urlstr = urlutils.urlstring(info.url)
        if (info.domain, info.error) in ignored_errors:
            log.webview.debug("Ignored error on {}: {} (error domain: {}, "
                              "error code: {})".format(
                                  urlstr, info.errorString, info.domain,
                                  info.error))
            return False
        log.webview.error("Error while loading {}: {}".format(
            urlstr, info.errorString))
        log.webview.debug("Error domain: {}, error code: {}".format(
            info.domain, info.error))
        title = "Error loading page: {}".format(urlstr)
        errpage.content = read_file('html/error.html').format(
            title=title, url=urlstr, error=info.errorString, icon='')
        return True

    def _handle_multiple_files(self, opt, files):
        """Handle uploading of multiple files.

        Loosly based on Helpviewer/HelpBrowserWV.py from eric5.

        Args:
            opt: The ChooseMultipleFilesExtensionOption instance.
            files: The ChooseMultipleFilesExtensionReturn instance to write
                   return values to.

        Return:
            True on success, the superclass return value on failure.
        """
        info = sip.cast(opt, QWebPage.ChooseMultipleFilesExtensionOption)
        files = sip.cast(files, QWebPage.ChooseMultipleFilesExtensionReturn)
        if info is None or files is None:
            return super().extension(QWebPage.ChooseMultipleFilesExtension,
                                     opt, files)
        suggested_file = ""
        if opt.suggestedFileNames:
            suggested_file = opt.suggestedFileNames[0]
        files.fileNames, _ = QFileDialog.getOpenFileNames(None, None,
                                                          suggested_file)
        return True

    def on_print_requested(self, frame):
        """Handle printing when requested via javascript."""
        if not check_print_compat():
            message.error("Printing on Qt < 5.3.0 on Windows is broken, "
                          "please upgrade!")
            return
        printdiag = QPrintDialog()
        printdiag.setAttribute(Qt.WA_DeleteOnClose)
        printdiag.open(lambda: frame.print(printdiag.printer()))

    @pyqtSlot('QNetworkRequest')
    def on_download_requested(self, request):
        """Called when the user wants to download a link.

        Emit:
            start_download: Emitted with the QNetworkReply associated with the
                            passed request.
        """
        from qutebrowser.utils.debug import set_trace; set_trace()
        reply = self.networkAccessManager().get(request)
        self.start_download.emit(reply)

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
            return super().extension(ext, opt, out)
        return handler(opt, out)

    def javaScriptAlert(self, _frame, msg):
        """Override javaScriptAlert to use the statusbar."""
        message.modular_question("js: {}".format(msg), PromptMode.alert)

    def javaScriptConfirm(self, _frame, msg):
        """Override javaScriptConfirm to use the statusbar."""
        ans = message.modular_question("js: {}".format(msg), PromptMode.yesno)
        return bool(ans)

    def javaScriptConsoleMessage(self, msg, line, source):
        """Override javaScriptConsoleMessage to use debug log."""
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
        answer = message.modular_question("Interrupt long-running javascript?",
                                          PromptMode.yesno)
        if answer is None:
            answer = True
        return answer
