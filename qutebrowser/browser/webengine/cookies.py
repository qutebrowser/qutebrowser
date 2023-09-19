# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

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
