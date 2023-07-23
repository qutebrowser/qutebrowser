# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""QtWebKit specific qute://* handlers and glue code."""

from qutebrowser.qt.core import QUrl
from qutebrowser.qt.network import QNetworkReply, QNetworkAccessManager

from qutebrowser.browser import qutescheme
from qutebrowser.browser.webkit.network import networkreply
from qutebrowser.utils import log, qtutils


def handler(request, operation, current_url):
    """Scheme handler for qute:// URLs.

    Args:
        request: QNetworkRequest to answer to.
        operation: The HTTP operation being done.
        current_url: The page we're on currently.

    Return:
        A QNetworkReply.
    """
    if operation != QNetworkAccessManager.Operation.GetOperation:
        return networkreply.ErrorNetworkReply(
            request, "Unsupported request type",
            QNetworkReply.NetworkError.ContentOperationNotPermittedError)

    url = request.url()

    if ((url.scheme(), url.host(), url.path()) ==
            ('qute', 'settings', '/set')):
        if current_url != QUrl('qute://settings/'):
            log.network.warning("Blocking malicious request from {} to {}"
                                .format(current_url.toDisplayString(),
                                        url.toDisplayString()))
            return networkreply.ErrorNetworkReply(
                request, "Invalid qute://settings request",
                QNetworkReply.NetworkError.ContentAccessDenied)

    try:
        mimetype, data = qutescheme.data_for_url(url)
    except qutescheme.Error as e:
        errors = {
            qutescheme.NotFoundError:
                QNetworkReply.NetworkError.ContentNotFoundError,
            qutescheme.UrlInvalidError:
                QNetworkReply.NetworkError.ContentOperationNotPermittedError,
            qutescheme.RequestDeniedError:
                QNetworkReply.NetworkError.ContentAccessDenied,
            qutescheme.SchemeOSError:
                QNetworkReply.NetworkError.ContentNotFoundError,
            qutescheme.Error:
                QNetworkReply.NetworkError.InternalServerError,
        }
        exctype = type(e)
        log.misc.error("{} while handling qute://* URL".format(
            exctype.__name__))
        return networkreply.ErrorNetworkReply(request, str(e), errors[exctype])
    except qutescheme.Redirect as e:
        qtutils.ensure_valid(e.url)
        return networkreply.RedirectNetworkReply(e.url)

    return networkreply.FixedDataNetworkReply(request, data, mimetype)
