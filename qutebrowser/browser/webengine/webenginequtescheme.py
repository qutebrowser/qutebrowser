# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""QtWebEngine specific qute://* handlers and glue code."""

from PyQt5.QtCore import QBuffer, QIODevice, QUrl
from PyQt5.QtWebEngineCore import (QWebEngineUrlSchemeHandler,
                                   QWebEngineUrlRequestJob)

from qutebrowser.browser import qutescheme
from qutebrowser.utils import log, qtutils


class QuteSchemeHandler(QWebEngineUrlSchemeHandler):

    """Handle qute://* requests on QtWebEngine."""

    def install(self, profile):
        """Install the handler for qute:// URLs on the given profile."""
        profile.installUrlSchemeHandler(b'qute', self)
        if qtutils.version_check('5.11', compiled=False):
            # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-63378
            profile.installUrlSchemeHandler(b'chrome-error', self)
            profile.installUrlSchemeHandler(b'chrome-extension', self)

    def _check_initiator(self, job):
        """Check whether the initiator of the job should be allowed.

        Only the browser itself or qute:// pages should access any of those
        URLs. The request interceptor further locks down qute://settings/set.

        Args:
            job: QWebEngineUrlRequestJob

        Return:
            True if the initiator is allowed, False if it was blocked.
        """
        try:
            initiator = job.initiator()
        except AttributeError:
            # Added in Qt 5.11
            return True

        if initiator == QUrl('null') and not qtutils.version_check('5.12'):
            # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-70421
            return True

        if initiator.isValid() and initiator.scheme() != 'qute':
            log.misc.warning("Blocking malicious request from {} to {}".format(
                initiator.toDisplayString(),
                job.requestUrl().toDisplayString()))
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

        if url.scheme() in ['chrome-error', 'chrome-extension']:
            # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-63378
            job.fail(QWebEngineUrlRequestJob.UrlInvalid)
            return

        if not self._check_initiator(job):
            return

        if job.requestMethod() != b'GET':
            job.fail(QWebEngineUrlRequestJob.RequestDenied)
            return

        assert url.scheme() == 'qute'

        log.misc.debug("Got request for {}".format(url.toDisplayString()))
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
            log.misc.error("{} while handling qute://* URL".format(
                exctype.__name__))
            job.fail(errors[exctype])
        except qutescheme.Redirect as e:
            qtutils.ensure_valid(e.url)
            job.redirect(e.url)
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
