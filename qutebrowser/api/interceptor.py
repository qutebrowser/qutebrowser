# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
