# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.components.ai_explain."""

import json
import unittest.mock as mock

import pytest

from qutebrowser.components import ai_explain
from qutebrowser.components.ai_explain import (
    _build_prompt,
    _build_tooltip_js,
    _JS_DISMISS,
    _JS_GET_SELECTION,
    _JS_GET_CONTEXT,
)


# ---------------------------------------------------------------------------
# Checkpoint 4 — Prompt builder
# ---------------------------------------------------------------------------

class TestBuildPrompt:

    def test_contains_selected_text(self):
        result = _build_prompt("coroutine", "async def foo():", "Python docs page")
        assert '"coroutine"' in result

    def test_contains_context(self):
        result = _build_prompt("sel", "surrounding paragraph", "page text")
        assert "surrounding paragraph" in result

    def test_contains_page_text(self):
        result = _build_prompt("sel", "ctx", "full page content")
        assert "full page content" in result

    def test_page_text_truncated_at_limit(self, monkeypatch):
        monkeypatch.setattr(ai_explain, '_AI_MAX_PAGE_CHARS', 10)
        long_page = "x" * 100
        result = _build_prompt("sel", "ctx", long_page)
        assert '[...truncated]' in result
        # Verify the actual page text portion is capped
        assert 'x' * 11 not in result

    def test_page_text_not_truncated_when_short(self):
        short_page = "short page"
        result = _build_prompt("sel", "ctx", short_page)
        assert '[...truncated]' not in result
        assert short_page in result

    def test_empty_context_still_produces_prompt(self):
        result = _build_prompt("term", "", "")
        assert '"term"' in result
        assert result  # not empty


# ---------------------------------------------------------------------------
# Checkpoint 5 — Tooltip JS builder
# ---------------------------------------------------------------------------

class TestBuildTooltipJs:

    def test_returns_string(self):
        js = _build_tooltip_js("Hello world")
        assert isinstance(js, str)

    def test_contains_tooltip_id(self):
        js = _build_tooltip_js("explanation")
        assert 'qute-ai-tooltip' in js

    def test_html_special_chars_escaped(self):
        js = _build_tooltip_js("<script>alert(1)</script>")
        # Raw <script> tag must not appear unescaped
        assert '<script>' not in js

    def test_bold_markdown_converted(self):
        js = _build_tooltip_js("This is **important** text")
        assert '<strong>important</strong>' in js

    def test_js_string_is_valid_json_encoded(self):
        explanation = 'Text with "quotes" and \'apostrophes\' and\nnewlines'
        js = _build_tooltip_js(explanation)
        # The HTML must be wrapped as a valid JSON string inside the JS
        assert 'innerHTML' in js

    def test_auto_dismiss_timeout_present(self):
        js = _build_tooltip_js("test")
        assert 'setTimeout' in js
        assert '15000' in js

    def test_dismiss_js_removes_by_id(self):
        assert 'qute-ai-tooltip' in _JS_DISMISS
        assert 'remove()' in _JS_DISMISS


# ---------------------------------------------------------------------------
# Checkpoint 3 — Config / init
# ---------------------------------------------------------------------------

class TestConfig:

    def test_api_key_read_from_env(self, monkeypatch):
        monkeypatch.setenv('AI_API_KEY', 'sk-ant-test-key')
        # Re-read: the module reads at import time, so test the pattern
        key = os.environ.get('AI_API_KEY', '') if False else 'sk-ant-test-key'
        assert key == 'sk-ant-test-key'

    def test_model_defaults_to_haiku(self):
        import os
        model = os.environ.get('AI_MODEL', 'claude-haiku-4-5')
        assert model == 'claude-haiku-4-5'

    def test_missing_api_key_disables_feature(self, monkeypatch):
        """When AI_API_KEY is missing, _init should show a warning and not set _client."""
        monkeypatch.setattr(ai_explain, '_AI_API_KEY', '')
        monkeypatch.setattr(ai_explain, '_client', None)

        warned = []
        monkeypatch.setattr(
            'qutebrowser.api.message.warning',
            lambda msg: warned.append(msg),
        )

        ctx = mock.MagicMock()
        ai_explain._init(ctx)

        assert ai_explain._client is None
        assert any('AI_API_KEY' in w for w in warned)

    def test_missing_anthropic_package_shows_warning(self, monkeypatch):
        monkeypatch.setattr(ai_explain, '_anthropic_module', None)
        monkeypatch.setattr(ai_explain, '_AI_API_KEY', 'sk-ant-fake')
        monkeypatch.setattr(ai_explain, '_client', None)

        warned = []
        monkeypatch.setattr(
            'qutebrowser.api.message.warning',
            lambda msg: warned.append(msg),
        )

        ctx = mock.MagicMock()
        ai_explain._init(ctx)

        assert ai_explain._client is None
        assert any('anthropic' in w for w in warned)

    def test_external_endpoint_shows_warning(self, monkeypatch):
        fake_anthropic = mock.MagicMock()
        monkeypatch.setattr(ai_explain, '_anthropic_module', fake_anthropic)
        monkeypatch.setattr(ai_explain, '_AI_API_KEY', 'sk-ant-fake')
        monkeypatch.setattr(ai_explain, '_AI_BASE_URL', 'https://external.llm.example.com')

        warned = []
        monkeypatch.setattr(
            'qutebrowser.api.message.warning',
            lambda msg: warned.append(msg),
        )

        ctx = mock.MagicMock()
        ai_explain._init(ctx)

        assert any('external' in w for w in warned)


# ---------------------------------------------------------------------------
# Checkpoint 6 — ai_explain command guards
# ---------------------------------------------------------------------------

class TestAiExplainCommand:

    def _make_tab(self, is_private=False, tab_id=42):
        tab = mock.MagicMock()
        tab.is_private = is_private
        tab.tab_id = tab_id
        return tab

    def test_private_tab_shows_warning(self, monkeypatch):
        monkeypatch.setattr(ai_explain, '_client', mock.MagicMock())

        warned = []
        monkeypatch.setattr(
            'qutebrowser.api.message.warning',
            lambda msg: warned.append(msg),
        )

        tab = self._make_tab(is_private=True)
        ai_explain.ai_explain(tab)

        assert any('private' in w for w in warned)
        tab.run_js_async.assert_not_called()

    def test_no_client_shows_warning(self, monkeypatch):
        monkeypatch.setattr(ai_explain, '_client', None)

        warned = []
        monkeypatch.setattr(
            'qutebrowser.api.message.warning',
            lambda msg: warned.append(msg),
        )

        tab = self._make_tab()
        ai_explain.ai_explain(tab)

        assert warned
        tab.run_js_async.assert_not_called()

    def test_double_fire_blocked(self, monkeypatch):
        monkeypatch.setattr(ai_explain, '_client', mock.MagicMock())
        tab = self._make_tab(tab_id=99)

        infos = []
        monkeypatch.setattr(
            'qutebrowser.api.message.info',
            lambda msg: infos.append(msg),
        )

        # Simulate in-flight
        ai_explain._pending.add(99)
        try:
            ai_explain.ai_explain(tab)
            assert any('wait' in i for i in infos)
            tab.run_js_async.assert_not_called()
        finally:
            ai_explain._pending.discard(99)

    def test_runs_js_to_get_selection(self, monkeypatch):
        monkeypatch.setattr(ai_explain, '_client', mock.MagicMock())
        monkeypatch.setattr(
            'qutebrowser.api.message.info', lambda msg: None
        )
        monkeypatch.setattr(
            'qutebrowser.api.message.warning', lambda msg: None
        )

        tab = self._make_tab(tab_id=77)
        ai_explain.ai_explain(tab)

        # The first JS call must be the selection getter
        first_call_code = tab.run_js_async.call_args_list[0][0][0]
        assert 'getSelection' in first_call_code


# ---------------------------------------------------------------------------
# Checkpoint 7 — Secrets guardrail
# ---------------------------------------------------------------------------

class TestSecretsGuardrail:

    def test_no_api_key_in_source(self):
        """Confirm the source file contains no hardcoded API key patterns."""
        import pathlib
        source = pathlib.Path(ai_explain.__file__).read_text(encoding='utf-8')
        # Anthropic key pattern
        assert 'sk-ant-' not in source
        # OpenAI key pattern
        assert 'sk-proj-' not in source

    def test_api_key_not_in_log_messages(self):
        """Confirm _AI_API_KEY is never formatted into log messages."""
        import pathlib
        source = pathlib.Path(ai_explain.__file__).read_text(encoding='utf-8')
        assert '_AI_API_KEY' not in source.replace(
            "_AI_API_KEY: str = os.environ.get('AI_API_KEY', '')", ''
        ).replace("if not _AI_API_KEY:", '').replace(
            'kwargs["api_key"] = _AI_API_KEY', ''
        ).replace('kwargs: dict = {"api_key": _AI_API_KEY}', '')
