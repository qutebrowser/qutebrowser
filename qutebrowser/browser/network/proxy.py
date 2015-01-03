# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


from PyQt5.QtNetwork import QNetworkProxy, QNetworkProxyFactory

from qutebrowser.config import config, configtypes


def init():
    """Set the application wide proxy factory."""
    QNetworkProxyFactory.setApplicationProxyFactory(ProxyFactory())


class ProxyFactory(QNetworkProxyFactory):

    """Factory for proxies to be used by qutebrowser."""

    def queryProxy(self, query):
        """Get the QNetworkProxies for a query.

        Args:
            query: The QNetworkProxyQuery to get a proxy for.

        Return:
            A list of QNetworkProxy objects in order of preference.
        """
        proxy = config.get('network', 'proxy')
        if proxy is configtypes.SYSTEM_PROXY:
            proxies = QNetworkProxyFactory.systemProxyForQuery(query)
        else:
            proxies = [proxy]
        for p in proxies:
            if p.type() != QNetworkProxy.NoProxy:
                capabilities = p.capabilities()
                if config.get('network', 'proxy-dns-requests'):
                    capabilities |= QNetworkProxy.HostNameLookupCapability
                else:
                    capabilities &= ~QNetworkProxy.HostNameLookupCapability
                p.setCapabilities(capabilities)
        return proxies
