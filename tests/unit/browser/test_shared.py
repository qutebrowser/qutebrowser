# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

import pytest

from qutebrowser.qt.core import QUrl
from qutebrowser.browser import shared
from qutebrowser.utils import usertypes


@pytest.mark.parametrize('dnt, accept_language, custom_headers, expected', [
    # DNT
    (True, None, {}, {b'DNT': b'1'}),
    (False, None, {}, {b'DNT': b'0'}),
    (None, None, {}, {}),
    # Accept-Language
    (False, 'de, en', {}, {b'DNT': b'0', b'Accept-Language': b'de, en'}),
    # Custom headers
    (False, None, {'X-Qute': 'yes'}, {b'DNT': b'0', b'X-Qute': b'yes'}),
    # Mixed
    (False, 'de, en', {'X-Qute': 'yes'}, {b'DNT': b'0',
                                          b'Accept-Language': b'de, en',
                                          b'X-Qute': b'yes'}),
])
def test_custom_headers(config_stub, dnt, accept_language, custom_headers,
                        expected):
    headers = config_stub.val.content.headers
    headers.do_not_track = dnt
    headers.accept_language = accept_language
    headers.custom = custom_headers

    expected_items = sorted(expected.items())
    assert shared.custom_headers(url=None) == expected_items


@pytest.mark.parametrize("url, fallback, expected", [
    # url is never None in the wild, mostly sanity check
    (None, True, True),
    (None, False, True),
    (QUrl("http://example.org"), True, True),
    (QUrl("http://example.org"), False, False),
])
def test_accept_language_no_fallback(config_stub, url, fallback, expected):
    config_stub.val.content.headers.accept_language = "de, en"
    headers = shared.custom_headers(url=url, fallback_accept_language=fallback)
    assert (b"Accept-Language" in dict(headers)) == expected


@pytest.mark.parametrize(
    (
        "levels_setting, excludes_setting, level, source, msg, expected_ret, "
        "expected_level"
    ), [
        # Empty settings
        (
            {},
            {},
            usertypes.JsLogLevel.error,
            "qute:test",
            "msg",
            False,
            None,
        ),
        # Simple error message
        (
            {"qute:*": ["error"]},
            {},
            usertypes.JsLogLevel.error,
            "qute:bla",
            "msg",
            True,
            usertypes.MessageLevel.error,
        ),
        # Unfiltered error message
        (
            {"qute:*": ["error"]},
            {"qute:*": ["filter*"]},
            usertypes.JsLogLevel.error,
            "qute:bla",
            "notfiltered",
            True,
            usertypes.MessageLevel.error,
        ),
        # Filtered error message
        (
            {"qute:*": ["error"]},
            {"qute:*": ["filter*"]},
            usertypes.JsLogLevel.error,
            "qute:bla",
            "filtered",
            False,
            None,
        ),
        # Filter with different domain
        (
            {"qute:*": ["error"]},
            {"qutie:*": ["*"]},
            usertypes.JsLogLevel.error,
            "qute:bla",
            "msg",
            True,
            usertypes.MessageLevel.error,
        ),
        # Info message, not logged
        (
            {"qute:*": ["error"]},
            {},
            usertypes.JsLogLevel.info,
            "qute:bla",
            "msg",
            False,
            None,
        ),
        # Info message, logged
        (
            {"qute:*": ["error", "info"]},
            {},
            usertypes.JsLogLevel.info,
            "qute:bla",
            "msg",
            True,
            usertypes.MessageLevel.info,
        ),
    ]
)
def test_js_log_to_ui(
    config_stub, message_mock, caplog,
    levels_setting, excludes_setting, level, source, msg, expected_ret, expected_level,
):
    config_stub.val.content.javascript.log_message.levels = levels_setting
    config_stub.val.content.javascript.log_message.excludes = excludes_setting

    with caplog.at_level(logging.ERROR):
        ret = shared._js_log_to_ui(level=level, source=source, line=0, msg=msg)

    assert ret == expected_ret

    if expected_level is not None:
        assert message_mock.getmsg(expected_level).text == f"JS: [{source}:0] {msg}"
    else:
        assert not message_mock.messages
