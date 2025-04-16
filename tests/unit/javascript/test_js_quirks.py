# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for QtWebEngine JavaScript quirks.

This tests JS functionality which is missing in older QtWebEngine releases, but we have
polyfills for. They should either pass because the polyfill is active, or pass because
the native functionality exists.
"""

import pathlib

import pytest
from qutebrowser.qt.core import QUrl

import qutebrowser
from qutebrowser.utils import usertypes
from qutebrowser.config import configdata


@pytest.mark.parametrize('base_url, source, expected', [
    pytest.param(
        QUrl(),
        '"This is a test".replaceAll("test", "fest")',
        "This is a fest",
        id='replace-all',
    ),
    pytest.param(
        QUrl(),
        '"This is a test".replaceAll(/[tr]est/g, "fest")',
        "This is a fest",
        id='replace-all-regex',
    ),
    pytest.param(
        QUrl(),
        '"This is a [test[".replaceAll("[", "<")',
        "This is a <test<",
        id='replace-all-reserved-string',
    ),
    pytest.param(
        QUrl("https://test.qutebrowser.org/linkedin"),
        '[1, 2, 3].at(1)',
        2,
        id='array-at',
    ),
])
def test_js_quirks(config_stub, js_tester_webengine, base_url, source, expected):
    config_stub.val.content.site_specific_quirks.skip = []
    js_tester_webengine.tab._scripts._inject_site_specific_quirks()
    js_tester_webengine.load('base.html', base_url=base_url)
    js_tester_webengine.run(source, expected, world=usertypes.JsWorld.main)


def test_js_quirks_match_files(webengine_tab):
    quirks_path = pathlib.Path(qutebrowser.__file__).parent / "javascript" / "quirks"
    suffix = ".user.js"
    quirks_files = {p.name.removesuffix(suffix) for p in quirks_path.glob(f"*{suffix}")}
    quirks_code = {q.filename for q in webengine_tab._scripts._get_quirks()}
    assert quirks_code == quirks_files


def test_js_quirks_match_settings(webengine_tab, configdata_init):
    quirks_code = {q.name for q in webengine_tab._scripts._get_quirks()}

    opt = configdata.DATA["content.site_specific_quirks.skip"]
    valid_values = opt.typ.get_valid_values()
    assert valid_values is not None
    quirks_config = {
        val
        for val in valid_values
        # some JS quirks are actually only setting the user agent, so we include
        # those as well.
        if val.startswith("js-") or (val.startswith("ua-") and val in quirks_code)
    }

    assert quirks_code == quirks_config
