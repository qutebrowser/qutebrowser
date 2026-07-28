# AI Feature: Natural-Language Command Translator

## What it does

qutebrowser is entirely keyboard- and command-driven — every action goes through a `:` command (`:tab-close`, `:tab-mute`, `:open`, etc.). That's powerful once you know the vocabulary, but it means the barrier to entry is memorizing (or looking up) exact command names and flags. This feature adds a natural-language layer on top of that existing command set.

**Trigger:** `:ai-do close all tabs except this one and mute the rest` (bound to a key, e.g. `,a`, for convenience). Note: `maxsplit=0` means quotes around the query are optional.

**Flow:**
1. **Retrieval** — the query is matched against a corpus built from qutebrowser's own command registry. The most relevant candidates (default: top-8) are surfaced.
2. **Translation** — a language model resolves the query into one or more concrete commands referencing *only those candidate* commands.
3. **Validation** — hallucinated commands/args are stripped, known flags are kept, mutual-exclusion constraints are enforced.
4. **Confirmation** — the resolved command string is shown to the user (e.g. `tab-close --except-current ;; tab-mute --all`) before anything runs.
5. **Execution** — on confirmation, it runs via qutebrowser's normal command-runner — the same path a hand-typed command would take.

Note on scope: qutebrowser's built-in `:` completion already does excellent fuzzy matching on command *names* — this feature isn't trying to replace that. It's aimed at the cases completion can't help with: queries that don't share vocabulary with the command name at all, and requests that require chaining multiple commands together (which the user would otherwise need to know two commands *and* the `;;` syntax for).

**Accessibility framing:** qutebrowser's keyboard-only design already makes it a strong option for users who can't rely on a mouse. A natural-language interface adds another axis to that: it lowers the requirement from "recall the exact command syntax" to "describe what you want," which matters for users who know their intent but not the vim-style vocabulary — a smaller but real accessibility gain layered on top of what the browser already does well.

---

## Architecture

```
  User query ("close tab with wikipedia")
         │
         ▼
  ┌──────────────┐
  │  RETRIEVAL   │── semantic + lexical hybrid search → top‑k candidates
  │  registry    │    - sentence-transformers (semantic, ~80MB model)
  │  retrieval   │    - TF-IDF (lexical, blended at α=0.6)
  │              │    - Fallback: pure-stdlib if sklearn absent
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │   PROVIDER   │── LLM translates query → JSON commands
  │  ┌─────────┐ │      Strategy 1 (preferred): function‑calling tool
  │  │ tool    │ │        LLM calls get_command_details → gets structured specs
  │  ├─────────┤ │      Strategy 2 (fallback): prompt‑based
  │  │ prompt  │ │        All candidate details inlined in system prompt
  │  ├─────────┤ │      Strategy 3 (last resort): mock fallback
  │  │ mock    │ │        Deterministic: returns top candidate, no args
  │  └─────────┘ │
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │  VALIDATION  │── strip hallucinated commands/args, enforce constraints
  │  translator  │    - Commands not in candidate set → dropped
  │              │    - Unknown flags (e.g. --help) → stripped
  │              │    - Flag–value hallucination pairs → both stripped
  │              │    - Mutual exclusion (--all + URL) → --all removed
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │  CONFIRM +   │── "Run: tab-close --url wikipedia ?" → y/n
  │  EXECUTE     │    - Auto-confirm with AI_AUTO_CONFIRM=true (testing only)
  └──────────────┘
```

The three provider strategies ensure the feature never hard-fails:
- **Tool-based** requires function-calling support in the LLM backend — highest accuracy, lowest hallucination.
- **Prompt-based** works with any OpenAI-compatible endpoint — all candidate details inlined.
- **Mock** works with zero dependencies — deterministic fallback for review/demo.

---

## Retrieval

The query must be matched against ~200 registered commands to find the most relevant candidates. This is done by computing a similarity score between the query text and each command's searchable text (command name + description + argument names).

### Hybrid scoring

When both the sentence-transformers embedder and TF-IDF are available, the final score is a blend:

```
score = 0.6 · embedding_cosine + 0.4 · tfidf_cosine
```

This ensures exact lexical matches (e.g. "open" in query => the `open` command) are never drowned out by the semantic embedder, while still benefiting from the embedder's ability to match paraphrases.

### Fallback chain

1. **sentence-transformers** (`all-MiniLM-L6-v2`, ~80MB CPU-only) — semantic matching. Requires `pip install sentence-transformers` and a pre-cached model (via `bash scripts/setup-ai.sh`).
2. **scikit-learn TF-IDF** (word bigrams, cosine similarity) — lexical matching, installed with qutebrowser's test deps.
3. **Pure-stdlib TF-IDF** — zero extra dependencies, always works.

Each fallback is automatic and transparent — the log will show which path was taken.

### Important: eager PyTorch import

`sentence_transformers` is imported at module load time (before `QApplication` is created) to avoid a segfault caused by PyTorch/Qt signal-handler conflicts. This adds ~500ms to startup but is invisible to the user (happens before the GUI renders).

---

## Provider (LLM translation)

The provider translates the user's natural-language query into structured JSON commands using an LLM. Three strategies are tried in order.

### Strategy 1: Tool-based (function calling)

When the LLM backend supports OpenAI-compatible function calling, we define a `get_command_details` tool. The flow:

1. **First call** — system prompt (instructions + candidate command names only, no details) + user query, with the tool definition.
2. **Tool call** — the LLM calls `get_command_details(["command-name", ...])` to fetch exact specs.
3. **Tool response** — we return structured JSON (description, positional args with choices, flags).
4. **Second call** — the LLM now has the exact specs and produces the final command JSON.

This is the preferred path: smaller initial prompt, structured data delivery, lower hallucination rate.

### Strategy 2: Prompt-based (fallback)

All candidate details are inlined in the system prompt. This works with any OpenAI-compatible endpoint, including those that don't support function calling.

### Strategy 3: Mock (zero-dependency fallback)

If no LLM is reachable, a deterministic rule returns the top-ranked candidate command with no arguments. An in-app message clearly indicates mock mode.

### Validation and safety

Every resolved command goes through validation:
- Commands not in the candidate set are dropped.
- Unknown flags (e.g. `--help`, hallucinated flags) are stripped.
- If a hallucinated flag has a value token, both are stripped.
- Mutual-exclusion constraints are enforced (e.g. `bookmark-del` can't take both `--all` and a URL).
- The user must confirm before execution (unless `AI_AUTO_CONFIRM=true`).

---

## How to Run

The feature needs **two independent things** to be useful:

1. **Embedding model** (for retrieval) — installed by `scripts/setup-ai.sh`.
2. **LLM endpoint** (for translation) — Ollama, a cloud provider, or mock mode.

You can use mock mode with just step 1, or with neither (pure stdlib + mock).

### Prerequisites

- A working qutebrowser dev environment (see the project's own `README.md`/`CONTRIBUTING.md` for base setup — Python 3.x + Qt/QtWebEngine).
- No API key or local model is strictly required — the feature runs in a degraded-but-functional mock mode with zero extra setup.

### Step 1: Install embedding model and Python dependencies

```bash
bash scripts/setup-ai.sh
```

This installs `sentence-transformers` and pre-downloads `all-MiniLM-L6-v2` into the HuggingFace cache. After this, no network requests happen at runtime.

**`setup-ai.sh does NOT install or manage Ollama`** — that is a separate step.

### Step 2a: Set up a local LLM via Ollama (recommended)

```bash
# Install Ollama (see https://ollama.com for other platforms)
curl -fsSL https://ollama.com/install.sh | sh
ollama serve  # or: systemctl --user start ollama

# Pull the default model
ollama pull gemma4:e4b
```

Now launch qutebrowser — the defaults (`AI_BASE_URL=http://localhost:11434/v1`, `AI_MODEL=gemma4:e4b`) point at this instance.

### Step 2b: Or, run against a cloud provider

```bash
export AI_BASE_URL="https://api.your-provider.com/v1"
export AI_MODEL="your-model-name"
export AI_API_KEY="your-key-here"
```

Any OpenAI-compatible chat completions endpoint works.

### Step 2c: Or, skip the LLM entirely (mock mode)

Launch qutebrowser with no LLM configured. The feature will:
- Use the lexical retrieval fallback (TF-IDF instead of neural).
- Attempt the local Ollama endpoint, fail to connect, and fall back to the deterministic mock provider — clearly indicated via an in-app message.
- Still run the full confirm-before-execute flow with a runnable (if less accurate) resolved command.

The whole pipeline is reviewable with nothing installed beyond qutebrowser itself.

### Using the feature

1. Launch qutebrowser from this branch.
2. Run `:ai-do your request in plain English` — for example:
   - `:ai-do close every tab except the current one`
   - `:ai-do mute all tabs`
   - `:ai-do close all tabs except this one and mute the rest` (multi-step, chained)
   - `:ai-do open wikipedia` (URL completion, no quotes needed)
3. Confirm the shown command string when prompted (y/n).
4. (Optional) bind it to a key for convenience by adding to your `config.py`:
   ```python
   config.bind(',a', 'set-cmd-text :ai-do ')
   ```

### Environment variable reference

| Variable | Default | Purpose |
|---|---|---|
| `AI_BASE_URL` | `http://localhost:11434/v1` | OpenAI-compatible endpoint for the generation model |
| `AI_MODEL` | `gemma4:e4b` | Model name sent in the request |
| `AI_API_KEY` | (unset) | Only needed for providers that require auth (local Ollama doesn't) |
| `AI_TOP_K` | `8` | Number of candidate commands retrieval surfaces to the model |
| `AI_AUTO_CONFIRM` | `false` | If `true`, skips the y/n prompt — off by default for safety, exists mainly for automated testing |

### Hardware requirements

| Component | Disk | RAM | Notes |
|---|---|---|---|
| PyTorch + CUDA libs | ~3.5 GB | — | Installed as a dependency of `sentence-transformers` |
| all-MiniLM-L6-v2 (model cache) | ~90 MB | ~500 MB at inference | Downloaded on first use, cached under `~/.cache/huggingface/` |
| Ollama runtime | ~600 MB | ~200 MB (idle) | Go binary + serving infra |
| `gemma4:e4b` (LLM) | ~2.5 GB | ~4 GB at inference | Quantized 4-bit; pulled into `~/.ollama/` |
| **Total with sentence-transformers** | **~7 GB** | **~5 GB** | Peak at inference time when both models are loaded |

All inference runs on CPU by default — no GPU required. Without `sentence-transformers`, the total drops to ~3 GB disk and ~4 GB RAM (Ollama + LLM only).

### Dependencies added

- `sentence-transformers` (optional — feature degrades gracefully without it)
- See `misc/requirements/requirements-ai.txt` for pinned versions.

No secrets are committed anywhere in this branch. See `.env.example` for the local-convenience variable template (not required to run — env vars can also just be exported in-shell).

---

## Testing

Tests live in `tests/unit/misc/ai/`. Run them with:

```bash
# All AI unit tests (no external dependencies needed)
python -m pytest tests/unit/misc/ai/test_registry.py tests/unit/misc/ai/test_provider.py tests/unit/misc/ai/test_translator.py tests/unit/misc/ai/test_retrieval.py -v

# with sentence-transformers tests (requires model cache)
python -m pytest tests/unit/misc/ai/test_retrieval.py -v

# End-to-end tests (requires a running Ollama instance)
python -m pytest tests/unit/misc/ai/test_e2e.py -v
```

The e2e tests auto-skip if Ollama isn't running. Sentence-transformer tests auto-skip if the model isn't cached. The unit tests use mocks and need no external services.

No CI changes were needed — the existing `tox -e py*` test environments automatically pick up the AI tests (they're under `tests/`), and the e2e/sentence-transformer tests are properly gated with skip conditions.

---

## Major design decisions / tradeoffs

See also [`RFC.md`](RFC.md) for the full design history, challenges, and rationale behind each decision.

- **Retrieval corpus = the app's own command registry, not scraped docs.** Ground truth, always in sync. Tradeoff: it only knows about commands, not about `:set` config options.
- **Local model by default, cloud as opt-in.** No API key required to try the feature. Tradeoff: a 2B local model is weaker than a large cloud model, so it's paired with retrieval narrowing.
- **Hybrid retrieval scoring (α=0.6).** Blends semantic (embedding) and lexical (TF-IDF) signals so exact word matches boost precision while paraphrases still match. Tradeoff: two retrievals instead of one, but both are fast (~0.1s each).
- **Three-tier provider with graceful degradation.** Tool → prompt → mock. Each level trades accuracy for reliability. Never hard-fails.
- **Confirm-before-execute, always.** No auto-run path. Safety-over-magic: chained commands can close tabs or quit windows.
- **Structured-output constraint on generation.** LLM must return strict JSON referencing only candidate commands. Anything outside is dropped.
- **Function-calling for command lookup.** Preferred path lets the LLM fetch exact command specs on demand, reducing hallucinations compared to inline prompt dumps. Falls back gracefully if the backend doesn't support tools.
- **Config kept to environment variables only.** Not wired into qutebrowser's `configdata.yml` — reduces surface area for an experimental feature.

---

## What I'd do next with more time

- **Multi-turn clarification.** Ambiguous queries either resolve imperfectly or get dropped; a follow-up question ("did you mean tab 3 or tab 4?") would meaningfully improve usability.
- **Expand the corpus beyond commands** to include `:set`-able config options.
- **Learn from confirm/reject feedback** — log which resolved commands users accept vs. decline, and use that to re-rank retrieval over time.
- **Bounded page-level actions** (e.g. "play this song on YouTube") — requires driving hint-mode/click and handling async page loads. Deliberately scoped out.
- **Real embedding fine-tuning or a larger local model** if evaluation showed retrieval quality was the bottleneck rather than generation.
- **Usage telemetry / eval harness** — a small offline eval set of (query → expected command) pairs to track accuracy as the corpus or model changes.
