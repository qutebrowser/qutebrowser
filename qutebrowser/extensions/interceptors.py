# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Infrastructure for intercepting requests."""

import enum
import dataclasses
from typing import Callable, List, Optional

from qutebrowser.qt.core import QUrl


class ResourceType(enum.Enum):
    """Possible request types that can be received.

    Currently corresponds to the QWebEngineUrlRequestInfo Enum:
    https://doc.qt.io/qt-6/qwebengineurlrequestinfo.html#ResourceType-enum
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
    # 18 is "preload", deprecated in Chromium
    preload_main_frame = 19
    preload_sub_frame = 20
    websocket = 254
    unknown = 255


class RedirectException(Exception):
    """Raised when the request was invalid, or a request was already made."""


@dataclasses.dataclass
class Request:

    """A request which can be intercepted/blocked."""

    #: The URL of the page being shown.
    first_party_url: Optional[QUrl]

    #: The URL of the file being requested.
    request_url: QUrl

    is_blocked: bool = False

    #: The resource type of the request. None if not supported on this backend.
    resource_type: Optional[ResourceType] = None

    def block(self) -> None:
        """Block this request."""
        self.is_blocked = True

    def redirect(self, url: QUrl, *, ignore_unsupported: bool = False) -> None:
        """Redirect this request.

        Only some types of requests can be successfully redirected.
        Improper use of this method can result in redirect loops.

        This method will throw a RedirectException if the request was not possible.

        Args:
            url: The QUrl to try to redirect to.
            ignore_unsupported: If set to True, request methods which can't be
                redirected (such as POST) are silently ignored instead of throwing an
                exception.
        """
        # Will be overridden if the backend supports redirection
        raise NotImplementedError


#: Type annotation for an interceptor function.
InterceptorType = Callable[[Request], None]


_interceptors: List[InterceptorType] = []


def register(interceptor: InterceptorType) -> None:
    _interceptors.append(interceptor)


def run(info: Request) -> None:
    for interceptor in _interceptors:
        interceptor(info)
