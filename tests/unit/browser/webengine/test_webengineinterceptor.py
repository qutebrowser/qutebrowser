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

"""Test interceptor.py for webengine."""


import pytest

pytest.importorskip('qutebrowser.qt.webenginecore')

from qutebrowser.qt.webenginecore import QWebEngineUrlRequestInfo

from qutebrowser.browser.webengine import interceptor
from qutebrowser.utils import qtutils
from helpers import testutils


def test_no_missing_resource_types():
    request_interceptor = interceptor.RequestInterceptor()
    qb_keys = set(request_interceptor._resource_types.keys())
    qt_keys = set(testutils.enum_members(
        QWebEngineUrlRequestInfo,
        QWebEngineUrlRequestInfo.ResourceType,
    ).values())
    assert qt_keys == qb_keys


def test_resource_type_values():
    request_interceptor = interceptor.RequestInterceptor()
    for qt_value, qb_item in request_interceptor._resource_types.items():
        assert qtutils.extract_enum_val(qt_value) == qb_item.value
