# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Handling of proxies."""

from typing import Optional

from qutebrowser.qt.core import QUrl, pyqtSlot
from qutebrowser.qt.network import QNetworkProxy, QNetworkProxyFactory, QNetworkProxyQuery

from qutebrowser.config import config, configtypes
from qutebrowser.utils import message, usertypes, urlutils, utils, qtutils
from qutebrowser.misc import objects
from qutebrowser.browser.network import pac


application_factory: Optional["ProxyFactory"] = None


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
        qtutils.QT_NONE)


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
        if proxy.type() == QNetworkProxy.ProxyType.NoProxy:
            return

        capabilities = proxy.capabilities()
        lookup_cap = QNetworkProxy.Capability.HostNameLookupCapability
        if config.val.content.proxy_dns_requests:
            capabilities |= lookup_cap
        else:
            capabilities &= ~lookup_cap
        proxy.setCapabilities(capabilities)

    def queryProxy(self, query: QNetworkProxyQuery = QNetworkProxyQuery()) -> list[QNetworkProxy]:
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
            # ref. https://doc.qt.io/qt-6/qnetworkproxyfactory.html#systemProxyForQuery
            proxies = QNetworkProxyFactory.systemProxyForQuery(query)
        elif isinstance(proxy, pac.PACFetcher):
            if objects.backend == usertypes.Backend.QtWebEngine:
                # Looks like query.url() is always invalid on QtWebEngine...
                proxy = urlutils.proxy_from_url(QUrl('direct://'))
                assert not isinstance(proxy, pac.PACFetcher)
                proxies = [proxy]
            elif objects.backend == usertypes.Backend.QtWebKit:
                proxies = proxy.resolve(query)
            else:
                raise utils.Unreachable(objects.backend)
        else:
            proxies = [proxy]
        for proxy in proxies:
            self._set_capabilities(proxy)
        return proxies
