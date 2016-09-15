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

"""QtWebKit specific qute:* handlers and glue code."""

import mimetypes
import functools
import configparser

from PyQt5.QtCore import pyqtSlot, QObject
from PyQt5.QtNetwork import QNetworkReply

from qutebrowser.browser import pdfjs, qutescheme
from qutebrowser.browser.webkit.network import schemehandler, networkreply
from qutebrowser.utils import jinja, log, message, objreg, usertypes
from qutebrowser.config import configexc, configdata


class QuteSchemeHandler(schemehandler.SchemeHandler):

    """Scheme handler for qute: URLs."""

    def createRequest(self, _op, request, _outgoing_data):
        """Create a new request.

        Args:
             request: const QNetworkRequest & req
             _op: Operation op
             _outgoing_data: QIODevice * outgoingData

        Return:
            A QNetworkReply.
        """
        try:
            mimetype, data = qutescheme.data_for_url(request.url())
        except qutescheme.NoHandlerFound:
            errorstr = "No handler found for {}!".format(
                request.url().toDisplayString())
            return networkreply.ErrorNetworkReply(
                request, errorstr, QNetworkReply.ContentNotFoundError,
                self.parent())
        except qutescheme.QuteSchemeOSError as e:
            return networkreply.ErrorNetworkReply(
                request, str(e), QNetworkReply.ContentNotFoundError,
                self.parent())
        except qutescheme.QuteSchemeError as e:
            return networkreply.ErrorNetworkReply(request, e.errorstring,
                                                  e.error, self.parent())

        return networkreply.FixedDataNetworkReply(request, data, mimetype,
                                                  self.parent())


class JSBridge(QObject):

    """Javascript-bridge for special qute:... pages."""

    @pyqtSlot(str, str, str)
    def set(self, sectname, optname, value):
        """Slot to set a setting from qute:settings."""
        # https://github.com/The-Compiler/qutebrowser/issues/727
        if ((sectname, optname) == ('content', 'allow-javascript') and
                value == 'false'):
            message.error("Refusing to disable javascript via qute:settings "
                          "as it needs javascript support.")
            return
        try:
            objreg.get('config').set('conf', sectname, optname, value)
        except (configexc.Error, configparser.Error) as e:
            message.error(str(e))


@qutescheme.add_handler('settings', backend=usertypes.Backend.QtWebKit)
def qute_settings(_url):
    """Handler for qute:settings. View/change qute configuration."""
    config_getter = functools.partial(objreg.get('config').get, raw=True)
    html = jinja.render('settings.html', title='settings', config=configdata,
                        confget=config_getter)
    return 'text/html', html


@qutescheme.add_handler('pdfjs', backend=usertypes.Backend.QtWebKit)
def qute_pdfjs(url):
    """Handler for qute://pdfjs. Return the pdf.js viewer."""
    try:
        data = pdfjs.get_pdfjs_res(url.path())
    except pdfjs.PDFJSNotFound as e:
        # Logging as the error might get lost otherwise since we're not showing
        # the error page if a single asset is missing. This way we don't lose
        # information, as the failed pdfjs requests are still in the log.
        log.misc.warning(
            "pdfjs resource requested but not found: {}".format(e.path))
        raise qutescheme.QuteSchemeError("Can't find pdfjs resource "
                                         "'{}'".format(e.path),
                                         QNetworkReply.ContentNotFoundError)
    else:
        mimetype, _encoding = mimetypes.guess_type(url.fileName())
        assert mimetype is not None, url
        return mimetype, data
