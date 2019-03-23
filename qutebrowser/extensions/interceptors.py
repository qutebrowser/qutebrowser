# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2019 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Infrastructure for intercepting requests."""

import typing
import enum

import attr

from PyQt5.QtCore import QUrl


class ResourceType(enum.Enum):
    """Possible request types that can be received.

    Currently corresponds to the QWebEngineUrlRequestInfo Enum:
    https://doc.qt.io/qt-5/qwebengineurlrequestinfo.html#ResourceType-enum
    """

    main_frame = 0
    sub_frame = 1
    stylesheet = 2
    script = 3
    image = 4
    font_resource = 5
    sub_resource = 6
    object = 7
    media = 8
    worker = 9
    shared_worker = 10
    prefetch = 11
    favicon = 12
    xhr = 13
    ping = 14
    service_worker = 15
    csp_report = 16
    plugin_resource = 17
    unknown = 255


@attr.s
class Request:

    """A request which can be intercepted/blocked."""

    #: The URL of the page being shown.
    first_party_url = attr.ib()  # type: QUrl

    #: The URL of the file being requested.
    request_url = attr.ib()  # type: QUrl

    is_blocked = attr.ib(False)  # type: bool

    #: The resource type of the request. None if not supported on this backend.
    resource_type = attr.ib(None)  # type: typing.Optional[ResourceType]

    #: Private attribute to a method which implements redirection
    _redirect_method = attr.ib(
        default=None, type=typing.Optional[typing.Callable[[QUrl], bool]])

    def block(self) -> None:
        """Block this request."""
        self.is_blocked = True

    def redirect(self, url: QUrl) -> bool:
        """Redirect this request.

        Only some types of requests can be successfully redirected.
        Improper use of this method can result in redirect loops.

        Args:
            url: The QUrl to try to redirect to.

        Return:
            False if the redirection was known to be unsupported, else True.
            A True return value does not guarantee success.
        """
        if self._redirect_method is None:
            return False
        retval = self._redirect_method(url)
        # Once firing a redirect, refuse any other attempt
        self._redirect_method = None
        return retval


#: Type annotation for an interceptor function.
InterceptorType = typing.Callable[[Request], None]


_interceptors = []  # type: typing.List[InterceptorType]


def register(interceptor: InterceptorType) -> None:
    _interceptors.append(interceptor)


def run(info: Request) -> None:
    for interceptor in _interceptors:
        interceptor(info)
