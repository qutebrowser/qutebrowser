# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

MYPY = False
if MYPY:
    # pylint: disable=unused-import,useless-suppression
    from PyQt5.QtCore import QUrl


class ResourceType(enum.Enum):
    """Possible request types that can be received.

    Currently corresponds to the QWebEngineUrlRequestInfo Enum:
    https://doc.qt.io/qt-5/qwebengineurlrequestinfo.html#ResourceType-enum
    """

    MAIN_FRAME = 1
    SUB_FRAME = 2
    STYLESHEET = 3
    SCRIPT = 4
    IMAGE = 5
    FONT_RESOURCE = 6
    SUB_RESOURCE = 7
    OBJECT = 8
    MEDIA = 9
    WORKER = 10
    SHARED_WORKER = 11
    PREFETCH = 12
    FAVICON = 13
    XHR = 14
    PING = 15
    SERVICE_WORKER = 16
    CSP_REPORT = 17
    PLUGIN_RESOURCE = 18
    UNKNOWN = 19


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

    def block(self) -> None:
        """Block this request."""
        self.is_blocked = True


#: Type annotation for an interceptor function.
InterceptorType = typing.Callable[[Request], None]


_interceptors = []  # type: typing.List[InterceptorType]


def register(interceptor: InterceptorType) -> None:
    _interceptors.append(interceptor)


def run(info: Request) -> None:
    for interceptor in _interceptors:
        interceptor(info)
