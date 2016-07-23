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

"""Handler functions for different qute:... pages.

Module attributes:
    pyeval_output: The output of the last :pyeval command.
"""

import functools
import configparser
import mimetypes
import urllib.parse

from PyQt5.QtCore import pyqtSlot, QObject
from PyQt5.QtNetwork import QNetworkReply

import qutebrowser
from qutebrowser.browser import pdfjs
from qutebrowser.browser.webkit.network import schemehandler, networkreply
from qutebrowser.utils import (version, utils, jinja, log, message, docutils,
                               objreg)
from qutebrowser.config import configexc, configdata


pyeval_output = ":pyeval was never called"


HANDLERS = {}


def add_handler(name):
    """Add a handler to the qute: scheme."""
    def namedecorator(function):
        HANDLERS[name] = function
        return function
    return namedecorator


class QuteSchemeError(Exception):

    """Exception to signal that a handler should return an ErrorReply.

    Attributes correspond to the arguments in
    networkreply.ErrorNetworkReply.

    Attributes:
        errorstring: Error string to print.
        error: Numerical error value.
    """

    def __init__(self, errorstring, error):
        """Constructor."""
        self.errorstring = errorstring
        self.error = error
        super().__init__(errorstring)


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
        path = request.url().path()
        host = request.url().host()
        # A url like "qute:foo" is split as "scheme:path", not "scheme:host".
        log.misc.debug("url: {}, path: {}, host {}".format(
            request.url().toDisplayString(), path, host))
        try:
            handler = HANDLERS[path]
        except KeyError:
            try:
                handler = HANDLERS[host]
            except KeyError:
                errorstr = "No handler found for {}!".format(
                    request.url().toDisplayString())
                return networkreply.ErrorNetworkReply(
                    request, errorstr, QNetworkReply.ContentNotFoundError,
                    self.parent())
        try:
            data = handler(self._win_id, request)
        except OSError as e:
            return networkreply.ErrorNetworkReply(
                request, str(e), QNetworkReply.ContentNotFoundError,
                self.parent())
        except QuteSchemeError as e:
            return networkreply.ErrorNetworkReply(request, e.errorstring,
                                                  e.error, self.parent())
        mimetype, _encoding = mimetypes.guess_type(request.url().fileName())
        if mimetype is None:
            mimetype = 'text/html'
        return networkreply.FixedDataNetworkReply(request, data, mimetype,
                                                  self.parent())


class JSBridge(QObject):

    """Javascript-bridge for special qute:... pages."""

    @pyqtSlot(int, str, str, str)
    def set(self, win_id, sectname, optname, value):
        """Slot to set a setting from qute:settings."""
        # https://github.com/The-Compiler/qutebrowser/issues/727
        if ((sectname, optname) == ('content', 'allow-javascript') and
                value == 'false'):
            message.error(win_id, "Refusing to disable javascript via "
                          "qute:settings as it needs javascript support.")
            return
        try:
            objreg.get('config').set('conf', sectname, optname, value)
        except (configexc.Error, configparser.Error) as e:
            message.error(win_id, e)


@add_handler('pyeval')
def qute_pyeval(_win_id, _request):
    """Handler for qute:pyeval. Return HTML content as bytes."""
    html = jinja.render('pre.html', title='pyeval', content=pyeval_output)
    return html.encode('UTF-8', errors='xmlcharrefreplace')


@add_handler('version')
@add_handler('verizon')
def qute_version(_win_id, _request):
    """Handler for qute:version. Return HTML content as bytes."""
    html = jinja.render('version.html', title='Version info',
                        version=version.version(),
                        copyright=qutebrowser.__copyright__)
    return html.encode('UTF-8', errors='xmlcharrefreplace')


@add_handler('plainlog')
def qute_plainlog(_win_id, request):
    """Handler for qute:plainlog. Return HTML content as bytes.

    An optional query parameter specifies the minimum log level to print.
    For example, qute://log?level=warning prints warnings and errors.
    Level can be one of: vdebug, debug, info, warning, error, critical.
    """
    if log.ram_handler is None:
        text = "Log output was disabled."
    else:
        try:
            level = urllib.parse.parse_qs(request.url().query())['level'][0]
        except KeyError:
            level = 'vdebug'
        text = log.ram_handler.dump_log(html=False, level=level)
    html = jinja.render('pre.html', title='log', content=text)
    return html.encode('UTF-8', errors='xmlcharrefreplace')


@add_handler('log')
def qute_log(_win_id, request):
    """Handler for qute:log. Return HTML content as bytes.

    An optional query parameter specifies the minimum log level to print.
    For example, qute://log?level=warning prints warnings and errors.
    Level can be one of: vdebug, debug, info, warning, error, critical.
    """
    if log.ram_handler is None:
        html_log = None
    else:
        try:
            level = urllib.parse.parse_qs(request.url().query())['level'][0]
        except KeyError:
            level = 'vdebug'
        html_log = log.ram_handler.dump_log(html=True, level=level)

    html = jinja.render('log.html', title='log', content=html_log)
    return html.encode('UTF-8', errors='xmlcharrefreplace')


@add_handler('gpl')
def qute_gpl(_win_id, _request):
    """Handler for qute:gpl. Return HTML content as bytes."""
    return utils.read_file('html/COPYING.html').encode('ASCII')


@add_handler('help')
def qute_help(win_id, request):
    """Handler for qute:help. Return HTML content as bytes."""
    try:
        utils.read_file('html/doc/index.html')
    except OSError:
        html = jinja.render(
            'error.html',
            title="Error while loading documentation",
            url=request.url().toDisplayString(),
            error="This most likely means the documentation was not generated "
                  "properly. If you are running qutebrowser from the git "
                  "repository, please run scripts/asciidoc2html.py. "
                  "If you're running a released version this is a bug, please "
                  "use :report to report it.",
            icon='')
        return html.encode('UTF-8', errors='xmlcharrefreplace')
    urlpath = request.url().path()
    if not urlpath or urlpath == '/':
        urlpath = 'index.html'
    else:
        urlpath = urlpath.lstrip('/')
    if not docutils.docs_up_to_date(urlpath):
        message.error(win_id, "Your documentation is outdated! Please re-run "
                      "scripts/asciidoc2html.py.")
    path = 'html/doc/{}'.format(urlpath)
    if urlpath.endswith('.png'):
        return utils.read_file(path, binary=True)
    else:
        data = utils.read_file(path)
        return data.encode('UTF-8', errors='xmlcharrefreplace')


@add_handler('settings')
def qute_settings(win_id, _request):
    """Handler for qute:settings. View/change qute configuration."""
    config_getter = functools.partial(objreg.get('config').get, raw=True)
    html = jinja.render('settings.html', win_id=win_id, title='settings',
                        config=configdata, confget=config_getter)
    return html.encode('UTF-8', errors='xmlcharrefreplace')


@add_handler('pdfjs')
def qute_pdfjs(_win_id, request):
    """Handler for qute://pdfjs. Return the pdf.js viewer."""
    urlpath = request.url().path()
    try:
        return pdfjs.get_pdfjs_res(urlpath)
    except pdfjs.PDFJSNotFound as e:
        # Logging as the error might get lost otherwise since we're not showing
        # the error page if a single asset is missing. This way we don't lose
        # information, as the failed pdfjs requests are still in the log.
        log.misc.warning(
            "pdfjs resource requested but not found: {}".format(e.path))
        raise QuteSchemeError("Can't find pdfjs resource '{}'".format(e.path),
                              QNetworkReply.ContentNotFoundError)


@add_handler('bookmarks')
def qute_bookmarks(_win_id, _request):
    """Handler for qute:bookmarks. Display all quickmarks / bookmarks."""
    bookmarks = sorted(objreg.get('bookmark-manager').marks.items(),
                       key=lambda x: x[1])  # Sort by title
    quickmarks = sorted(objreg.get('quickmark-manager').marks.items(),
                        key=lambda x: x[0])  # Sort by name

    html = jinja.render('bookmarks.html',
                        title='Bookmarks',
                        bookmarks=bookmarks,
                        quickmarks=quickmarks)
    return html.encode('UTF-8', errors='xmlcharrefreplace')
