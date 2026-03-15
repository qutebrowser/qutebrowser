# SPDX-License-Identifier: GPL-3.0-or-later

"""AI-powered text explainer — :ai-explain and :ai-dismiss commands.

Default key bindings (registered automatically):
    ,e  — ai-explain (normal + caret modes)
    ,d  — ai-dismiss (normal + caret modes)
"""

import html
import json
import logging
import os
import re
from typing import Any

from qutebrowser.api import apitypes, cmdutils, hook, message
from qutebrowser.config import config as configmodule
from qutebrowser.keyinput import keyutils
from qutebrowser.qt.core import QObject, QThread, pyqtSignal
from qutebrowser.utils import usertypes

# ---------------------------------------------------------------------------
# Logging, constants, and module-level helpers
# ---------------------------------------------------------------------------

_LOGGER = logging.getLogger("ai_explain")
_TOOLTIP_DISMISS_MS: int = 15_000


def _env_int(name: str, default: int) -> int:
    """Read *name* from the environment as an integer.

    Returns *default* and logs a warning on missing or invalid values,
    preventing import-time crashes from misconfigured environments.
    """
    raw = os.environ.get(name, "")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        _LOGGER.warning(
            "ai-explain: %s=%r is not a valid integer, using default %d",
            name,
            raw,
            default,
        )
        return default


# ---------------------------------------------------------------------------
# Configuration — all values from environment variables only
# ---------------------------------------------------------------------------

_AI_API_KEY: str = os.environ.get("AI_API_KEY", "")
_AI_MODEL: str = os.environ.get("AI_MODEL", "claude-haiku-4-5")
_AI_BASE_URL: str = os.environ.get("AI_BASE_URL", "https://api.anthropic.com")
_AI_MAX_PAGE_CHARS: int = _env_int("AI_MAX_PAGE_CHARS", 12_000)
_AI_TIMEOUT_SECONDS: int = _env_int("AI_TIMEOUT_SECONDS", 30)

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

# anthropic.Anthropic instance once initialized; None means feature is disabled
_client: Any = None

# Tab IDs currently waiting for an LLM response — prevents double-firing
_pending: set[int] = set()

# Keeps (QThread, _LLMWorker) alive while in-flight (GC protection)
_active_threads: dict[int, tuple[QThread, "_LLMWorker"]] = {}

# Tab IDs whose load_started signal is already connected to cleanup
_connected_tabs: set[int] = set()

# Per-tab request generation counter. Incremented on each new request and on
# navigation. Callbacks compare against this to discard superseded results —
# thread.quit() alone cannot interrupt a blocking network call.
_tab_generation: dict[int, int] = {}


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
        # _client is set once at startup (main thread) and never mutated after;
        # reading it here without a lock is safe under CPython's GIL.
        if _client is None:
            self.error.emit("ai-explain: client not initialized")
            return

        # Invariant: _anthropic_module is non-None whenever _client is non-None
        # (_client is only assigned when the import succeeded — see _init).
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
            explanation = "\n".join(
                block.text
                for block in final.content
                if hasattr(block, "text") and block.type == "text"
            ).strip()

            if not explanation:
                self.error.emit("ai-explain: no explanation was produced")
                return

            _LOGGER.debug(
                "ai-explain: received explanation (%d chars, %s input tokens)",
                len(explanation),
                getattr(final.usage, "input_tokens", "?"),
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
    "You are a precise technical explainer embedded in a web browser.\n"
    "Give a concise explanation of the selected text.\n\n"
    "Formatting rules — follow exactly:\n"
    "- Write each sentence on its own line (hard newline after every period).\n"
    "- For concepts with multiple aspects, write one short intro sentence "
    "then 2-4 bullet points (- prefix), one per line.\n"
    "- You may use **bold** for key terms.\n"
    "- No markdown headers.\n"
    "- Do not restate the selected text or start with 'This is...'."
)


def _build_prompt(selected: str, context: str, page_text: str) -> str:
    """Build the user message for the LLM."""
    if len(page_text) > _AI_MAX_PAGE_CHARS:
        page_text = page_text[:_AI_MAX_PAGE_CHARS] + "\n[...truncated]"

    return (
        f"Page content (background context):\n{page_text}\n\n"
        "---\n"
        f"Text surrounding the selection:\n{context}\n\n"
        "---\n"
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


_LIST_OPEN = {
    "ul": '<ul style="margin:4px 0 4px 16px;padding:0;">',
    "ol": '<ol style="margin:4px 0 4px 16px;padding:0;">',
}
_BOLD_RE = re.compile(r"\*\*(.*?)\*\*")


def _render_markdown(text: str) -> str:
    """Convert a small Markdown subset to safe HTML for the tooltip.

    Handles **bold**, unordered lists (- or *), and ordered lists (1.).
    All other non-empty lines become <p> elements.
    Bold is applied per-element (not on the joined string) to prevent the
    regex from accidentally matching across HTML tag boundaries.
    """
    # Safety net: if the model ignores the newline-per-sentence instruction and
    # returns a wall of text, split at sentence boundaries so each sentence
    # gets its own <p>. Splits on ". " followed by an uppercase letter to
    # avoid breaking abbreviations like "e.g. foo" (lowercase after dot).
    text = re.sub(r"\. ([A-Z])", r".\n\1", text)

    escaped = html.escape(text)
    parts: list[str] = []
    current_list = ""  # '' | 'ul' | 'ol'

    def _bold(s: str) -> str:
        return _BOLD_RE.sub(r"<strong>\1</strong>", s)

    def _switch_list(new_type: str) -> None:
        nonlocal current_list
        if current_list != new_type:
            if current_list:
                parts.append(f"</{current_list}>")
            if new_type:
                parts.append(_LIST_OPEN[new_type])
            current_list = new_type

    for raw_line in escaped.split("\n"):
        line = raw_line.strip()
        m_ul = re.match(r"^[-*]\s+(.*)", line)
        m_ol = m_ul is None and re.match(r"^\d+\.\s+(.*)", line)

        if m_ul:
            _switch_list("ul")
            parts.append(f'<li style="margin-bottom:2px;">{_bold(m_ul.group(1))}</li>')
        elif m_ol:
            _switch_list("ol")
            parts.append(f'<li style="margin-bottom:2px;">{_bold(m_ol.group(1))}</li>')
        else:
            _switch_list("")
            if line:
                parts.append(f'<p style="margin:0 0 6px 0;">{_bold(line)}</p>')

    _switch_list("")  # close any open list

    return "".join(parts)


def _build_tooltip_js(explanation: str) -> str:
    """Return a JS string that injects a floating tooltip into the page."""
    formatted = _render_markdown(explanation)

    tooltip_html = (
        '<div id="qute-ai-tooltip" style="'
        "position:fixed;bottom:20px;right:20px;"
        "max-width:440px;min-width:200px;"
        "background:#1e1e2e;color:#cdd6f4;"
        "border:1px solid #313244;"
        "border-left:3px solid #89b4fa;"
        "border-radius:8px;"
        "padding:14px 16px 12px 16px;"
        "font-family:system-ui,-apple-system,sans-serif;"
        "font-size:13px;line-height:1.65;"
        "z-index:2147483647;"
        "box-shadow:0 8px 32px rgba(0,0,0,0.65);"
        'pointer-events:none;">'
        # Header row: coloured label + subtle divider
        '<div style="'
        "display:flex;align-items:center;gap:8px;"
        "margin-bottom:10px;padding-bottom:8px;"
        'border-bottom:1px solid #313244;">'
        '<span style="'
        "font-size:9px;font-weight:700;letter-spacing:1.2px;"
        'color:#89b4fa;text-transform:uppercase;">AI Explain</span>'
        "</div>"
        f"{formatted}"
        "</div>"
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
    setTimeout(function() {{ if (el.parentNode) el.remove(); }}, {_TOOLTIP_DISMISS_MS});
}})()
""".strip()


# ---------------------------------------------------------------------------
# Thread management helpers
# ---------------------------------------------------------------------------


def _run_llm_in_thread(
    tab: apitypes.Tab,
    tab_id: int,
    gen: int,
    selected: str,
    context: str,
    page_text: str,
) -> None:
    """Spin up a QThread, run the LLM call, deliver results to the main thread."""
    thread = QThread()
    worker = _LLMWorker(selected, context, page_text)
    worker.moveToThread(thread)

    thread.started.connect(worker.run)

    worker.finished.connect(lambda text: _on_llm_finished(tab, tab_id, gen, text))
    worker.finished.connect(thread.quit)

    worker.error.connect(lambda err: _on_llm_error(tab_id, gen, err))
    worker.error.connect(thread.quit)

    thread.finished.connect(thread.deleteLater)

    # Guard against the ABA problem: if navigation cancels this thread and a new
    # request immediately stores a replacement entry under the same tab_id, a
    # late-finishing old thread must NOT evict the new entry.  Capture `thread`
    # by identity so the pop is conditional on still owning the slot.
    def _evict_thread_entry(t: QThread = thread) -> None:
        entry = _active_threads.get(tab_id)
        if entry is not None and entry[0] is t:
            del _active_threads[tab_id]

    thread.finished.connect(_evict_thread_entry)

    # Keep references alive — Python GC would collect them otherwise
    _active_threads[tab_id] = (thread, worker)

    thread.start()


def _claim_pending(tab_id: int, gen: int) -> bool:
    """Return True if this generation is still current and remove tab from _pending.

    Returns False when superseded by a navigation event or a newer request —
    callers should silently discard the result in that case.
    """
    if _tab_generation.get(tab_id) != gen:
        return False
    _pending.discard(tab_id)
    return True


def _on_llm_finished(
    tab: apitypes.Tab, tab_id: int, gen: int, explanation: str
) -> None:
    """Main-thread callback: inject tooltip only if the request is still current."""
    if not _claim_pending(tab_id, gen):
        return
    js = _build_tooltip_js(explanation)
    tab.run_js_async(js, world=usertypes.JsWorld.jseval)


def _on_llm_error(tab_id: int, gen: int, error_msg: str) -> None:
    """Main-thread callback: surface error only if the request is still current."""
    if not _claim_pending(tab_id, gen):
        return
    message.error(error_msg)


def _connect_tab_cleanup(tab: apitypes.Tab) -> None:
    """Connect load_started to cleanup exactly once per tab lifetime.

    The handler is intentionally permanent: removing tab_id from _connected_tabs
    inside _cleanup would allow a second handler to be re-connected on the next
    ai-explain call, causing duplicate callbacks on every subsequent navigation.
    """
    tab_id = tab.tab_id
    if tab_id in _connected_tabs:
        return
    _connected_tabs.add(tab_id)

    def _cleanup() -> None:
        _pending.discard(tab_id)
        # Advance the generation so any in-flight callback discards its result.
        # thread.quit() signals the Qt event loop to stop but cannot interrupt
        # a blocking network call; the generation guard is the real safety net.
        _tab_generation[tab_id] = _tab_generation.get(tab_id, 0) + 1
        entry = _active_threads.pop(tab_id, None)
        if entry:
            thread, _ = entry
            thread.quit()
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
    for mode in ("normal", "caret"):
        for key, cmd in [(",e", "ai-explain"), (",d", "ai-dismiss")]:
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

    _is_custom_endpoint = (
        _AI_BASE_URL
        and _AI_BASE_URL != "https://api.anthropic.com"
        and "localhost" not in _AI_BASE_URL
        and "127.0.0.1" not in _AI_BASE_URL
    )
    if _is_custom_endpoint:
        message.warning(
            "ai-explain: page content will be sent to "
            f"external endpoint: {_AI_BASE_URL}"
        )

    try:
        kwargs: dict[str, Any] = {"api_key": _AI_API_KEY}
        if _AI_BASE_URL != "https://api.anthropic.com":
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


@cmdutils.register(name="ai-explain")
@cmdutils.argument("tab", value=cmdutils.Value.cur_tab)
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
        selected_text = (selected or "").strip()
        if not selected_text:
            message.info("ai-explain: select some text first")
            return

        _pending.add(tab_id)
        _tab_generation[tab_id] = _tab_generation.get(tab_id, 0) + 1
        gen = _tab_generation[tab_id]
        message.info("ai-explain: explaining…")

        def _on_context(context: Any) -> None:
            context_text = (context or "").strip()

            def _on_page(page_text: Any) -> None:
                text = (page_text or "").strip()
                _LOGGER.debug(
                    "ai-explain: selected=%d, context=%d, page=%d chars",
                    len(selected_text),
                    len(context_text),
                    len(text),
                )
                _run_llm_in_thread(tab, tab_id, gen, selected_text, context_text, text)

            tab.dump_async(_on_page, plain=True)

        tab.run_js_async(_JS_GET_CONTEXT, _on_context)

    tab.run_js_async(_JS_GET_SELECTION, _on_selection)


@cmdutils.register(name="ai-dismiss")
@cmdutils.argument("tab", value=cmdutils.Value.cur_tab)
def ai_dismiss(tab: apitypes.Tab) -> None:
    """Dismiss the AI explain tooltip from the current page."""
    tab.run_js_async(_JS_DISMISS, world=usertypes.JsWorld.jseval)
