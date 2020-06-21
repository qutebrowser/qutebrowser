# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Handling of proxies."""

from PyQt5.QtCore import QUrl, pyqtSlot
from PyQt5.QtNetwork import QNetworkProxy, QNetworkProxyFactory

from qutebrowser.config import config, configtypes
from qutebrowser.utils import message, usertypes, urlutils
from qutebrowser.misc import objects
from qutebrowser.browser.network import pac


application_factory = None


def init():
    """Set the application wide proxy factory."""
    global application_factory
    application_factory = ProxyFactory()
    QNetworkProxyFactory.setApplicationProxyFactory(application_factory)

    config.instance.changed.connect(_warn_for_pac)
    _warn_for_pac()


@config.change_filter('content.proxy', function=True)
def _warn_for_pac():
    """Show a warning if PAC is used with QtWebEngine."""
    proxy = config.val.content.proxy
    if (isinstance(proxy, pac.PACFetcher) and
            objects.backend == usertypes.Backend.QtWebEngine):
        message.error("PAC support isn't implemented for QtWebEngine yet!")


@pyqtSlot()
def shutdown():
    QNetworkProxyFactory.setApplicationProxyFactory(
        None)  # type: ignore[arg-type]


class ProxyFactory(QNetworkProxyFactory):

    """Factory for proxies to be used by qutebrowser."""

    def get_error(self):
        """Check if proxy can't be resolved.

        Return:
           None if proxy is correct, otherwise an error message.
        """
        proxy = config.val.content.proxy
        if isinstance(proxy, pac.PACFetcher):
            return proxy.fetch_error()
        else:
            return None

    def _set_capabilities(self, proxy):
        if proxy.type() == QNetworkProxy.NoProxy:
            return

        capabilities = proxy.capabilities()
        lookup_cap = QNetworkProxy.HostNameLookupCapability
        if config.val.content.proxy_dns_requests:
            capabilities |= lookup_cap
        else:
            capabilities &= ~lookup_cap
        proxy.setCapabilities(capabilities)

    def queryProxy(self, query):
        """Get the QNetworkProxies for a query.

        Args:
            query: The QNetworkProxyQuery to get a proxy for.

        Return:
            A list of QNetworkProxy objects in order of preference.
        """
        proxy = config.val.content.proxy
        if proxy is configtypes.SYSTEM_PROXY:
            # On Linux, use "export http_proxy=socks5://host:port" to manually
            # set system proxy.
            # ref. http://doc.qt.io/qt-5/qnetworkproxyfactory.html#systemProxyForQuery
            proxies = QNetworkProxyFactory.systemProxyForQuery(query)
        elif isinstance(proxy, pac.PACFetcher):
            if objects.backend == usertypes.Backend.QtWebEngine:
                # Looks like query.url() is always invalid on QtWebEngine...
                proxy = urlutils.proxy_from_url(QUrl('direct://'))
                assert not isinstance(proxy, pac.PACFetcher)
                proxies = [proxy]
            else:
                proxies = proxy.resolve(query)
        else:
            proxies = [proxy]
        for proxy in proxies:
            self._set_capabilities(proxy)
        return proxies
