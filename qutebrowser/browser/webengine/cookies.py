# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Filter for QtWebEngine cookies."""

from qutebrowser.config import config
from qutebrowser.utils import utils, log
from qutebrowser.misc import objects


@utils.prevent_exceptions(False)  # Runs in I/O thread
def _accept_cookie(request):
    """Check whether the given cookie should be accepted."""
    url = request.firstPartyUrl
    if not url.isValid():
        url = None

    accept = config.instance.get('content.cookies.accept',
                                 url=url)

    if 'log-cookies' in objects.debug_flags:
        first_party_str = ("<unknown>" if not request.firstPartyUrl.isValid()
                           else request.firstPartyUrl.toDisplayString())
        origin_str = ("<unknown>" if not request.origin.isValid()
                      else request.origin.toDisplayString())
        log.network.debug('Cookie from origin {} on {} (third party: {}) '
                          '-> applying setting {}'
                          .format(origin_str, first_party_str, request.thirdParty,
                                  accept))

    if accept == 'all':
        return True
    elif accept in ['no-3rdparty', 'no-unknown-3rdparty']:
        return not request.thirdParty
    elif accept == 'never':
        return False
    else:
        raise utils.Unreachable


def install_filter(profile):
    """Install the cookie filter on the given profile."""
    profile.cookieStore().setCookieFilter(_accept_cookie)
