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
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtNetwork import QNetworkReply
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWebKitWidgets import QWebPage

import qutebrowser.utils.message as message
import qutebrowser.utils.url as urlutils
import qutebrowser.config.config as config
import qutebrowser.utils.log as log
from qutebrowser.utils.misc import read_file
from qutebrowser.utils.usertypes import PromptMode


class BrowserPage(QWebPage):

    """Our own QWebPage with advanced features.

    Attributes:
        _extension_handlers: Mapping of QWebPage extensions to their handlers.
        network_access_manager: The QNetworkAccessManager used.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._extension_handlers = {
            QWebPage.ErrorPageExtension: self._handle_errorpage,
            QWebPage.ChooseMultipleFilesExtension: self._handle_multiple_files,
        }
        self.setNetworkAccessManager(
            QCoreApplication.instance().networkmanager)

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
        return message.modular_question("js: {}".format(msg), PromptMode.yesno)

    def javaScriptConsoleMessage(self, msg, line, source):
        """Override javaScriptConsoleMessage to use debug log."""
        log.js.debug("[{}:{}] {}".format(source, line, msg))

    def javaScriptPrompt(self, _frame, msg, default):
        """Override javaScriptConfirm to use the statusbar."""
        answer = message.modular_question(
            "js: {}".format(msg), PromptMode.text, default)
        if answer is None:
            return (False, "")
        else:
            return (True, answer)

    def chooseFile(self, _frame, suggested_file):
        """Override QWebPage's chooseFile to be able to chose a file to upload.

        Args:
            frame: The parent QWebFrame.
            suggested_file: A suggested filename.
        """
        filename, _ = QFileDialog.getOpenFileName(None, None, suggested_file)
        return filename
