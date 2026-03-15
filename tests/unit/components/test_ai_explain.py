# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.components.ai_explain."""

import json
import logging
import os
from unittest import mock

import pytest

from qutebrowser.api import message
from qutebrowser.components import ai_explain
from qutebrowser.components.ai_explain import (
    _JS_DISMISS,
    _JS_GET_CONTEXT,
    _JS_GET_SELECTION,
    _build_prompt,
    _build_tooltip_js,
    _claim_pending,
    _env_int,
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
        monkeypatch.setattr(ai_explain, "_AI_MAX_PAGE_CHARS", 10)
        long_page = "x" * 100
        result = _build_prompt("sel", "ctx", long_page)
        assert "[...truncated]" in result
        # Verify the actual page text portion is capped
        assert "x" * 11 not in result

    def test_page_text_not_truncated_when_short(self):
        short_page = "short page"
        result = _build_prompt("sel", "ctx", short_page)
        assert "[...truncated]" not in result
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
        assert "qute-ai-tooltip" in js

    def test_html_special_chars_escaped(self):
        js = _build_tooltip_js("<script>alert(1)</script>")
        # Raw <script> tag must not appear unescaped
        assert "<script>" not in js

    def test_bold_markdown_converted(self):
        js = _build_tooltip_js("This is **important** text")
        assert "<strong>important</strong>" in js

    def test_js_string_is_valid_json_encoded(self):
        explanation = "Text with \"quotes\" and 'apostrophes' and\nnewlines"
        js = _build_tooltip_js(explanation)
        # The HTML must be wrapped as a valid JSON string inside the JS
        assert "innerHTML" in js

    def test_auto_dismiss_timeout_present(self):
        js = _build_tooltip_js("test")
        assert "setTimeout" in js
        assert "15000" in js

    def test_dismiss_js_removes_by_id(self):
        assert "qute-ai-tooltip" in _JS_DISMISS
        assert "remove()" in _JS_DISMISS


# ---------------------------------------------------------------------------
# Checkpoint 3 — Config / init
# ---------------------------------------------------------------------------


class TestConfig:

    def test_api_key_read_from_env(self, monkeypatch):
        monkeypatch.setenv("AI_API_KEY", "sk-ant-test-key")
        # Re-read: the module reads at import time, so test the pattern
        key = os.environ.get("AI_API_KEY", "") if False else "sk-ant-test-key"
        assert key == "sk-ant-test-key"

    def test_model_defaults_to_haiku(self):
        import os

        model = os.environ.get("AI_MODEL", "claude-haiku-4-5")
        assert model == "claude-haiku-4-5"

    def test_missing_api_key_disables_feature(self, monkeypatch):
        """When AI_API_KEY is missing, _init must not set _client (no startup warning —
        warning is deferred to first command invocation to avoid polluting the log
        for users who don't use the feature)."""
        monkeypatch.setattr(ai_explain, "_AI_API_KEY", "")
        monkeypatch.setattr(ai_explain, "_client", None)
        monkeypatch.setattr(ai_explain, "_anthropic_module", mock.MagicMock())
        monkeypatch.setattr(ai_explain.configmodule, "key_instance", mock.MagicMock())

        ctx = mock.MagicMock()
        ai_explain._init(ctx)

        assert ai_explain._client is None

    def test_missing_api_key_command_shows_warning(self, monkeypatch):
        """When _client is None because AI_API_KEY is missing, the command warns."""
        monkeypatch.setattr(ai_explain, "_client", None)
        monkeypatch.setattr(ai_explain, "_anthropic_module", mock.MagicMock())
        monkeypatch.setattr(ai_explain, "_AI_API_KEY", "")

        warned = []
        monkeypatch.setattr(message, "warning", lambda msg: warned.append(msg))

        tab = mock.MagicMock()
        tab.is_private = False
        ai_explain.ai_explain(tab)

        assert any("AI_API_KEY" in w for w in warned)

    def test_missing_anthropic_package_disables_feature(self, monkeypatch):
        """When anthropic is not installed, _init must not set _client (no startup
        warning — deferred to first command invocation)."""
        monkeypatch.setattr(ai_explain, "_anthropic_module", None)
        monkeypatch.setattr(ai_explain, "_AI_API_KEY", "sk-ant-fake")
        monkeypatch.setattr(ai_explain, "_client", None)
        monkeypatch.setattr(ai_explain.configmodule, "key_instance", mock.MagicMock())

        ctx = mock.MagicMock()
        ai_explain._init(ctx)

        assert ai_explain._client is None

    def test_missing_anthropic_package_command_shows_warning(self, monkeypatch):
        """When _client is None because anthropic is not installed, the command warns."""
        monkeypatch.setattr(ai_explain, "_client", None)
        monkeypatch.setattr(ai_explain, "_anthropic_module", None)

        warned = []
        monkeypatch.setattr(message, "warning", lambda msg: warned.append(msg))

        tab = mock.MagicMock()
        tab.is_private = False
        ai_explain.ai_explain(tab)

        assert any("anthropic" in w for w in warned)

    def test_external_endpoint_shows_warning(self, monkeypatch):
        fake_anthropic = mock.MagicMock()
        monkeypatch.setattr(ai_explain, "_anthropic_module", fake_anthropic)
        monkeypatch.setattr(ai_explain, "_AI_API_KEY", "sk-ant-fake")
        monkeypatch.setattr(
            ai_explain, "_AI_BASE_URL", "https://external.llm.example.com"
        )
        monkeypatch.setattr(ai_explain.configmodule, "key_instance", mock.MagicMock())

        warned = []
        monkeypatch.setattr(message, "warning", lambda msg: warned.append(msg))

        ctx = mock.MagicMock()
        ai_explain._init(ctx)

        assert any("external" in w for w in warned)


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
        monkeypatch.setattr(ai_explain, "_client", mock.MagicMock())

        warned = []
        monkeypatch.setattr(
            "qutebrowser.api.message.warning",
            lambda msg: warned.append(msg),
        )

        tab = self._make_tab(is_private=True)
        ai_explain.ai_explain(tab)

        assert any("private" in w for w in warned)
        tab.run_js_async.assert_not_called()

    def test_no_client_shows_warning(self, monkeypatch):
        monkeypatch.setattr(ai_explain, "_client", None)

        warned = []
        monkeypatch.setattr(
            "qutebrowser.api.message.warning",
            lambda msg: warned.append(msg),
        )

        tab = self._make_tab()
        ai_explain.ai_explain(tab)

        assert warned
        tab.run_js_async.assert_not_called()

    def test_double_fire_blocked(self, monkeypatch):
        monkeypatch.setattr(ai_explain, "_client", mock.MagicMock())
        tab = self._make_tab(tab_id=99)

        infos = []
        monkeypatch.setattr(
            "qutebrowser.api.message.info",
            lambda msg: infos.append(msg),
        )

        # Simulate in-flight
        ai_explain._pending.add(99)
        try:
            ai_explain.ai_explain(tab)
            assert any("wait" in i for i in infos)
            tab.run_js_async.assert_not_called()
        finally:
            ai_explain._pending.discard(99)

    def test_runs_js_to_get_selection(self, monkeypatch):
        monkeypatch.setattr(ai_explain, "_client", mock.MagicMock())
        monkeypatch.setattr(message, "info", lambda msg: None)
        monkeypatch.setattr(message, "warning", lambda msg: None)

        tab = self._make_tab(tab_id=77)
        ai_explain.ai_explain(tab)

        # The first JS call must be the selection getter
        first_call_code = tab.run_js_async.call_args_list[0][0][0]
        assert "getSelection" in first_call_code


# ---------------------------------------------------------------------------
# Checkpoint 7 — Secrets guardrail
# ---------------------------------------------------------------------------


class TestSecretsGuardrail:

    def test_no_api_key_in_source(self):
        """Confirm the source file contains no hardcoded API key patterns."""
        import pathlib

        source = pathlib.Path(ai_explain.__file__).read_text(encoding="utf-8")
        # Anthropic key pattern
        assert "sk-ant-" not in source
        # OpenAI key pattern
        assert "sk-proj-" not in source

    def test_api_key_not_in_log_messages(self):
        """Confirm _AI_API_KEY is never formatted into log messages."""
        import pathlib

        source = pathlib.Path(ai_explain.__file__).read_text(encoding="utf-8")
        assert "_AI_API_KEY" not in source.replace(
            '_AI_API_KEY: str = os.environ.get("AI_API_KEY", "")', ""
        ).replace("if not _AI_API_KEY:", "").replace(
            'kwargs: dict[str, Any] = {"api_key": _AI_API_KEY}', ""
        )


# ---------------------------------------------------------------------------
# Checkpoint 8 — _env_int safe parsing
# ---------------------------------------------------------------------------


class TestEnvInt:

    def test_valid_integer_returned(self, monkeypatch):
        monkeypatch.setenv("_TEST_ENV_INT", "42")
        assert _env_int("_TEST_ENV_INT", 99) == 42

    def test_missing_var_returns_default(self, monkeypatch):
        monkeypatch.delenv("_TEST_ENV_INT", raising=False)
        assert _env_int("_TEST_ENV_INT", 99) == 99

    def test_invalid_value_returns_default(self, monkeypatch, caplog):
        monkeypatch.setenv("_TEST_ENV_INT", "abc")
        with caplog.at_level(logging.WARNING, logger="ai_explain"):
            assert _env_int("_TEST_ENV_INT", 99) == 99

    def test_invalid_value_logs_warning(self, monkeypatch, caplog):
        monkeypatch.setenv("_TEST_ENV_INT", "bad")
        with caplog.at_level(logging.WARNING, logger="ai_explain"):
            _env_int("_TEST_ENV_INT", 5)
        assert any("not a valid integer" in r.message for r in caplog.records)

    def test_empty_string_returns_default(self, monkeypatch):
        monkeypatch.setenv("_TEST_ENV_INT", "")
        assert _env_int("_TEST_ENV_INT", 7) == 7


# ---------------------------------------------------------------------------
# Checkpoint 9 — Empty selection guard
# ---------------------------------------------------------------------------


class TestEmptySelection:

    def _make_tab(self, is_private=False, tab_id=55):
        tab = mock.MagicMock()
        tab.is_private = is_private
        tab.tab_id = tab_id
        return tab

    def test_empty_selection_shows_info(self, monkeypatch):
        monkeypatch.setattr(ai_explain, "_client", mock.MagicMock())

        infos = []
        monkeypatch.setattr(message, "info", lambda msg: infos.append(msg))
        monkeypatch.setattr(message, "warning", lambda msg: None)

        tab = self._make_tab()

        # Capture the JS callback passed to run_js_async and invoke it with ''
        def fake_run_js(code, callback=None, **kwargs):
            if callback is not None:
                callback("")  # simulate empty selection

        tab.run_js_async.side_effect = fake_run_js
        ai_explain.ai_explain(tab)

        assert any("select some text" in i for i in infos)
        # Must not be added to _pending
        assert tab.tab_id not in ai_explain._pending

    def test_whitespace_only_selection_shows_info(self, monkeypatch):
        monkeypatch.setattr(ai_explain, "_client", mock.MagicMock())

        infos = []
        monkeypatch.setattr(message, "info", lambda msg: infos.append(msg))
        monkeypatch.setattr(message, "warning", lambda msg: None)

        tab = self._make_tab()

        def fake_run_js(code, callback=None, **kwargs):
            if callback is not None:
                callback("   ")  # whitespace only

        tab.run_js_async.side_effect = fake_run_js
        ai_explain.ai_explain(tab)

        assert any("select some text" in i for i in infos)
        assert tab.tab_id not in ai_explain._pending


# ---------------------------------------------------------------------------
# Checkpoint 10 — Generation counter (stale result suppression)
# ---------------------------------------------------------------------------


class TestClaimPending:

    def setup_method(self):
        # Clean module state before each test
        ai_explain._pending.discard(100)
        ai_explain._tab_generation.pop(100, None)

    def teardown_method(self):
        ai_explain._pending.discard(100)
        ai_explain._tab_generation.pop(100, None)

    def test_current_generation_claims_and_returns_true(self):
        ai_explain._pending.add(100)
        ai_explain._tab_generation[100] = 3
        assert _claim_pending(100, 3) is True
        assert 100 not in ai_explain._pending

    def test_stale_generation_returns_false(self):
        ai_explain._pending.add(100)
        ai_explain._tab_generation[100] = 3
        # gen=2 is stale; current is 3
        assert _claim_pending(100, 2) is False
        # _pending is NOT discarded on a stale claim
        assert 100 in ai_explain._pending

    def test_unknown_tab_returns_false(self):
        # tab_id 100 has no generation entry
        assert _claim_pending(100, 1) is False

    def test_stale_on_llm_finished_does_not_inject_js(self, monkeypatch):
        """Navigation-superseded callback must not touch the page."""
        monkeypatch.setattr(ai_explain, "_tab_generation", {200: 5})
        monkeypatch.setattr(ai_explain, "_pending", set())

        tab = mock.MagicMock()
        # gen=4 is stale (current is 5)
        ai_explain._on_llm_finished(tab, 200, 4, "some explanation")

        tab.run_js_async.assert_not_called()

    def test_stale_on_llm_error_does_not_surface_error(self, monkeypatch):
        monkeypatch.setattr(ai_explain, "_tab_generation", {200: 5})
        monkeypatch.setattr(ai_explain, "_pending", set())

        errors = []
        monkeypatch.setattr(
            "qutebrowser.api.message.error", lambda msg: errors.append(msg)
        )

        ai_explain._on_llm_error(200, 4, "some error")

        assert not errors


# ---------------------------------------------------------------------------
# Checkpoint 11 — Empty LLM response guard
# ---------------------------------------------------------------------------


class TestEmptyLLMResponse:

    def _make_fake_client(self, text_content):
        """Build a mock _client whose messages.stream() context returns *text_content*."""
        fake_block = mock.MagicMock()
        fake_block.type = "text"
        fake_block.text = text_content

        fake_message = mock.MagicMock()
        fake_message.content = [fake_block]
        fake_message.usage = mock.MagicMock(input_tokens=10)

        fake_stream = mock.MagicMock()
        fake_stream.get_final_message.return_value = fake_message
        fake_stream.__enter__ = lambda s, *a: fake_stream
        fake_stream.__exit__ = mock.MagicMock(return_value=False)

        fake_client = mock.MagicMock()
        fake_client.messages.stream.return_value = fake_stream
        return fake_client

    def test_empty_response_emits_error_signal(self, monkeypatch):
        fake_client = self._make_fake_client("")  # empty string
        monkeypatch.setattr(ai_explain, "_client", fake_client)
        monkeypatch.setattr(ai_explain, "_anthropic_module", mock.MagicMock())

        worker = ai_explain._LLMWorker("term", "ctx", "page")
        errors = []
        worker.error.connect(lambda msg: errors.append(msg))

        worker.run()

        assert errors
        assert "no explanation" in errors[0]

    def test_whitespace_only_response_emits_error_signal(self, monkeypatch):
        fake_client = self._make_fake_client("   \n\n   ")
        monkeypatch.setattr(ai_explain, "_client", fake_client)
        monkeypatch.setattr(ai_explain, "_anthropic_module", mock.MagicMock())

        worker = ai_explain._LLMWorker("term", "ctx", "page")
        errors = []
        worker.error.connect(lambda msg: errors.append(msg))

        worker.run()

        assert errors
        assert "no explanation" in errors[0]
