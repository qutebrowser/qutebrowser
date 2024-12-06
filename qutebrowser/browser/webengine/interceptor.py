# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""A request interceptor taking care of adblocking and custom headers."""

from qutebrowser.qt.core import QUrl, QByteArray
from qutebrowser.qt.webenginecore import (QWebEngineUrlRequestInterceptor,
                                   QWebEngineUrlRequestInfo)

from qutebrowser.config import websettings, config
from qutebrowser.browser import shared
from qutebrowser.utils import debug, log, qtutils
from qutebrowser.extensions import interceptors
from qutebrowser.misc import objects


class WebEngineRequest(interceptors.Request):

    """QtWebEngine-specific request interceptor functionality."""

    _WHITELISTED_REQUEST_METHODS = {
        QByteArray(b'GET'),
        QByteArray(b'HEAD'),
    }

    def __init__(self, *args, webengine_info, **kwargs):
        super().__init__(*args, **kwargs)
        self._webengine_info = webengine_info
        self._redirected = False

    def redirect(self, url: QUrl, *, ignore_unsupported: bool = False) -> None:
        if self._redirected:
            raise interceptors.RedirectException("Request already redirected.")
        if self._webengine_info is None:
            raise interceptors.RedirectException("Request improperly initialized.")

        try:
            qtutils.ensure_valid(url)
        except qtutils.QtValueError as e:
            raise interceptors.RedirectException(f"Redirect to invalid URL: {e}")

        # Redirecting a request that contains payload data is not allowed.
        # To be safe, abort on any request not in a whitelist.
        verb = self._webengine_info.requestMethod()
        if verb not in self._WHITELISTED_REQUEST_METHODS:
            msg = (f"Request method {verb} for {self.request_url.toDisplayString()} "
                   "does not support redirection.")
            if ignore_unsupported:
                log.network.debug(msg)
                return
            raise interceptors.RedirectException(msg)

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
            QWebEngineUrlRequestInfo.ResourceType.ResourceTypeMainFrame:
                interceptors.ResourceType.main_frame,
            QWebEngineUrlRequestInfo.ResourceType.ResourceTypeSubFrame:
                interceptors.ResourceType.sub_frame,
            QWebEngineUrlRequestInfo.ResourceType.ResourceTypeStylesheet:
                interceptors.ResourceType.stylesheet,
            QWebEngineUrlRequestInfo.ResourceType.ResourceTypeScript:
                interceptors.ResourceType.script,
            QWebEngineUrlRequestInfo.ResourceType.ResourceTypeImage:
                interceptors.ResourceType.image,
            QWebEngineUrlRequestInfo.ResourceType.ResourceTypeFontResource:
                interceptors.ResourceType.font_resource,
            QWebEngineUrlRequestInfo.ResourceType.ResourceTypeSubResource:
                interceptors.ResourceType.sub_resource,
            QWebEngineUrlRequestInfo.ResourceType.ResourceTypeObject:
                interceptors.ResourceType.object,
            QWebEngineUrlRequestInfo.ResourceType.ResourceTypeMedia:
                interceptors.ResourceType.media,
            QWebEngineUrlRequestInfo.ResourceType.ResourceTypeWorker:
                interceptors.ResourceType.worker,
            QWebEngineUrlRequestInfo.ResourceType.ResourceTypeSharedWorker:
                interceptors.ResourceType.shared_worker,
            QWebEngineUrlRequestInfo.ResourceType.ResourceTypePrefetch:
                interceptors.ResourceType.prefetch,
            QWebEngineUrlRequestInfo.ResourceType.ResourceTypeFavicon:
                interceptors.ResourceType.favicon,
            QWebEngineUrlRequestInfo.ResourceType.ResourceTypeXhr:
                interceptors.ResourceType.xhr,
            QWebEngineUrlRequestInfo.ResourceType.ResourceTypePing:
                interceptors.ResourceType.ping,
            QWebEngineUrlRequestInfo.ResourceType.ResourceTypeServiceWorker:
                interceptors.ResourceType.service_worker,
            QWebEngineUrlRequestInfo.ResourceType.ResourceTypeCspReport:
                interceptors.ResourceType.csp_report,
            QWebEngineUrlRequestInfo.ResourceType.ResourceTypePluginResource:
                interceptors.ResourceType.plugin_resource,
            QWebEngineUrlRequestInfo.ResourceType.ResourceTypeUnknown:
                interceptors.ResourceType.unknown,
            QWebEngineUrlRequestInfo.ResourceType.ResourceTypeNavigationPreloadMainFrame:
                interceptors.ResourceType.preload_main_frame,
            QWebEngineUrlRequestInfo.ResourceType.ResourceTypeNavigationPreloadSubFrame:
                interceptors.ResourceType.preload_sub_frame,
        }
        new_types = {
            "WebSocket": interceptors.ResourceType.websocket,  # added in Qt 6.4
            "Json": interceptors.ResourceType.json,  # added in Qt 6.8
        }
        for qt_name, qb_value in new_types.items():
            qt_value = getattr(
                QWebEngineUrlRequestInfo.ResourceType,
                f"ResourceType{qt_name}",
                None,
            )
            if qt_value is not None:
                self._resource_types[qt_value] = qb_value

    def install(self, profile):
        """Install the interceptor on the given QWebEngineProfile."""
        profile.setUrlRequestInterceptor(self)

    def interceptRequest(self, info):
        """Handle the given request.

        Reimplementing this virtual function and setting the interceptor on a
        profile makes it possible to intercept URL requests.

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
            log.network.debug("{} {}, first-party {}, resource {}, "
                              "navigation {}".format(
                                  bytes(info.requestMethod()).decode('ascii'),
                                  info.requestUrl().toDisplayString(),
                                  info.firstPartyUrl().toDisplayString(),
                                  resource_type_str, navigation_type_str))

        url = info.requestUrl()
        first_party = info.firstPartyUrl()
        if not url.isValid():
            log.network.debug("Ignoring invalid intercepted URL: {}".format(
                url.errorString()))
            return

        # Per QWebEngineUrlRequestInfo::ResourceType documentation, if we fail
        # our lookup, we should fall back to ResourceTypeUnknown
        try:
            resource_type = self._resource_types[info.resourceType()]
        except KeyError:
            log.network.warning(
                "Resource type {} not found in RequestInterceptor dict."
                .format(debug.qenum_key(QWebEngineUrlRequestInfo,
                                        info.resourceType())))
            resource_type = interceptors.ResourceType.unknown

        is_xhr = info.resourceType() == QWebEngineUrlRequestInfo.ResourceType.ResourceTypeXhr

        if ((url.scheme(), url.host(), url.path()) ==
                ('qute', 'settings', '/set')):
            if first_party != QUrl('qute://settings/') or not is_xhr:
                log.network.warning("Blocking malicious request from {} to {}"
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

        for header, value in shared.custom_headers(
            url=url, fallback_accept_language=not is_xhr
        ):
            if header.lower() == b'accept' and is_xhr:
                # https://developer.mozilla.org/en-US/docs/Web/API/XMLHttpRequest/setRequestHeader
                # says: "If no Accept header has been set using this, an Accept header
                # with the type "*/*" is sent with the request when send() is called."
                #
                # We shouldn't break that if someone sets a custom Accept header for
                # normal requests.
                continue
            info.setHttpHeader(header, value)

        if config.cache['content.headers.referer'] == 'never':
            info.setHttpHeader(b'Referer', b'')

        user_agent = websettings.user_agent(url)
        info.setHttpHeader(b'User-Agent', user_agent.encode('ascii'))
