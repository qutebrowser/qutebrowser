# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""APIs related to intercepting/blocking requests."""

from qutebrowser.extensions import interceptors
# pylint: disable=unused-import
from qutebrowser.extensions.interceptors import Request


#: Type annotation for an interceptor function.
InterceptorType = interceptors.InterceptorType

#: Possible resource types for requests sent to interceptor.
ResourceType = interceptors.ResourceType


def register(interceptor: InterceptorType) -> None:
    """Register a request interceptor.

    Whenever a request happens, the interceptor gets called with a
    :class:`Request` object.

    Example::

        def intercept(request: interceptor.Request) -> None:
            if request.request_url.host() == 'badhost.example.com':
                request.block()
    """
    interceptors.register(interceptor)
