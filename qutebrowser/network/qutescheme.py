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

import logging
import cgi

from qutebrowser.network._schemehandler import (SchemeHandler,
                                                SpecialNetworkReply)
from qutebrowser.utils.version import version
from qutebrowser.utils.url import urlstring


_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{title}</title>
</head>
<body>
{body}
</body>
</html>
"""


pyeval_output = None


def _get_html(title, snippet):
    """Add HTML boilerplate to a html snippet.

    Args:
        title: The title the page should have.
        snippet: The html snippet.

    Return:
        HTML content as bytes.
    """
    return _HTML_TEMPLATE.format(title=title, body=snippet).encode('UTF-8')


class QuteSchemeHandler(SchemeHandler):

    """Scheme handler for qute: URLs."""

    def _transform_url(self, url):
        """Transform a special URL to an QuteHandlers method name.

        Args:
            url: The URL as string.

        Return:
            The method name qute_*
        """
        return url.replace('http://', '').replace('qute:', 'qute_')

    def createRequest(self, _op, request, _outgoing_data):
        """Create a new request.

        Args:
             request: const QNetworkRequest & req
             _op: Operation op
             _outgoing_data: QIODevice * outgoingData

        Return:
            A QNetworkReply.
        """
        logging.debug('request: {}'.format(request))
        url = urlstring(request.url())
        try:
            handler = getattr(QuteHandlers, self._transform_url(url))
        except AttributeError:
            data = bytes()
        else:
            data = handler()
        return SpecialNetworkReply(request, data, "text/html", self.parent())


class QuteHandlers:

    """Handlers for qute:... pages."""

    @classmethod
    def qute_pyeval(cls):
        """Handler for qute:pyeval. Return HTML content as bytes."""
        text = cgi.escape(pyeval_output)
        return _get_html('pyeval', '<pre>{}</pre>'.format(text))

    @classmethod
    def qute_version(cls):
        """Handler for qute:version. Return HTML content as bytes."""
        text = cgi.escape(version())
        return _get_html('Version', '<pre>{}</pre>'.format(text))
