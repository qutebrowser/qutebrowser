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

"""Handler functions for different qute:... pages.

Module attributes:
    _HTML_TEMPLATE: The HTML boilerplate used to convert text into html.
    pyeval_output: The output of the last :pyeval command.
"""

import html as pyhtml

from PyQt5.QtNetwork import QNetworkReply

import qutebrowser
from qutebrowser.network import schemehandler
from qutebrowser.utils import version, utils
from qutebrowser.utils import log as logutils


_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  {head}
</head>
<body>
{body}
</body>
</html>
"""


pyeval_output = ":pyeval was never called"


def _get_html(title, snippet, head=None):
    """Add HTML boilerplate to a html snippet.

    Args:
        title: The title the page should have.
        snippet: The html snippet.
        head: Additional stuff to put in <head>

    Return:
        HTML content as bytes.
    """
    if head is None:
        head = ""
    html = _HTML_TEMPLATE.format(title=title, body=snippet, head=head).encode(
        'UTF-8', errors='xmlcharrefreplace')
    return html


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
        # An url like "qute:foo" is split as "scheme:path", not "scheme:host".
        logutils.misc.debug("url: {}, path: {}".format(
            request.url().toDisplayString(), path))
        try:
            handler = getattr(QuteHandlers, path)
        except AttributeError:
            errorstr = "No handler found for {}!".format(
                request.url().toDisplayString())
            return schemehandler.ErrorNetworkReply(
                request, errorstr, QNetworkReply.ContentNotFoundError,
                self.parent())
        else:
            data = handler()
        return schemehandler.SpecialNetworkReply(
            request, data, 'text/html', self.parent())


class QuteHandlers:

    """Handlers for qute:... pages."""

    @classmethod
    def pyeval(cls):
        """Handler for qute:pyeval. Return HTML content as bytes."""
        text = pyhtml.escape(pyeval_output)
        return _get_html('pyeval', '<pre>{}</pre>'.format(text))

    @classmethod
    def version(cls):
        """Handler for qute:version. Return HTML content as bytes."""
        text = pyhtml.escape(version.version())
        html = '<h1>Version info</h1>'
        html += '<p>{}</p>'.format(text.replace('\n', '<br/>'))
        html += '<h1>Copyright info</h1>'
        html += '<p>{}</p>'.format(qutebrowser.__copyright__)
        html += version.GPL_BOILERPLATE_HTML
        return _get_html('Version', html)

    @classmethod
    def plainlog(cls):
        """Handler for qute:log. Return HTML content as bytes."""
        if logutils.ram_handler is None:
            text = "Log output was disabled."
        else:
            text = pyhtml.escape(logutils.ram_handler.dump_log())
        return _get_html('log', '<pre>{}</pre>'.format(text))

    @classmethod
    def log(cls):
        """Handler for qute:log. Return HTML content as bytes."""
        style = """
        <style type="text/css">
            body {
                background-color: black;
                color: white;
                font-size: 11px;
            }

            table {
                border: 1px solid grey;
                border-collapse: collapse;
            }

            pre {
                margin: 2px;
            }

            th, td {
                border: 1px solid grey;
                padding-left: 5px;
                padding-right: 5px;
            }
        </style>
        """
        if logutils.ram_handler is None:
            html = "<p>Log output was disabled.</p>"
        else:
            html = logutils.ram_handler.dump_log(html=True)
        return _get_html('log', html, head=style)

    @classmethod
    def gpl(cls):
        """Handler for qute:gpl. Return HTML content as bytes."""
        return utils.read_file('html/COPYING.html').encode('ASCII')
