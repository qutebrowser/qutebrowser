# SPDX-License-Identifier: GPL-3.0-or-later

"""AI-powered text explainer — :ai-explain and :ai-dismiss commands.

Default key bindings (registered automatically):
    ,e  — ai-explain (normal + caret modes)
    ,d  — ai-dismiss (normal + caret modes)
"""

import os
import re
import html
import json
import logging
from typing import Optional, Any

from qutebrowser.qt.core import QObject, QThread, pyqtSignal

from qutebrowser.api import cmdutils, apitypes, message, hook
from qutebrowser.utils import usertypes
from qutebrowser.config import config as configmodule
from qutebrowser.keyinput import keyutils

# ---------------------------------------------------------------------------
# Configuration — all values from environment variables only
# ---------------------------------------------------------------------------

_AI_API_KEY: str = os.environ.get('AI_API_KEY', '')
_AI_MODEL: str = os.environ.get('AI_MODEL', 'claude-haiku-4-5')
_AI_BASE_URL: str = os.environ.get('AI_BASE_URL', 'https://api.anthropic.com')
_AI_MAX_PAGE_CHARS: int = int(os.environ.get('AI_MAX_PAGE_CHARS', '12000'))
_AI_TIMEOUT_SECONDS: int = int(os.environ.get('AI_TIMEOUT_SECONDS', '30'))

_LOGGER = logging.getLogger('ai_explain')

# ---------------------------------------------------------------------------
# Optional dependency — graceful degradation if not installed
# ---------------------------------------------------------------------------

try:
    import anthropic as _anthropic_module
except ImportError:
    _anthropic_module = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

# Initialized in @hook.init() — None means feature is disabled
_client: Optional[Any] = None

# Tab IDs currently waiting for an LLM response — prevents double-firing
_pending: set[int] = set()

# Keeps (QThread, _LLMWorker) alive while in-flight (GC protection)
_active_threads: dict[int, tuple] = {}

# Tab IDs whose load_started signal is already connected to cleanup
_connected_tabs: set[int] = set()


# ---------------------------------------------------------------------------
# LLM worker — runs in a background QThread, never blocks the Qt event loop
# ---------------------------------------------------------------------------

class _LLMWorker(QObject):

    """Calls the Anthropic API synchronously inside a dedicated QThread.

    Emits finished(text) on success or error(msg) on failure.
    Both signals are connected in the main thread so Qt delivers them safely.
    """

    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, selected: str, context: str, page_text: str) -> None:
        super().__init__()
        self._selected = selected
        self._context = context
        self._page_text = page_text

    def run(self) -> None:
        """Entry point — called by QThread.started signal."""
        if _client is None:
            self.error.emit("ai-explain: client not initialized")
            return

        prompt = _build_prompt(self._selected, self._context, self._page_text)
        _LOGGER.debug("ai-explain: sending request (model=%s)", _AI_MODEL)

        try:
            with _client.messages.stream(
                model=_AI_MODEL,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                timeout=_AI_TIMEOUT_SECONDS,
            ) as stream:
                final = stream.get_final_message()

            # Extract text blocks only (skip thinking blocks)
            explanation = '\n'.join(
                block.text
                for block in final.content
                if hasattr(block, 'text') and block.type == 'text'
            ).strip()

            _LOGGER.debug(
                "ai-explain: received explanation (%d chars, %s input tokens)",
                len(explanation),
                getattr(final.usage, 'input_tokens', '?'),
            )
            self.finished.emit(explanation)

        except _anthropic_module.AuthenticationError:
            self.error.emit("ai-explain: invalid API key — check AI_API_KEY")
        except _anthropic_module.RateLimitError:
            self.error.emit("ai-explain: rate limited — try again shortly")
        except _anthropic_module.APIError as e:
            self.error.emit(f"ai-explain: API error {e.status_code}: {e.message}")
        except Exception as e:  # pylint: disable=broad-except
            self.error.emit(f"ai-explain: unexpected error: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a precise technical explainer embedded in a web browser. "
    "Explain the selected text in 2-4 concise sentences. "
    "If it is code, explain what it does. "
    "If it is a concept or term, define it in the context of the surrounding text. "
    "Do not use markdown headers or bullet points. "
    "You may use **bold** sparingly for key terms. "
    "Do not restate the selected text or start with 'This is...'."
)


def _build_prompt(selected: str, context: str, page_text: str) -> str:
    """Build the user message for the LLM."""
    if len(page_text) > _AI_MAX_PAGE_CHARS:
        page_text = page_text[:_AI_MAX_PAGE_CHARS] + '\n[...truncated]'

    return (
        f"Page content (background context):\n{page_text}\n\n"
        f"---\n"
        f"Text surrounding the selection:\n{context}\n\n"
        f"---\n"
        f'Explain this specific text in 2-4 sentences: "{selected}"'
    )


# ---------------------------------------------------------------------------
# JavaScript snippets
# ---------------------------------------------------------------------------

_JS_GET_SELECTION = "window.getSelection().toString()"

_JS_GET_CONTEXT = """
(function() {
    var sel = window.getSelection();
    if (!sel || !sel.rangeCount) return '';
    var node = sel.getRangeAt(0).commonAncestorContainer;
    var el = (node.nodeType === 3) ? node.parentElement : node;
    var inline = ['SPAN', 'A', 'STRONG', 'EM', 'CODE', 'B', 'I', 'S'];
    while (el && inline.indexOf(el.tagName) !== -1) {
        el = el.parentElement;
    }
    return el ? (el.innerText || el.textContent || '').slice(0, 800) : '';
})()
""".strip()

_JS_DISMISS = """
(function() {
    var el = document.getElementById('qute-ai-tooltip');
    if (el) el.remove();
})()
""".strip()


def _build_tooltip_js(explanation: str) -> str:
    """Return a JS string that injects a floating tooltip into the page."""
    # Convert **bold** → <strong>bold</strong>, escape everything else
    escaped = html.escape(explanation)
    formatted = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', escaped)
    formatted = formatted.replace('\n', '<br>')

    tooltip_html = (
        '<div id="qute-ai-tooltip" style="'
        'position:fixed;bottom:20px;right:20px;'
        'max-width:420px;min-width:180px;'
        'background:#1e1e2e;color:#cdd6f4;'
        'border:1px solid #45475a;border-radius:8px;'
        'padding:14px 16px;'
        'font-family:system-ui,-apple-system,sans-serif;'
        'font-size:13px;line-height:1.6;'
        'z-index:2147483647;'
        'box-shadow:0 4px 24px rgba(0,0,0,0.5);'
        'pointer-events:none;">'
        '<div style="font-size:10px;color:#6c7086;'
        'margin-bottom:8px;letter-spacing:0.5px;">AI EXPLAIN</div>'
        f'{formatted}'
        '</div>'
    )

    # json.dumps ensures correct JS string escaping
    escaped_html = json.dumps(tooltip_html)

    return f"""
(function() {{
    var existing = document.getElementById('qute-ai-tooltip');
    if (existing) existing.remove();
    var wrapper = document.createElement('div');
    wrapper.innerHTML = {escaped_html};
    var el = wrapper.firstElementChild;
    document.body.appendChild(el);
    setTimeout(function() {{ if (el.parentNode) el.remove(); }}, 15000);
}})()
""".strip()


# ---------------------------------------------------------------------------
# Thread management helpers
# ---------------------------------------------------------------------------

def _run_llm_in_thread(
    tab: apitypes.Tab,
    tab_id: int,
    selected: str,
    context: str,
    page_text: str,
) -> None:
    """Spin up a QThread, run the LLM call, deliver results to the main thread."""
    thread = QThread()
    worker = _LLMWorker(selected, context, page_text)
    worker.moveToThread(thread)

    thread.started.connect(worker.run)

    worker.finished.connect(
        lambda text: _on_llm_finished(tab, tab_id, text)
    )
    worker.finished.connect(thread.quit)

    worker.error.connect(lambda err: _on_llm_error(tab_id, err))
    worker.error.connect(thread.quit)

    # Cleanup: remove from active dict once thread stops
    thread.finished.connect(thread.deleteLater)
    thread.finished.connect(lambda: _active_threads.pop(tab_id, None))

    # Keep references alive — Python GC would collect them otherwise
    _active_threads[tab_id] = (thread, worker)

    thread.start()


def _on_llm_finished(tab: apitypes.Tab, tab_id: int, explanation: str) -> None:
    """Main-thread callback: inject tooltip into page."""
    _pending.discard(tab_id)
    js = _build_tooltip_js(explanation)
    tab.run_js_async(js, world=usertypes.JsWorld.jseval)


def _on_llm_error(tab_id: int, error_msg: str) -> None:
    """Main-thread callback: surface error in status bar."""
    _pending.discard(tab_id)
    message.error(error_msg)


def _connect_tab_cleanup(tab: apitypes.Tab) -> None:
    """Connect load_started to cleanup once per tab."""
    tab_id = tab.tab_id
    if tab_id in _connected_tabs:
        return
    _connected_tabs.add(tab_id)

    def _cleanup() -> None:
        _pending.discard(tab_id)
        _connected_tabs.discard(tab_id)
        # Cancel in-flight thread if any
        entry = _active_threads.pop(tab_id, None)
        if entry:
            thread, _ = entry
            thread.quit()
        # Dismiss tooltip
        tab.run_js_async(_JS_DISMISS, world=usertypes.JsWorld.jseval)

    tab.load_started.connect(_cleanup)


# ---------------------------------------------------------------------------
# Extension init hook
# ---------------------------------------------------------------------------

@hook.init()
def _init(_context: apitypes.InitContext) -> None:
    """Initialize the ai-explain extension on startup."""
    global _client  # noqa: PLW0603

    # Register default key bindings so users don't need to touch config.py
    for mode in ('normal', 'caret'):
        for key, cmd in [(',e', 'ai-explain'), (',d', 'ai-dismiss')]:
            seq = keyutils.KeySequence.parse(key)
            configmodule.key_instance.bind(seq, cmd, mode=mode)

    if _anthropic_module is None:
        message.warning(
            "ai-explain: 'anthropic' package not installed. "
            "Run: pip install anthropic"
        )
        return

    if not _AI_API_KEY:
        message.warning("ai-explain: AI_API_KEY not set — feature disabled")
        return

    # Warn if sending data to a non-default external endpoint
    _is_custom_endpoint = (
        _AI_BASE_URL
        and _AI_BASE_URL != 'https://api.anthropic.com'
        and 'localhost' not in _AI_BASE_URL
        and '127.0.0.1' not in _AI_BASE_URL
    )
    if _is_custom_endpoint:
        message.warning(
            f"ai-explain: page content will be sent to external endpoint: {_AI_BASE_URL}"
        )

    try:
        kwargs: dict = {"api_key": _AI_API_KEY}
        if _AI_BASE_URL != 'https://api.anthropic.com':
            kwargs["base_url"] = _AI_BASE_URL

        _client = _anthropic_module.Anthropic(**kwargs)
        _LOGGER.debug(
            "ai-explain: initialized (model=%s, endpoint=%s)",
            _AI_MODEL,
            _AI_BASE_URL,
        )
    except Exception as e:  # pylint: disable=broad-except
        message.error(f"ai-explain: failed to initialize: {e}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@cmdutils.register(name='ai-explain')
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
def ai_explain(tab: apitypes.Tab) -> None:
    """Explain the currently selected text using AI.

    Select any text on the page, then run this command to get a 2-4 sentence
    explanation from Claude, displayed as a floating tooltip on the page.

    The tooltip auto-dismisses after 15 seconds. Use :ai-dismiss to remove
    it immediately.

    Requires the AI_API_KEY environment variable to be set.
    """
    if _client is None:
        message.warning(
            "ai-explain: not available — set AI_API_KEY and restart qutebrowser"
        )
        return

    if tab.is_private:
        message.warning("ai-explain: disabled in private tabs")
        return

    tab_id = tab.tab_id

    if tab_id in _pending:
        message.info("ai-explain: already explaining, please wait…")
        return

    # Connect navigation cleanup once per tab
    _connect_tab_cleanup(tab)

    def _on_selection(selected: Any) -> None:
        selected_text = (selected or '').strip()
        if not selected_text:
            message.info("ai-explain: select some text first")
            return

        _pending.add(tab_id)
        message.info("ai-explain: explaining…")

        def _on_context(context: Any) -> None:
            context_text = (context or '').strip()

            def _on_page(page_text: Any) -> None:
                text = (page_text or '').strip()
                _LOGGER.debug(
                    "ai-explain: selected=%d, context=%d, page=%d chars",
                    len(selected_text), len(context_text), len(text),
                )
                _run_llm_in_thread(tab, tab_id, selected_text, context_text, text)

            tab.dump_async(_on_page, plain=True)

        tab.run_js_async(_JS_GET_CONTEXT, _on_context)

    tab.run_js_async(_JS_GET_SELECTION, _on_selection)


@cmdutils.register(name='ai-dismiss')
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
def ai_dismiss(tab: apitypes.Tab) -> None:
    """Dismiss the AI explain tooltip from the current page."""
    tab.run_js_async(_JS_DISMISS, world=usertypes.JsWorld.jseval)
