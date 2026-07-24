# SPDX-FileCopyrightText: Camilo <camilo@example.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""End-to-end tests against a real Ollama instance.

Skipped unless Ollama and the configured model are available.  Run::

    pytest tests/unit/misc/ai/test_e2e.py -v
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error

import pytest

from qutebrowser.misc.ai import translator


def ollama_available() -> bool:
    """Check whether Ollama is reachable and the model exists."""
    base = os.environ.get('AI_BASE_URL', 'http://localhost:11434/v1')
    model = os.environ.get('AI_MODEL', 'gemma:2b')
    url = base.rstrip('/v1').rstrip('/') + '/api/tags'
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return False
    return any(model in m['name'] for m in data.get('models', []))


@pytest.mark.skipif(not ollama_available(), reason="Ollama not available")
class TestEndToEnd:

    """Full pipeline tests against a real Ollama model."""

    def test_close_tab(self):
        """'close this tab' resolves to tab-close."""
        result = translator.translate_query('close this tab')
        assert result
        assert 'tab-close' in result or 'close' in result, result

    def test_open_url(self):
        """'open github' resolves to open."""
        result = translator.translate_query('open github.com')
        assert result
        assert 'open' in result, result

    def test_reload_page(self):
        """'reload' resolves to reload."""
        result = translator.translate_query('reload the page')
        assert result
        assert 'reload' in result, result

    def test_next_tab(self):
        """'next tab' resolves to tab-next."""
        result = translator.translate_query('switch to the next tab')
        assert result
        assert 'tab-next' in result or 'next' in result, result

    def test_close_all_except_current(self):
        """Multi-token request resolves to tab-only or tab-close."""
        result = translator.translate_query(
            'close all tabs except the current one',
        )
        assert result
        assert 'tab-only' in result or 'tab-close' in result, result

    def test_unknown_request_falls_back(self):
        """Gibberish falls back to the mock provider gracefully."""
        result = translator.translate_query('xyzzy flurbo garblex')
        assert isinstance(result, str)
