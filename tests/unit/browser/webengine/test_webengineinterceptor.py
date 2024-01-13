# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test interceptor.py for webengine."""


import pytest
import pytest_mock

pytest.importorskip("qutebrowser.qt.webenginecore")

from qutebrowser.qt.core import QUrl, QByteArray
from qutebrowser.qt.webenginecore import QWebEngineUrlRequestInfo

from qutebrowser.browser.webengine import interceptor
from qutebrowser.extensions import interceptors
from qutebrowser.utils import qtutils
from helpers import testutils


def test_no_missing_resource_types():
    request_interceptor = interceptor.RequestInterceptor()
    qb_keys = set(request_interceptor._resource_types.keys())
    qt_keys = set(
        testutils.enum_members(
            QWebEngineUrlRequestInfo,
            QWebEngineUrlRequestInfo.ResourceType,
        ).values()
    )
    assert qt_keys == qb_keys


def test_resource_type_values():
    request_interceptor = interceptor.RequestInterceptor()
    for qt_value, qb_item in request_interceptor._resource_types.items():
        assert qtutils.extract_enum_val(qt_value) == qb_item.value


@pytest.fixture
def we_request(  # a shrubbery!
    mocker: pytest_mock.MockerFixture,
) -> interceptor.WebEngineRequest:
    qt_info = mocker.Mock(spec=QWebEngineUrlRequestInfo)
    qt_info.requestMethod.return_value = QByteArray(b"GET")
    first_party_url = QUrl("https://firstparty.example.org/")
    request_url = QUrl("https://request.example.org/")
    return interceptor.WebEngineRequest(
        first_party_url=first_party_url,
        request_url=request_url,
        webengine_info=qt_info,
    )


def test_block(we_request: interceptor.WebEngineRequest):
    assert not we_request.is_blocked
    we_request.block()
    assert we_request.is_blocked


class TestRedirect:
    REDIRECT_URL = QUrl("https://redirect.example.com/")

    def test_redirect(self, we_request: interceptor.WebEngineRequest):
        assert not we_request._redirected
        we_request.redirect(self.REDIRECT_URL)
        assert we_request._redirected
        we_request._webengine_info.redirect.assert_called_once_with(self.REDIRECT_URL)

    def test_twice(self, we_request: interceptor.WebEngineRequest):
        we_request.redirect(self.REDIRECT_URL)
        with pytest.raises(
            interceptors.RedirectException,
            match=r"Request already redirected.",
        ):
            we_request.redirect(self.REDIRECT_URL)
        we_request._webengine_info.redirect.assert_called_once_with(self.REDIRECT_URL)

    def test_invalid_method(self, we_request: interceptor.WebEngineRequest):
        we_request._webengine_info.requestMethod.return_value = QByteArray(b"POST")
        with pytest.raises(
            interceptors.RedirectException,
            match=(
                r"Request method b'POST' for https://request.example.org/ does not "
                r"support redirection."
            ),
        ):
            we_request.redirect(self.REDIRECT_URL)
        assert not we_request._webengine_info.redirect.called

    def test_invalid_method_ignore_unsupported(
        self,
        we_request: interceptor.WebEngineRequest,
        caplog: pytest.LogCaptureFixture,
    ):
        we_request._webengine_info.requestMethod.return_value = QByteArray(b"POST")
        we_request.redirect(self.REDIRECT_URL, ignore_unsupported=True)
        assert caplog.messages == [
            "Request method b'POST' for https://request.example.org/ does not support "
            "redirection."
        ]
        assert not we_request._webengine_info.redirect.called

    def test_improperly_initialized(self, we_request: interceptor.WebEngineRequest):
        we_request._webengine_info = None
        with pytest.raises(
            interceptors.RedirectException,
            match=r"Request improperly initialized.",
        ):
            we_request.redirect(self.REDIRECT_URL)

    def test_invalid_url(self, we_request: interceptor.WebEngineRequest):
        url = QUrl()
        assert not url.isValid()
        with pytest.raises(
            interceptors.RedirectException,
            match=r"Redirect to invalid URL: PyQt\d\.QtCore\.QUrl\(''\) is not valid",
        ):
            we_request.redirect(url)
