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

"""Test interceptor.py for webengine."""


import pytest

pytest.importorskip('PyQt5.QtWebEngineWidgets')

from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInfo

from qutebrowser.browser.webengine import interceptor


def test_no_missing_resource_types():
    request_interceptor = interceptor.RequestInterceptor()
    qb_keys = request_interceptor._resource_types.keys()
    qt_keys = {i for i in vars(QWebEngineUrlRequestInfo).values()
               if isinstance(i, QWebEngineUrlRequestInfo.ResourceType)}
    assert qt_keys == qb_keys


def test_resource_type_values():
    request_interceptor = interceptor.RequestInterceptor()
    for qt_value, qb_item in request_interceptor._resource_types.items():
        assert qt_value == qb_item.value
