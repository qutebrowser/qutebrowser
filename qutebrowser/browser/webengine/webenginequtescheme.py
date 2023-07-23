# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""QtWebEngine specific qute://* handlers and glue code."""

from qutebrowser.qt.core import QBuffer, QIODevice, QUrl, QByteArray
from qutebrowser.qt.webenginecore import (QWebEngineUrlSchemeHandler,
                                   QWebEngineUrlRequestJob,
                                   QWebEngineUrlScheme)

from qutebrowser.browser import qutescheme
from qutebrowser.utils import log, qtutils

_QUTE = QByteArray(b'qute')


class QuteSchemeHandler(QWebEngineUrlSchemeHandler):

    """Handle qute://* requests on QtWebEngine."""

    def install(self, profile):
        """Install the handler for qute:// URLs on the given profile."""
        if QWebEngineUrlScheme is not None:
            assert QWebEngineUrlScheme.schemeByName(_QUTE) is not None

        profile.installUrlSchemeHandler(_QUTE, self)

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
            job.fail(QWebEngineUrlRequestJob.Error.RequestDenied)
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
            job.fail(QWebEngineUrlRequestJob.Error.RequestDenied)
            return

        assert url.scheme() == 'qute'

        log.network.debug("Got request for {}".format(url.toDisplayString()))
        try:
            mimetype, data = qutescheme.data_for_url(url)
        except qutescheme.Error as e:
            errors = {
                qutescheme.NotFoundError:
                    QWebEngineUrlRequestJob.Error.UrlNotFound,
                qutescheme.UrlInvalidError:
                    QWebEngineUrlRequestJob.Error.UrlInvalid,
                qutescheme.RequestDeniedError:
                    QWebEngineUrlRequestJob.Error.RequestDenied,
                qutescheme.SchemeOSError:
                    QWebEngineUrlRequestJob.Error.UrlNotFound,
                qutescheme.Error:
                    QWebEngineUrlRequestJob.Error.RequestFailed,
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
            buf.open(QIODevice.OpenModeFlag.WriteOnly)
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
        assert not QWebEngineUrlScheme.schemeByName(_QUTE).name()
        scheme = QWebEngineUrlScheme(_QUTE)
        scheme.setFlags(
            QWebEngineUrlScheme.Flag.LocalScheme |
            QWebEngineUrlScheme.Flag.LocalAccessAllowed)
        QWebEngineUrlScheme.registerScheme(scheme)
