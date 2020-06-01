# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Backend-independent qute://* code.

Module attributes:
    pyeval_output: The output of the last :pyeval command.
    _HANDLERS: The handlers registered via decorators.
"""

import html
import json
import os
import time
import textwrap
import urllib
import collections
import base64
import typing
from typing import TypeVar, Callable, Union, Tuple

try:
    import secrets
except ImportError:
    # New in Python 3.6
    secrets = None  # type: ignore[assignment]

from PyQt5.QtCore import QUrlQuery, QUrl, qVersion

import qutebrowser
from qutebrowser.browser import pdfjs, downloads, history
from qutebrowser.config import config, configdata, configexc, configdiff
from qutebrowser.utils import (version, utils, jinja, log, message, docutils,
                               objreg, urlutils, standarddir)
from qutebrowser.qt import sip


pyeval_output = ":pyeval was never called"
spawn_output = ":spawn was never called"
csrf_token = None


_HANDLERS = {}


class Error(Exception):

    """Exception for generic errors on a qute:// page."""


class NotFoundError(Error):

    """Raised when the given URL was not found."""


class SchemeOSError(Error):

    """Raised when there was an OSError inside a handler."""


class UrlInvalidError(Error):

    """Raised when an invalid URL was opened."""


class RequestDeniedError(Error):

    """Raised when the request is forbidden."""


class Redirect(Exception):

    """Exception to signal a redirect should happen.

    Attributes:
        url: The URL to redirect to, as a QUrl.
    """

    def __init__(self, url: QUrl):
        super().__init__(url.toDisplayString())
        self.url = url


# Return value: (mimetype, data) (encoded as utf-8 if a str is returned)
_HandlerRet = Tuple[str, Union[str, bytes]]
_Handler = TypeVar('_Handler', bound=Callable[[QUrl], _HandlerRet])


class add_handler:  # noqa: N801,N806 pylint: disable=invalid-name

    """Decorator to register a qute://* URL handler.

    Attributes:
        _name: The 'foo' part of qute://foo
    """

    def __init__(self, name):
        self._name = name
        self._function = None  # type: typing.Optional[typing.Callable]

    def __call__(self, function: _Handler) -> _Handler:
        self._function = function
        _HANDLERS[self._name] = self.wrapper
        return function

    def wrapper(self, *args, **kwargs):
        """Call the underlying function."""
        assert self._function is not None
        return self._function(*args, **kwargs)


def data_for_url(url: QUrl) -> typing.Tuple[str, bytes]:
    """Get the data to show for the given URL.

    Args:
        url: The QUrl to show.

    Return:
        A (mimetype, data) tuple.
    """
    norm_url = url.adjusted(
        QUrl.NormalizePathSegments |  # type: ignore[arg-type]
        QUrl.StripTrailingSlash)
    if norm_url != url:
        raise Redirect(norm_url)

    path = url.path()
    host = url.host()
    query = urlutils.query_string(url)
    # A url like "qute:foo" is split as "scheme:path", not "scheme:host".
    log.misc.debug("url: {}, path: {}, host {}".format(
        url.toDisplayString(), path, host))
    if not path or not host:
        new_url = QUrl()
        new_url.setScheme('qute')
        # When path is absent, e.g. qute://help (with no trailing slash)
        if host:
            new_url.setHost(host)
        # When host is absent, e.g. qute:help
        else:
            new_url.setHost(path)

        new_url.setPath('/')
        if query:
            new_url.setQuery(query)
        if new_url.host():  # path was a valid host
            raise Redirect(new_url)

    try:
        handler = _HANDLERS[host]
    except KeyError:
        raise NotFoundError("No handler found for {}".format(
            url.toDisplayString()))

    try:
        mimetype, data = handler(url)
    except OSError as e:
        raise SchemeOSError(e)

    assert mimetype is not None, url
    if mimetype == 'text/html' and isinstance(data, str):
        # We let handlers return HTML as text
        data = data.encode('utf-8', errors='xmlcharrefreplace')

    return mimetype, data


@add_handler('bookmarks')
def qute_bookmarks(_url: QUrl) -> _HandlerRet:
    """Handler for qute://bookmarks. Display all quickmarks / bookmarks."""
    bookmarks = sorted(objreg.get('bookmark-manager').marks.items(),
                       key=lambda x: x[1])  # Sort by title
    quickmarks = sorted(objreg.get('quickmark-manager').marks.items(),
                        key=lambda x: x[0])  # Sort by name

    src = jinja.render('bookmarks.html',
                       title='Bookmarks',
                       bookmarks=bookmarks,
                       quickmarks=quickmarks)
    return 'text/html', src


@add_handler('tabs')
def qute_tabs(_url: QUrl) -> _HandlerRet:
    """Handler for qute://tabs. Display information about all open tabs."""
    tabs = collections.defaultdict(
        list)  # type: typing.Dict[str, typing.List[typing.Tuple[str, str]]]
    for win_id, window in objreg.window_registry.items():
        if sip.isdeleted(window):
            continue
        tabbed_browser = objreg.get('tabbed-browser',
                                    scope='window',
                                    window=win_id)
        for tab in tabbed_browser.widgets():
            if tab.url() not in [QUrl("qute://tabs/"), QUrl("qute://tabs")]:
                urlstr = tab.url().toDisplayString()
                tabs[str(win_id)].append((tab.title(), urlstr))

    src = jinja.render('tabs.html',
                       title='Tabs',
                       tab_list_by_window=tabs)
    return 'text/html', src


def history_data(
        start_time: float,
        offset: int = None
) -> typing.Sequence[typing.Dict[str, typing.Union[str, int]]]:
    """Return history data.

    Arguments:
        start_time: select history starting from this timestamp.
        offset: number of items to skip
    """
    # history atimes are stored as ints, ensure start_time is not a float
    start_time = int(start_time)
    if offset is not None:
        entries = history.web_history.entries_before(start_time, limit=1000,
                                                     offset=offset)
    else:
        # end is 24hrs earlier than start
        end_time = start_time - 24*60*60
        entries = history.web_history.entries_between(end_time, start_time)

    return [{"url": e.url,
             "title": html.escape(e.title) or html.escape(e.url),
             "time": e.atime} for e in entries]


@add_handler('history')
def qute_history(url: QUrl) -> _HandlerRet:
    """Handler for qute://history. Display and serve history."""
    if url.path() == '/data':
        q_offset = QUrlQuery(url).queryItemValue("offset")
        try:
            offset = int(q_offset) if q_offset else None
        except ValueError:
            raise UrlInvalidError("Query parameter offset is invalid")

        # Use start_time in query or current time.
        q_start_time = QUrlQuery(url).queryItemValue("start_time")
        try:
            start_time = float(q_start_time) if q_start_time else time.time()
        except ValueError:
            raise UrlInvalidError("Query parameter start_time is invalid")

        return 'text/html', json.dumps(history_data(start_time, offset))
    else:
        return 'text/html', jinja.render(
            'history.html',
            title='History',
            gap_interval=config.val.history_gap_interval
        )


@add_handler('javascript')
def qute_javascript(url: QUrl) -> _HandlerRet:
    """Handler for qute://javascript.

    Return content of file given as query parameter.
    """
    path = url.path()
    if path:
        path = "javascript" + os.sep.join(path.split('/'))
        return 'text/html', utils.read_file(path, binary=False)
    else:
        raise UrlInvalidError("No file specified")


@add_handler('pyeval')
def qute_pyeval(_url: QUrl) -> _HandlerRet:
    """Handler for qute://pyeval."""
    src = jinja.render('pre.html', title='pyeval', content=pyeval_output)
    return 'text/html', src


@add_handler('spawn-output')
def qute_spawn_output(_url: QUrl) -> _HandlerRet:
    """Handler for qute://spawn-output."""
    src = jinja.render('pre.html', title='spawn output', content=spawn_output)
    return 'text/html', src


@add_handler('version')
@add_handler('verizon')
def qute_version(_url):
    """Handler for qute://version."""
    src = jinja.render('version.html', title='Version info',
                       version=version.version_info(),
                       copyright=qutebrowser.__copyright__)
    return 'text/html', src


@add_handler('plainlog')
def qute_plainlog(url: QUrl) -> _HandlerRet:
    """Handler for qute://plainlog.

    An optional query parameter specifies the minimum log level to print.
    For example, qute://log?level=warning prints warnings and errors.
    Level can be one of: vdebug, debug, info, warning, error, critical.
    """
    if log.ram_handler is None:
        text = "Log output was disabled."
    else:
        level = QUrlQuery(url).queryItemValue('level')
        if not level:
            level = 'vdebug'
        text = log.ram_handler.dump_log(html=False, level=level)
    src = jinja.render('pre.html', title='log', content=text)
    return 'text/html', src


@add_handler('log')
def qute_log(url: QUrl) -> _HandlerRet:
    """Handler for qute://log.

    An optional query parameter specifies the minimum log level to print.
    For example, qute://log?level=warning prints warnings and errors.
    Level can be one of: vdebug, debug, info, warning, error, critical.
    """
    if log.ram_handler is None:
        html_log = None
    else:
        level = QUrlQuery(url).queryItemValue('level')
        if not level:
            level = 'vdebug'
        html_log = log.ram_handler.dump_log(html=True, level=level)

    src = jinja.render('log.html', title='log', content=html_log)
    return 'text/html', src


@add_handler('gpl')
def qute_gpl(_url: QUrl) -> _HandlerRet:
    """Handler for qute://gpl. Return HTML content as string."""
    return 'text/html', utils.read_file('html/license.html')


def _asciidoc_fallback_path(html_path: str) -> typing.Optional[str]:
    """Fall back to plaintext asciidoc if the HTML is unavailable."""
    path = html_path.replace('.html', '.asciidoc')
    try:
        return utils.read_file(path)
    except OSError:
        return None


@add_handler('help')
def qute_help(url: QUrl) -> _HandlerRet:
    """Handler for qute://help."""
    urlpath = url.path()
    if not urlpath or urlpath == '/':
        urlpath = 'index.html'
    else:
        urlpath = urlpath.lstrip('/')
    if not docutils.docs_up_to_date(urlpath):
        message.error("Your documentation is outdated! Please re-run "
                      "scripts/asciidoc2html.py.")

    path = 'html/doc/{}'.format(urlpath)
    if not urlpath.endswith('.html'):
        try:
            bdata = utils.read_file(path, binary=True)
        except OSError as e:
            raise SchemeOSError(e)
        mimetype = utils.guess_mimetype(urlpath)
        return mimetype, bdata

    try:
        data = utils.read_file(path)
    except OSError:
        asciidoc = _asciidoc_fallback_path(path)

        if asciidoc is None:
            raise

        preamble = textwrap.dedent("""
            There was an error loading the documentation!

            This most likely means the documentation was not generated
            properly. If you are running qutebrowser from the git repository,
            please (re)run scripts/asciidoc2html.py and reload this page.

            If you're running a released version this is a bug, please use
            :report to report it.

            Falling back to the plaintext version.

            ---------------------------------------------------------------


        """)
        return 'text/plain', (preamble + asciidoc).encode('utf-8')
    else:
        return 'text/html', data


def _qute_settings_set(url: QUrl) -> _HandlerRet:
    """Handler for qute://settings/set."""
    query = QUrlQuery(url)
    option = query.queryItemValue('option', QUrl.FullyDecoded)
    value = query.queryItemValue('value', QUrl.FullyDecoded)

    # https://github.com/qutebrowser/qutebrowser/issues/727
    if option == 'content.javascript.enabled' and value == 'false':
        msg = ("Refusing to disable javascript via qute://settings "
               "as it needs javascript support.")
        message.error(msg)
        return 'text/html', b'error: ' + msg.encode('utf-8')

    try:
        config.instance.set_str(option, value, save_yaml=True)
        return 'text/html', b'ok'
    except configexc.Error as e:
        message.error(str(e))
        return 'text/html', b'error: ' + str(e).encode('utf-8')


@add_handler('settings')
def qute_settings(url: QUrl) -> _HandlerRet:
    """Handler for qute://settings. View/change qute configuration."""
    global csrf_token

    if url.path() == '/set':
        if url.password() != csrf_token:
            message.error("Invalid CSRF token for qute://settings!")
            raise RequestDeniedError("Invalid CSRF token!")
        return _qute_settings_set(url)

    # Requests to qute://settings/set should only be allowed from
    # qute://settings. As an additional security precaution, we generate a CSRF
    # token to use here.
    if secrets:
        csrf_token = secrets.token_urlsafe()
    else:
        # On Python < 3.6, from secrets.py
        token = base64.urlsafe_b64encode(os.urandom(32))
        csrf_token = token.rstrip(b'=').decode('ascii')

    src = jinja.render('settings.html', title='settings',
                       configdata=configdata,
                       confget=config.instance.get_str,
                       csrf_token=csrf_token)
    return 'text/html', src


@add_handler('bindings')
def qute_bindings(_url: QUrl) -> _HandlerRet:
    """Handler for qute://bindings. View keybindings."""
    bindings = {}
    defaults = config.val.bindings.default

    config_modes = set(defaults.keys()).union(config.val.bindings.commands)
    config_modes.remove('normal')

    modes = ['normal'] + sorted(config_modes)
    for mode in modes:
        bindings[mode] = config.key_instance.get_bindings_for(mode)

    src = jinja.render('bindings.html', title='Bindings',
                       bindings=bindings)
    return 'text/html', src


@add_handler('back')
def qute_back(url: QUrl) -> _HandlerRet:
    """Handler for qute://back.

    Simple page to free ram / lazy load a site, goes back on focusing the tab.
    """
    src = jinja.render(
        'back.html',
        title='Suspended: ' + urllib.parse.unquote(url.fragment()))
    return 'text/html', src


@add_handler('configdiff')
def qute_configdiff(url: QUrl) -> _HandlerRet:
    """Handler for qute://configdiff."""
    if url.path() == '/old':
        try:
            return 'text/html', configdiff.get_diff()
        except OSError as e:
            error = (b'Failed to read old config: ' +
                     str(e.strerror).encode('utf-8'))
            return 'text/plain', error
    else:
        data = config.instance.dump_userconfig().encode('utf-8')
        return 'text/plain', data


@add_handler('pastebin-version')
def qute_pastebin_version(_url: QUrl) -> _HandlerRet:
    """Handler that pastebins the version string."""
    version.pastebin_version()
    return 'text/plain', b'Paste called.'


def _pdf_path(filename: str) -> str:
    """Get the path of a temporary PDF file."""
    return os.path.join(downloads.temp_download_manager.get_tmpdir().name,
                        filename)


@add_handler('pdfjs')
def qute_pdfjs(url: QUrl) -> _HandlerRet:
    """Handler for qute://pdfjs.

    Return the pdf.js viewer or redirect to original URL if the file does not
    exist.
    """
    if url.path() == '/file':
        filename = QUrlQuery(url).queryItemValue('filename')
        if not filename:
            raise UrlInvalidError("Missing filename")
        if '/' in filename or os.sep in filename:
            raise RequestDeniedError("Path separator in filename.")

        path = _pdf_path(filename)
        with open(path, 'rb') as f:
            data = f.read()

        mimetype = utils.guess_mimetype(filename, fallback=True)
        return mimetype, data

    if url.path() == '/web/viewer.html':
        query = QUrlQuery(url)
        filename = query.queryItemValue("filename")
        if not filename:
            raise UrlInvalidError("Missing filename")

        path = _pdf_path(filename)
        if not os.path.isfile(path):
            source = query.queryItemValue('source')
            if not source:  # This may happen with old URLs stored in history
                raise UrlInvalidError("Missing source")
            raise Redirect(QUrl(source))

        data = pdfjs.generate_pdfjs_page(filename, url)
        return 'text/html', data

    try:
        data = pdfjs.get_pdfjs_res(url.path())
    except pdfjs.PDFJSNotFound as e:
        # Logging as the error might get lost otherwise since we're not showing
        # the error page if a single asset is missing. This way we don't lose
        # information, as the failed pdfjs requests are still in the log.
        log.misc.warning(
            "pdfjs resource requested but not found: {}".format(e.path))
        raise NotFoundError("Can't find pdfjs resource '{}'".format(e.path))
    else:
        mimetype = utils.guess_mimetype(url.fileName(), fallback=True)
        return mimetype, data


@add_handler('warning')
def qute_warning(url: QUrl) -> _HandlerRet:
    """Handler for qute://warning."""
    path = url.path()
    if path == '/old-qt':
        src = jinja.render('warning-old-qt.html',
                           title='Old Qt warning',
                           qt_version=qVersion())
    elif path == '/webkit':
        src = jinja.render('warning-webkit.html',
                           title='QtWebKit backend warning')
    elif path == '/sessions':
        src = jinja.render('warning-sessions.html',
                           title='Qt 5.15 sessions warning',
                           datadir=standarddir.data(),
                           sep=os.sep)
    else:
        raise NotFoundError("Invalid warning page {}".format(path))
    return 'text/html', src
