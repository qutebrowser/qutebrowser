# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""QtWebEngine specific qute://* handlers and glue code."""

from PyQt5.QtCore import QBuffer, QIODevice, QUrl
from PyQt5.QtWebEngineCore import (QWebEngineUrlSchemeHandler,
                                   QWebEngineUrlRequestJob,
                                   QWebEngineUrlScheme)

from qutebrowser.browser import qutescheme
from qutebrowser.utils import log, qtutils


class QuteSchemeHandler(QWebEngineUrlSchemeHandler):

    """Handle qute://* requests on QtWebEngine."""

    def install(self, profile):
        """Install the handler for qute:// URLs on the given profile."""
        if QWebEngineUrlScheme is not None:
            assert QWebEngineUrlScheme.schemeByName(b'qute') is not None

        profile.installUrlSchemeHandler(b'qute', self)

    def _check_initiator(self, job):
        """Check whether the initiator of the job should be allowed.

        Only the browser itself or qute:// pages should access any of those
        URLs. The request interceptor further locks down qute://settings/set.

        Args:
            job: QWebEngineUrlRequestJob

        Return:
            True if the initiator is allowed, False if it was blocked.
        """
        initiator = job.initiator()
        request_url = job.requestUrl()

        # https://codereview.qt-project.org/#/c/234849/
        is_opaque = initiator == QUrl('null')
        target = request_url.scheme(), request_url.host()

        if target == ('qute', 'testdata') and is_opaque:
            # Allow requests to qute://testdata, as this is needed for all tests to work
            # properly. No qute://testdata handler is installed outside of tests.
            return True

        if initiator.isValid() and initiator.scheme() != 'qute':
            log.network.warning("Blocking malicious request from {} to {}"
                                .format(initiator.toDisplayString(),
                                        request_url.toDisplayString()))
            job.fail(QWebEngineUrlRequestJob.RequestDenied)
            return False

        return True

    def requestStarted(self, job):
        """Handle a request for a qute: scheme.

        This method must be reimplemented by all custom URL scheme handlers.
        The request is asynchronous and does not need to be handled right away.

        Args:
            job: QWebEngineUrlRequestJob
        """
        url = job.requestUrl()

        if not self._check_initiator(job):
            return

        if job.requestMethod() != b'GET':
            job.fail(QWebEngineUrlRequestJob.RequestDenied)
            return

        assert url.scheme() == 'qute'

        log.network.debug("Got request for {}".format(url.toDisplayString()))
        try:
            mimetype, data = qutescheme.data_for_url(url)
        except qutescheme.Error as e:
            errors = {
                qutescheme.NotFoundError:
                    QWebEngineUrlRequestJob.UrlNotFound,
                qutescheme.UrlInvalidError:
                    QWebEngineUrlRequestJob.UrlInvalid,
                qutescheme.RequestDeniedError:
                    QWebEngineUrlRequestJob.RequestDenied,
                qutescheme.SchemeOSError:
                    QWebEngineUrlRequestJob.UrlNotFound,
                qutescheme.Error:
                    QWebEngineUrlRequestJob.RequestFailed,
            }
            exctype = type(e)
            log.network.error(f"{exctype.__name__} while handling qute://* URL: {e}")
            job.fail(errors[exctype])
        except qutescheme.Redirect as e:
            qtutils.ensure_valid(e.url)
            job.redirect(e.url)
        else:
            log.network.debug("Returning {} data".format(mimetype))

            # We can't just use the QBuffer constructor taking a QByteArray,
            # because that somehow segfaults...
            # https://www.riverbankcomputing.com/pipermail/pyqt/2016-September/038075.html
            buf = QBuffer(parent=self)
            buf.open(QIODevice.WriteOnly)
            buf.write(data)
            buf.seek(0)
            buf.close()
            job.reply(mimetype.encode('ascii'), buf)


def init():
    """Register the qute:// scheme.

    Note this needs to be called early, before constructing any QtWebEngine
    classes.
    """
    if QWebEngineUrlScheme is not None:
        assert not QWebEngineUrlScheme.schemeByName(b'qute').name()
        scheme = QWebEngineUrlScheme(b'qute')
        scheme.setFlags(
            QWebEngineUrlScheme.LocalScheme |  # type: ignore[arg-type]
            QWebEngineUrlScheme.LocalAccessAllowed)
        QWebEngineUrlScheme.registerScheme(scheme)
