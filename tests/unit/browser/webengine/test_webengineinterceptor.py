# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

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
