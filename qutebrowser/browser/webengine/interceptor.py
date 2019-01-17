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

"""A request interceptor taking care of adblocking and custom headers."""

from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngineCore import (QWebEngineUrlRequestInterceptor,
                                   QWebEngineUrlRequestInfo)

from qutebrowser.config import config
from qutebrowser.browser import shared
from qutebrowser.utils import utils, log, debug
from qutebrowser.extensions import interceptors


class RequestInterceptor(QWebEngineUrlRequestInterceptor):

    """Handle ad blocking and custom headers."""

    # A simple mapping from QWebEngine Resource Types to qutebrowser extension
    # ResourceTypes. If a ResourceType is added to Qt, this table should be
    # updated too.
    RESOURCE_TYPES = {
        QWebEngineUrlRequestInfo.ResourceTypeMainFrame:
            interceptors.ResourceType.MAIN_FRAME,
        QWebEngineUrlRequestInfo.ResourceTypeSubFrame:
            interceptors.ResourceType.SUB_FRAME,
        QWebEngineUrlRequestInfo.ResourceTypeStylesheet:
            interceptors.ResourceType.STYLESHEET,
        QWebEngineUrlRequestInfo.ResourceTypeScript:
            interceptors.ResourceType.SCRIPT,
        QWebEngineUrlRequestInfo.ResourceTypeImage:
            interceptors.ResourceType.IMAGE,
        QWebEngineUrlRequestInfo.ResourceTypeFontResource:
            interceptors.ResourceType.FONT_RESOURCE,
        QWebEngineUrlRequestInfo.ResourceTypeSubResource:
            interceptors.ResourceType.SUB_RESOURCE,
        QWebEngineUrlRequestInfo.ResourceTypeObject:
            interceptors.ResourceType.OBJECT,
        QWebEngineUrlRequestInfo.ResourceTypeMedia:
            interceptors.ResourceType.MEDIA,
        QWebEngineUrlRequestInfo.ResourceTypeWorker:
            interceptors.ResourceType.WORKER,
        QWebEngineUrlRequestInfo.ResourceTypeSharedWorker:
            interceptors.ResourceType.SHARED_WORKER,
        QWebEngineUrlRequestInfo.ResourceTypePrefetch:
            interceptors.ResourceType.PREFETCH,
        QWebEngineUrlRequestInfo.ResourceTypeFavicon:
            interceptors.ResourceType.FAVICON,
        QWebEngineUrlRequestInfo.ResourceTypeXhr:
            interceptors.ResourceType.XHR,
        QWebEngineUrlRequestInfo.ResourceTypePing:
            interceptors.ResourceType.PING,
        QWebEngineUrlRequestInfo.ResourceTypeServiceWorker:
            interceptors.ResourceType.SERVICE_WORKER,
        QWebEngineUrlRequestInfo.ResourceTypeCspReport:
            interceptors.ResourceType.CSP_REPORT,
        QWebEngineUrlRequestInfo.ResourceTypePluginResource:
            interceptors.ResourceType.PLUGIN_RESOURCE,
        QWebEngineUrlRequestInfo.ResourceTypeUnknown:
            interceptors.ResourceType.UNKNOWN,
    }

    def __init__(self, args, parent=None):
        super().__init__(parent)
        self._args = args

    def install(self, profile):
        """Install the interceptor on the given QWebEngineProfile."""
        profile.setRequestInterceptor(self)

    # Gets called in the IO thread -> showing crash window will fail
    @utils.prevent_exceptions(None)
    def interceptRequest(self, info):
        """Handle the given request.

        Reimplementing this virtual function and setting the interceptor on a
        profile makes it possible to intercept URL requests. This function is
        executed on the IO thread, and therefore running long tasks here will
        block networking.

        info contains the information about the URL request and will track
        internally whether its members have been altered.

        Args:
            info: QWebEngineUrlRequestInfo &info
        """
        if 'log-requests' in self._args.debug_flags:
            resource_type = debug.qenum_key(QWebEngineUrlRequestInfo,
                                            info.resourceType())
            navigation_type = debug.qenum_key(QWebEngineUrlRequestInfo,
                                              info.navigationType())
            log.webview.debug("{} {}, first-party {}, resource {}, "
                              "navigation {}".format(
                                  bytes(info.requestMethod()).decode('ascii'),
                                  info.requestUrl().toDisplayString(),
                                  info.firstPartyUrl().toDisplayString(),
                                  resource_type, navigation_type))

        url = info.requestUrl()
        first_party = info.firstPartyUrl()
        # Per QWebEngineUrlRequestInfo::ResourceType documentation, if we fail
        # our lookup, we should fall back to ResourceTypeUnknown
        try:
            resource_type = RequestInterceptor.RESOURCE_TYPES[
                info.resourceType()]
        except KeyError:
            log.webview.warning(
                "Resource type {} not found in RequestInterceptor map."
                .format(debug.qenum_key(QWebEngineUrlRequestInfo,
                                        info.resourceType())))
            resource_type = interceptors.ResourceType.UNKNOWN

        if ((url.scheme(), url.host(), url.path()) ==
                ('qute', 'settings', '/set')):
            if (first_party != QUrl('qute://settings/') or
                    info.resourceType() !=
                    QWebEngineUrlRequestInfo.ResourceTypeXhr):
                log.webview.warning("Blocking malicious request from {} to {}"
                                    .format(first_party.toDisplayString(),
                                            url.toDisplayString()))
                info.block(True)
                return

        # FIXME:qtwebengine only block ads for NavigationTypeOther?
        request = interceptors.Request(first_party_url=first_party,
                                       request_url=url,
                                       resource_type=resource_type)
        interceptors.run(request)
        if request.is_blocked:
            info.block(True)

        for header, value in shared.custom_headers(url=url):
            info.setHttpHeader(header, value)

        user_agent = config.instance.get('content.headers.user_agent', url=url)
        if user_agent is not None:
            info.setHttpHeader(b'User-Agent', user_agent.encode('ascii'))
