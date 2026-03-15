# ai-explain — qutebrowser extension

**Feature:** `:ai-explain` — select any text on a page, press a key, and receive an
LLM-generated explanation rendered as a floating tooltip directly in the page.

---

## Flow

1. **Select text** — highlight any word or phrase with the mouse or in caret mode
2. **Trigger** — press `,e` or type `:ai-explain`
3. **Context extraction** — the extension collects three layers automatically: the selected text, the surrounding paragraph, and the full page as background
4. **API call** — the payload is sent to an Anthropic-compatible endpoint (Claude by default) via streaming
5. **Tooltip rendered** — the explanation appears as a floating overlay in the bottom-right corner
6. **Dismiss** — auto-dismisses after 15 seconds; press `,d` or navigate away to remove it immediately

Key bindings are registered automatically on startup — no `config.py` edits required.

---

## Examples

### Structured bullet-point explanation

Selecting *"non-preemptive multitasking"* on an English Wikipedia article:

![AI Explain tooltip on English text](docs/screenshots/tooltip_english.png)

### Cross-language explanation

Selecting *"Eigenschaften und Gesetzmäßigkeiten"* (properties and governing laws)
from the German Wikipedia article on *Quantenmechanik*. The model reads the full
page context, infers the language, and returns the explanation in English —
breaking the compound phrase into two bullet points, one per term:

![AI Explain tooltip on German text](docs/screenshots/tooltip_german.png)

---

## Files

```
qutebrowser/components/ai_explain.py   # extension — all runtime code
tests/unit/components/test_ai_explain.py
tests/evaluation/
    eval_ai_explain.py                 # LLM-as-a-judge evaluation harness
    fixtures.py                        # 6 realistic selection scenarios
    eval_results.json                  # latest results (no key needed to read)
    requirements.txt
```

---

## Major design decisions and tradeoffs

### Context extraction — three-layer prompt

The prompt is built from three inputs (see `_build_prompt` in `ai_explain.py`):

| Layer | Source | Cap | Role in prompt |
|---|---|---|---|
| Selected text | `window.getSelection().toString()` | — | *"Explain this specific text"* |
| Semantic block context | DOM traversal | 800 chars | *"Text surrounding the selection"* |
| Full page text | `tab.dump_async(plain=True)` | 12 000 chars | *"Page content (background context)"* |

`_JS_GET_CONTEXT` walks the DOM from the selection anchor past inline elements
(`<span>`, `<a>`, `<code>`, …) to the nearest block ancestor (`<p>`, `<div>`,
`<li>`, …) and returns its `innerText`. This gives the model the complete sentence
the user was reading rather than an arbitrary byte slice.
Tradeoff: very large block elements can include more text than needed; the 800-char
cap is a blunt fallback.

This layering lets the model interpret the same term differently depending on page
context — "handler" means something different on a Django docs page than on a
legal document.

### QThread worker, not asyncio

qutebrowser uses Qt's event loop. A blocking API call on the main thread would
freeze the entire browser for the round-trip. The call runs in a `QThread` worker
and delivers its result back via `pyqtSignal`.
Tradeoff: `thread.quit()` cannot interrupt a blocking socket call. A per-tab
generation counter (`_tab_generation`) discards stale results if the user navigates
before the response arrives.

### Generation counter over thread cancellation

Each new request increments a per-tab integer. Every callback checks its captured
generation before touching the DOM or surfacing an error. This blocks stale results
and closes the ABA race where a late-finishing old thread could evict the new
thread's GC-protection entry from `_active_threads`.

### Single-file implementation

qutebrowser's extension API is designed for self-contained single-file modules,
consistent with every other component in `qutebrowser/components/`. Internal layers
are clean (`_LLMWorker` is UI-agnostic, `_build_prompt` is a pure function) even
though they share a file.

### Haiku as the default model

`claude-haiku-4-5` balances speed, cost, and quality for a feature that fires on
every user selection. Overridable via `AI_MODEL` without code changes.

### Configuration via `.env`, never hardcoded

All config is read from the environment at import time. `.env` is gitignored.
`AI_BASE_URL` supports proxy and local-endpoint routing without code edits.

### Graceful degradation

If `anthropic` is missing or `AI_API_KEY` is unset, the extension warns and
disables itself. Both commands still register so qutebrowser never errors on `,e`.

### Module-level state keyed by `tab_id`

All coordination state (`_pending`, `_active_threads`, `_connected_tabs`,
`_tab_generation`) lives in module-level dicts indexed by `tab_id`. This keeps
the data model flat and the extension self-contained.
Tradeoff: lifecycle correctness relies on strict helper boundaries rather than
object encapsulation.

---

## Evaluation methodology

### Approach: RAGAS-inspired LLM-as-a-judge

We use a two-step **LLM-as-a-judge** pipeline inspired by
[RAGAS](https://docs.ragas.io), instead of brittle fixed-answer assertions.
The harness follows RAGAS-style grounding metrics but uses a lightweight custom
judge prompt, so it stays dependency-light and works with Anthropic-compatible endpoints.

**Step 1 — Generate.** The harness runs the real `_build_prompt` + `_SYSTEM_PROMPT`
pipeline (identical to production) against each fixture and collects the model's
explanation. This means the eval measures what the actual feature produces, not a
simplified proxy.

**Step 2 — Judge.** Each explanation is sent to a second LLM call (the judge) along
with the original selected text, paragraph context, and page text. The judge scores
the explanation on four metrics and returns structured JSON with a score *and* a
one-sentence reason for each metric. The reason is critical — it lets a developer
understand *why* a score was assigned and whether to trust it.

### Metrics

| Metric | Type | Definition |
|---|---|---|
| **Faithfulness** | float 0.0–1.0 | What fraction of the explanation's factual claims are directly supported by the page context or page text? 1.0 = fully grounded, 0.0 = fabricated or contradicted. Adapted from RAGAS faithfulness. |
| **Relevance** | 0 or 1 | Does the explanation address the *selected text specifically*, rather than giving a generic description of the surrounding topic? |
| **Conciseness** | 0 or 1 | Is the explanation free of padding and repetition? Accepts two formats: 2–4 plain sentences, or one short intro sentence followed by 2–4 bullet points. |
| **Clarity** | 0 or 1 | Is the explanation clear and accessible to a general technical audience, using plain language? |

### Fixtures

Six fixtures cover different vocabulary and context types, all drawn from
Python documentation topics:

| Fixture | Selected text | Tests |
|---|---|---|
| `coroutine` | "coroutine" | single technical term, rich context |
| `garbage_collection` | "garbage-collected" | adjective form, inferred concept |
| `global_interpreter_lock` | "Global Interpreter Lock" | named concept, multi-sentence context |
| `list_comprehension` | "list comprehension" | syntax feature with code example in page |
| `duck_typing` | "duck typing" | idiomatic term with metaphor in context |
| `significant_indentation` | "significant indentation" | design decision term |

All fixtures supply realistic `selected_text`, `context` (paragraph-level), and
`page_text` (full-page-level) — the same three inputs the live extension collects
from the browser.

### Results (last run: 2026-03-15, `claude-haiku-4-5`)

| Metric | Score | Interpretation |
|---|---|---|
| **Faithfulness** | **0.958** | All claims grounded in source; minor rounding on edge cases (e.g. "immediately" for reference counting timing) |
| **Relevance** | **1.000** | All 6 explanations stayed on-topic for the selected term |
| **Conciseness** | **1.000** | All responses were appropriately brief; bullet-point and plain-sentence formats both scored correctly |
| **Clarity** | **1.000** | All explanations rated accessible to a general technical audience |

Full per-fixture explanations and per-metric reasoning are in
`tests/evaluation/eval_results.json` — readable without an API key.

### Running the eval yourself

```bash
# With an Anthropic key:
pip install -r tests/evaluation/requirements.txt
AI_API_KEY=<your-key> python tests/evaluation/eval_ai_explain.py

# Override the model under test or the judge model:
AI_MODEL=claude-haiku-4-5 AI_JUDGE_MODEL=claude-haiku-4-5 \
    python tests/evaluation/eval_ai_explain.py
```

---

## Running the feature

### With an Anthropic key

```bash
pip install anthropic
```

Create a `.env` file in the repository root (already gitignored):

```bash
# .env — never commit this file
AI_API_KEY=sk-ant-...              # required
AI_MODEL=claude-haiku-4-5         # optional — any Anthropic model ID
AI_BASE_URL=https://api.anthropic.com  # optional — override for local proxy
AI_MAX_PAGE_CHARS=12000            # optional — cap on page text sent to the LLM
AI_TIMEOUT_SECONDS=30              # optional — per-request timeout
```

Source it and launch:

```bash
set -a && source .env && set +a
python qutebrowser.py
```

1. Navigate to any page.
2. Select text (mouse drag or caret mode + Shift+arrow).
3. Press `,e` — status bar shows *ai-explain: explaining…*
4. Tooltip appears. Press `,d` or navigate to dismiss early.

| Variable | Default | Effect |
|---|---|---|
| `AI_MODEL` | `claude-haiku-4-5` | Any Anthropic model ID |
| `AI_BASE_URL` | `https://api.anthropic.com` | Redirect to a local proxy |
| `AI_MAX_PAGE_CHARS` | `12000` | Cap on page text sent to the LLM |
| `AI_TIMEOUT_SECONDS` | `30` | Per-request timeout |

### Without an Anthropic key — disabled-mode verification

Leave `AI_API_KEY` unset and start qutebrowser. Verify:

- A startup warning appears: *"AI_API_KEY not set — feature disabled"*
- Pressing `,e` shows an actionable message rather than crashing
- `:ai-dismiss` is safe and idempotent with no tooltip present

This exercises the graceful degradation path without any API cost.

### Without an Anthropic key — local model via Ollama + LiteLLM

`AI_BASE_URL` redirects the Anthropic SDK to any Anthropic-compatible endpoint.

```bash
# 1. Start the Ollama server (skip if already running as a system service)
ollama serve &
sleep 2   # give the server a moment to bind

# 2. Pull the model (requires Ollama server to be running)
ollama pull llama3.2

# 3. Run LiteLLM as an Anthropic-compatible proxy
#    ollama_chat/ routes to /api/chat (messages format) — required for the Anthropic SDK
pip install "litellm[proxy]"
cat > litellm.config.yaml << 'YAML'
model_list:
  - model_name: ollama-llama3.2
    litellm_params:
      model: ollama_chat/llama3.2
      api_base: http://127.0.0.1:11434
YAML
litellm --config litellm.config.yaml --port 4000 &
sleep 2   # give the proxy a moment to start

# 4. Preflight check — verify the proxy forwards to Ollama correctly
curl -sS http://127.0.0.1:4000/v1/messages \
  -H "content-type: application/json" \
  -H "x-api-key: dummy" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "ollama-llama3.2",
    "max_tokens": 64,
    "messages": [{"role":"user","content":"Say hello in one short sentence."}]
  }'
# Expected: JSON with a content[].text field — if you see that, the chain works

# 5. Add to .env and launch
# AI_API_KEY=dummy          # any non-empty value — LiteLLM does not enforce key auth by default
# AI_BASE_URL=http://localhost:4000
# AI_MODEL=ollama-llama3.2  # must match model_name in litellm.config.yaml
set -a && source .env && set +a
python qutebrowser.py
```

Explanation quality will differ from Claude, but the full flow
(selection → context extraction → API call → tooltip → auto-dismiss) can be
validated end-to-end.

---

## Definition of done (DoD) and verification artifacts

### Criteria

**Functional correctness** — works on plain text, code, and cross-language selections; all error paths (empty selection, private tab, missing key, network failure, rate limit) are handled gracefully; tooltip is non-blocking (`pointer-events: none`) and both auto-dismiss and manual dismiss work reliably. Known open item: tooltip uses a fixed dark theme and may conflict with light-mode pages.

**Performance** — first explanation token appears within 3 s via streaming; page text extraction completes in < 500 ms; Qt event loop is never blocked (all I/O in `QThread`); no unbounded data structures (`_pending` is always cleared on navigation and tab close).

**Security & privacy** — API key never appears in source or logs; private tabs are hard-blocked; an external-endpoint warning fires when `AI_BASE_URL` is non-localhost; page text is hard-capped before sending; automated test (`TestSecretsGuardrail`) confirms no `sk-ant-` pattern in source.

**Code quality** — single responsibility per layer (`_LLMWorker` / `_build_prompt` / `_build_tooltip_js`); open/closed (new explanation style = new prompt only); no duplicated extraction logic; all configuration via env vars; full type annotations throughout.

**Observability** — all major steps logged at DEBUG level; every error surfaces to the user via `message.error()` or `message.warning()`; token usage logged after each call.

**Tests** — 38 unit tests covering prompt builder, config loading, all error handlers, guardrails, generation-counter logic, empty selection, and empty LLM response. Two gaps remain: end-to-end integration test with a fully mocked `anthropic.Anthropic` client, and automation of the manual test matrix.

**Lint/style** — black, isort, and flake8 all clean.

**Documentation** — README claims match the current implementation and point to reproducible artifacts.

### Verification results (2026-03-15 UTC)

| Check | Command | Result |
|---|---|---|
| Unit tests | `pytest -q tests/unit/components/test_ai_explain.py` | **38 passed** |
| Formatting | `black --check qutebrowser/components/ai_explain.py tests/unit/components/test_ai_explain.py` | **clean** |
| Import order | `isort --check --profile black qutebrowser/components/ai_explain.py tests/unit/components/test_ai_explain.py` | **clean** |
| Lint | `flake8 qutebrowser/components/ai_explain.py --max-complexity=10` | **clean** |
| LLM eval | `python tests/evaluation/eval_ai_explain.py` | see table below |

| Metric | Score |
|---|---|
| Faithfulness | **0.958** |
| Relevance | **1.000** |
| Conciseness | **1.000** |
| Clarity | **1.000** |

Full per-fixture results committed to `tests/evaluation/eval_results.json`.

---

## What I would do next with more time

**1. Formalise the LLM provider boundary.**
`_LLMWorker` communicates only through `finished(str)` / `error(str)` signals.
Adding a `Protocol` with those two signals would make it trivial to swap in an
OpenAI or local-model backend without touching orchestration or UI code.

**2. Progressive tooltip (streaming).**
`_client.messages.stream()` is already used under the hood. Piping
`stream.text_stream` into the page via repeated `run_js_async` calls would give
the user visible progress during the API round-trip, reducing perceived latency.

**3. Harden the tooltip presenter.**
`_render_markdown` handles bold, lists, and paragraph breaks. If a second display
mode were needed (status bar, native notification), extracting it and
`_build_tooltip_js` to a `_presenter.py` would make both paths testable in isolation.
Remaining gap: inline `` `code` `` → `<code>` rendering is not yet implemented.

**4. Qt threading lifecycle tests.**
What remains untested at the Qt level is ABA-safe thread entry eviction and the
behaviour when a `QThread` finishes after a new request has already started.
These require `QSignalSpy` and a live Qt event loop, which the current pytest
setup does not provide.

**5. Tooltip accessibility and theme integration.**
The tooltip uses hardcoded Catppuccin Mocha colors (`#1e1e2e`, `#cdd6f4`).
On a light-mode setup this produces a jarring dark overlay. Reading
`prefers-color-scheme` in the injected JS, or exposing `AI_TOOLTIP_BG` /
`AI_TOOLTIP_FG` env vars, would fix this without any Python changes. Adding an
`Escape` key handler inside the tooltip JS would also make dismissal keyboard-accessible.

**6. Configurable prompt suffix.**
An `AI_EXPLAIN_SUFFIX` env var appended to the user message would let users
change the explanation register ("explain in Spanish", "focus on security
implications") without touching source code.

**7. Prompt caching.**
Adding `cache_control: {type: "ephemeral"}` to the page text block would cache it
across repeated `:ai-explain` calls on the same page, cutting token cost ~90% for
the context portion on the second and subsequent requests.

**8. Shared `LLMClient` abstraction.**
If additional AI commands are added (`:ai-summarize`, `:ai-ask`), extracting the
HTTP/streaming/error-handling logic from `_LLMWorker` into a shared
`qutebrowser/misc/llm_client.py` would eliminate duplication across components.

**9. Explanation history.**
Store the last N explanations in a session dict, accessible at `qute://ai-history`.
Low implementation cost; high value for users who want to review earlier explanations.
