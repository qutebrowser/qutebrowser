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

"""A request interceptor taking care of adblocking and custom headers."""

import attr

from PyQt5.QtCore import QUrl, QByteArray
from PyQt5.QtWebEngineCore import (QWebEngineUrlRequestInterceptor,
                                   QWebEngineUrlRequestInfo)

from qutebrowser.config import websettings
from qutebrowser.browser import shared
from qutebrowser.utils import utils, log, debug, qtutils
from qutebrowser.extensions import interceptors
from qutebrowser.misc import objects


@attr.s
class WebEngineRequest(interceptors.Request):

    """QtWebEngine-specific request interceptor functionality."""

    _WHITELISTED_REQUEST_METHODS = {QByteArray(b'GET'), QByteArray(b'HEAD')}

    _webengine_info = attr.ib(default=None)  # type: QWebEngineUrlRequestInfo
    #: If this request has been redirected already
    _redirected = attr.ib(init=False, default=False)  # type: bool

    def redirect(self, url: QUrl) -> None:
        if self._redirected:
            raise interceptors.RedirectFailedException(
                "Request already redirected.")
        if self._webengine_info is None:
            raise interceptors.RedirectFailedException(
                "Request improperly initialized.")
        # Redirecting a request that contains payload data is not allowed.
        # To be safe, abort on any request not in a whitelist.
        if (self._webengine_info.requestMethod()
                not in self._WHITELISTED_REQUEST_METHODS):
            raise interceptors.RedirectFailedException(
                "Request method does not support redirection.")
        self._webengine_info.redirect(url)
        self._redirected = True


class RequestInterceptor(QWebEngineUrlRequestInterceptor):
    """Handle ad blocking and custom headers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # This dict should be from QWebEngine Resource Types to qutebrowser
        # extension ResourceTypes. If a ResourceType is added to Qt, this table
        # should be updated too.
        self._resource_types = {
            QWebEngineUrlRequestInfo.ResourceTypeMainFrame:
                interceptors.ResourceType.main_frame,
            QWebEngineUrlRequestInfo.ResourceTypeSubFrame:
                interceptors.ResourceType.sub_frame,
            QWebEngineUrlRequestInfo.ResourceTypeStylesheet:
                interceptors.ResourceType.stylesheet,
            QWebEngineUrlRequestInfo.ResourceTypeScript:
                interceptors.ResourceType.script,
            QWebEngineUrlRequestInfo.ResourceTypeImage:
                interceptors.ResourceType.image,
            QWebEngineUrlRequestInfo.ResourceTypeFontResource:
                interceptors.ResourceType.font_resource,
            QWebEngineUrlRequestInfo.ResourceTypeSubResource:
                interceptors.ResourceType.sub_resource,
            QWebEngineUrlRequestInfo.ResourceTypeObject:
                interceptors.ResourceType.object,
            QWebEngineUrlRequestInfo.ResourceTypeMedia:
                interceptors.ResourceType.media,
            QWebEngineUrlRequestInfo.ResourceTypeWorker:
                interceptors.ResourceType.worker,
            QWebEngineUrlRequestInfo.ResourceTypeSharedWorker:
                interceptors.ResourceType.shared_worker,
            QWebEngineUrlRequestInfo.ResourceTypePrefetch:
                interceptors.ResourceType.prefetch,
            QWebEngineUrlRequestInfo.ResourceTypeFavicon:
                interceptors.ResourceType.favicon,
            QWebEngineUrlRequestInfo.ResourceTypeXhr:
                interceptors.ResourceType.xhr,
            QWebEngineUrlRequestInfo.ResourceTypePing:
                interceptors.ResourceType.ping,
            QWebEngineUrlRequestInfo.ResourceTypeServiceWorker:
                interceptors.ResourceType.service_worker,
            QWebEngineUrlRequestInfo.ResourceTypeCspReport:
                interceptors.ResourceType.csp_report,
            QWebEngineUrlRequestInfo.ResourceTypePluginResource:
                interceptors.ResourceType.plugin_resource,
            QWebEngineUrlRequestInfo.ResourceTypeUnknown:
                interceptors.ResourceType.unknown,
        }

        try:
            preload_main_frame = (QWebEngineUrlRequestInfo.
                                  ResourceTypeNavigationPreloadMainFrame)
            preload_sub_frame = (QWebEngineUrlRequestInfo.
                                 ResourceTypeNavigationPreloadSubFrame)
        except AttributeError:
            # Added in Qt 5.14
            pass
        else:
            self._resource_types[preload_main_frame] = (
                interceptors.ResourceType.preload_main_frame)
            self._resource_types[preload_sub_frame] = (
                interceptors.ResourceType.preload_sub_frame)

    def install(self, profile):
        """Install the interceptor on the given QWebEngineProfile."""
        try:
            # Qt >= 5.13, GUI thread
            profile.setUrlRequestInterceptor(self)
        except AttributeError:
            # Qt <= 5.12, IO thread
            profile.setRequestInterceptor(self)

    # Gets called in the IO thread -> showing crash window will fail
    @utils.prevent_exceptions(None, not qtutils.version_check('5.13'))
    def interceptRequest(self, info):
        """Handle the given request.

        Reimplementing this virtual function and setting the interceptor on a
        profile makes it possible to intercept URL requests.

        On Qt < 5.13, this function is executed on the IO thread, and therefore
        running long tasks here will block networking.

        info contains the information about the URL request and will track
        internally whether its members have been altered.

        Args:
            info: QWebEngineUrlRequestInfo &info
        """
        if 'log-requests' in objects.debug_flags:
            resource_type_str = debug.qenum_key(QWebEngineUrlRequestInfo,
                                                info.resourceType())
            navigation_type_str = debug.qenum_key(QWebEngineUrlRequestInfo,
                                                  info.navigationType())
            log.webview.debug("{} {}, first-party {}, resource {}, "
                              "navigation {}".format(
                                  bytes(info.requestMethod()).decode('ascii'),
                                  info.requestUrl().toDisplayString(),
                                  info.firstPartyUrl().toDisplayString(),
                                  resource_type_str, navigation_type_str))

        url = info.requestUrl()
        first_party = info.firstPartyUrl()
        if not url.isValid():
            log.webview.debug("Ignoring invalid intercepted URL: {}".format(
                url.errorString()))
            return

        # Per QWebEngineUrlRequestInfo::ResourceType documentation, if we fail
        # our lookup, we should fall back to ResourceTypeUnknown
        try:
            resource_type = self._resource_types[info.resourceType()]
        except KeyError:
            log.webview.warning(
                "Resource type {} not found in RequestInterceptor dict."
                .format(debug.qenum_key(QWebEngineUrlRequestInfo,
                                        info.resourceType())))
            resource_type = interceptors.ResourceType.unknown

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
        request = WebEngineRequest(
            first_party_url=first_party,
            request_url=url,
            resource_type=resource_type,
            webengine_info=info)

        interceptors.run(request)
        if request.is_blocked:
            info.block(True)

        for header, value in shared.custom_headers(url=url):
            info.setHttpHeader(header, value)

        user_agent = websettings.user_agent(url)
        info.setHttpHeader(b'User-Agent', user_agent.encode('ascii'))
