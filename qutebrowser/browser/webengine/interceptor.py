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

from PyQt5.QtWebEngineCore import (QWebEngineUrlRequestInterceptor,
                                   QWebEngineUrlRequestInfo)

from qutebrowser.config import config
from qutebrowser.browser import shared
from qutebrowser.utils import utils, log, debug


class RequestInterceptor(QWebEngineUrlRequestInterceptor):

    """Handle ad blocking and custom headers."""

    def __init__(self, host_blocker, args, parent=None):
        super().__init__(parent)
        self._host_blocker = host_blocker
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

        # FIXME:qtwebengine only block ads for NavigationTypeOther?
        if self._host_blocker.is_blocked(info.requestUrl()):
            log.webview.info("Request to {} blocked by host blocker.".format(
                info.requestUrl().host()))
            info.block(True)

        for header, value in shared.custom_headers():
            info.setHttpHeader(header, value)

        user_agent = config.val.content.headers.user_agent
        if user_agent is not None:
            info.setHttpHeader(b'User-Agent', user_agent.encode('ascii'))
