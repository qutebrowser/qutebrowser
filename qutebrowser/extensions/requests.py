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

"""Infrastructure for filtering requests."""

import typing

import attr


@attr.s
class Request:

    """A request which can be blocked."""

    first_party_url = attr.ib()  # type: QUrl
    request_url = attr.ib()  # type: QUrl
    is_blocked = attr.ib(False)  # type: bool

    def block(self):
        """Block this request."""
        self.is_blocked = True


RequestFilterType = typing.Callable[[Request], None]


_request_filters = []  # type: typing.List[RequestFilterType]


def register_filter(reqfilter: RequestFilterType) -> None:
    _request_filters.append(reqfilter)


def run_filters(info):
    for reqfilter in _request_filters:
        reqfilter(info)
