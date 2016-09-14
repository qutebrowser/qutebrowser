# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""QtWebEngine specific qute:* handlers and glue code."""

from PyQt5.QtCore import QBuffer, QIODevice
# pylint: disable=no-name-in-module,import-error,useless-suppression
from PyQt5.QtWebEngineCore import (QWebEngineUrlSchemeHandler,
                                   QWebEngineUrlRequestJob)
# pylint: enable=no-name-in-module,import-error,useless-suppression

from qutebrowser.browser import qutescheme
from qutebrowser.utils import log


class QuteSchemeHandler(QWebEngineUrlSchemeHandler):

    """Handle qute:* requests on QtWebEngine."""

    def install(self, profile):
        """Install the handler for qute: URLs on the given profile."""
        profile.installUrlSchemeHandler(b'qute', self)

    def requestStarted(self, job):
        """Handle a request for a qute: scheme.

        This method must be reimplemented by all custom URL scheme handlers.
        The request is asynchronous and does not need to be handled right away.

        Args:
            job: QWebEngineUrlRequestJob
        """
        url = job.requestUrl()
        assert job.requestMethod() == b'GET'
        assert url.scheme() == 'qute'
        log.misc.debug("Got request for {}".format(url.toDisplayString()))
        try:
            mimetype, data = qutescheme.data_for_url(url)
        except qutescheme.NoHandlerFound:
            log.misc.debug("No handler found for {}".format(
                url.toDisplayString()))
            job.fail(QWebEngineUrlRequestJob.UrlNotFound)
        except qutescheme.QuteSchemeOSError:
            # FIXME:qtwebengine how do we show a better error here?
            log.misc.exception("OSError while handling qute:* URL")
            job.fail(QWebEngineUrlRequestJob.UrlNotFound)
        except qutescheme.QuteSchemeError:
            # FIXME:qtwebengine how do we show a better error here?
            log.misc.exception("Error while handling qute:* URL")
            job.fail(QWebEngineUrlRequestJob.RequestFailed)
        else:
            log.misc.debug("Returning {} data".format(mimetype))

            # We can't just use the QBuffer constructor taking a QByteArray,
            # because that somehow segfaults...
            # https://www.riverbankcomputing.com/pipermail/pyqt/2016-September/038075.html
            buf = QBuffer(parent=self)
            buf.open(QIODevice.WriteOnly)
            buf.write(data)
            buf.seek(0)
            buf.close()
            job.reply(mimetype.encode('ascii'), buf)
