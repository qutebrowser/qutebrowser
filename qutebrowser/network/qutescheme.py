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
#
# pylint complains when using .render() on jinja templates, so we make it shut
# up for this whole module.
# pylint: disable=maybe-no-member

"""Handler functions for different qute:... pages.

Module attributes:
    pyeval_output: The output of the last :pyeval command.
"""

from PyQt5.QtNetwork import QNetworkReply

import qutebrowser
from qutebrowser.network import schemehandler
from qutebrowser.utils import version, utils, jinja
from qutebrowser.utils import log as logutils


pyeval_output = ":pyeval was never called"


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
        html = jinja.env.get_template('pre.html').render(
            title='pyeval', content=pyeval_output)
        return html.encode('UTF-8', errors='xmlcharrefreplace')

    @classmethod
    def version(cls):
        """Handler for qute:version. Return HTML content as bytes."""
        html = jinja.env.get_template('version.html').render(
            title='Version info', version=version.version(),
            copyright=qutebrowser.__copyright__)
        return html.encode('UTF-8', errors='xmlcharrefreplace')

    @classmethod
    def plainlog(cls):
        """Handler for qute:plainlog. Return HTML content as bytes."""
        if logutils.ram_handler is None:
            text = "Log output was disabled."
        else:
            text = logutils.ram_handler.dump_log()
        html = jinja.env.get_template('pre.html').render(
            title='log', content=text)
        return html.encode('UTF-8', errors='xmlcharrefreplace')

    @classmethod
    def log(cls):
        """Handler for qute:log. Return HTML content as bytes."""
        if logutils.ram_handler is None:
            html_log = None
        else:
            html_log = logutils.ram_handler.dump_log(html=True)
        html = jinja.env.get_template('log.html').render(
            title='log', content=html_log)
        return html.encode('UTF-8', errors='xmlcharrefreplace')

    @classmethod
    def gpl(cls):
        """Handler for qute:gpl. Return HTML content as bytes."""
        return utils.read_file('html/COPYING.html').encode('ASCII')
