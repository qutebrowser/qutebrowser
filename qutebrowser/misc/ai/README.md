# AI Feature: Natural-Language Command Translator

## What it does

qutebrowser is entirely keyboard- and command-driven — every action goes through a `:` command (`:tab-close`, `:tab-mute`, `:open`, etc.). That's powerful once you know the vocabulary, but it means the barrier to entry is memorizing (or looking up) exact command names and flags. This feature adds a natural-language layer on top of that existing command set.

**Trigger:** `:ai-do "close all tabs except this one and mute the rest"` (bound to a key, e.g. `,a`, for convenience).

**Flow:**
1. The query is matched against a corpus built from qutebrowser's own command registry (name + docstring + args for every registered command) to retrieve the most relevant candidates.
2. A language model (local by default, cloud-optional) resolves the query into one or more of *only those candidate* commands, with concrete arguments.
3. The resolved command string is shown to the user for confirmation (e.g. `tab-close --except-current ;; tab-mute --all`) before anything runs.
4. On confirmation, it executes via qutebrowser's normal command-runner — the same path a hand-typed command would take.

Note on scope: qutebrowser's built-in `:` completion already does excellent fuzzy matching on command *names* — this feature isn't trying to replace that. It's aimed at the cases completion can't help with: queries that don't share vocabulary with the command name at all, and requests that require chaining multiple commands together (which the user would otherwise need to know two commands *and* the `;;` syntax for).

**Accessibility framing:** qutebrowser's keyboard-only design already makes it a strong option for users who can't rely on a mouse. A natural-language interface adds another axis to that: it lowers the requirement from "recall the exact command syntax" to "describe what you want," which matters for users who know their intent but not the vim-style vocabulary — a smaller but real accessibility gain layered on top of what the browser already does well.

## How to Run

### Prerequisites

- A working qutebrowser dev environment (see the project's own `README.md`/`CONTRIBUTING.md` for base setup — Python 3.x + Qt/QtWebEngine).
- No API key or local model is strictly required — the feature runs in a degraded-but-functional mock mode with zero extra setup. See "Evaluation without any model" below if that's all you want to check.

### Run with the full local model (recommended for the real experience)

**Quick start (one command):**
```bash
bash scripts/setup-ai.sh
```

This installs [Ollama](https://ollama.com) (if missing), pulls the default model (`gemma4:e4b`), and installs the optional `sentence-transformers` package for semantic retrieval.

**Or, step by step:**
1. Install [Ollama](https://ollama.com) and make sure it's running (`ollama serve` or `systemctl --user start ollama`).
2. Pull the default model: `ollama pull gemma4:e4b`
3. (Optional) `pip install sentence-transformers` — if skipped, retrieval falls back to lexical matching (no loss of functionality, just a different backend).

### Optional: run against a cloud provider instead

Set these environment variables before launching qutebrowser:

```
export AI_BASE_URL="https://api.your-provider.com/v1"
export AI_MODEL="your-model-name"
export AI_API_KEY="your-key-here"
```

Any OpenAI-compatible chat completions endpoint works — no code changes needed, only these three variables.

### Evaluation without any model or dependency at all

Just launch qutebrowser as normal with no env vars set and `sentence-transformers` not installed. The feature will:
- Use the lexical retrieval fallback (still real retrieval, just not neural).
- Attempt the local Ollama endpoint, fail to connect, and fall back to the deterministic mock provider — clearly indicated via an in-app message so it's never mistaken for the real model output.
- Still run the full confirm-before-execute flow end-to-end with a runnable (if less accurate) resolved command.

This means the whole pipeline is reviewable with nothing installed beyond qutebrowser itself.

### Using the feature

1. Launch qutebrowser from this branch.
2. Run `:ai-do "your request in plain English"` — for example:
   - `:ai-do "close every tab except the current one"`
   - `:ai-do "mute all tabs"`
   - `:ai-do "close all tabs except this one and mute the rest"` (multi-step, chained)
3. Confirm the shown command string when prompted (y/n).
4. (Optional) bind it to a key for convenience by adding to your `config.py`:
   ```python
   config.bind(',a', 'ai-do')
   ```
   Note: `:ai-do` needs an argument, so in practice you'd bind it to a prompt-fill pattern, e.g. `config.bind(',a', 'set-cmd-text :ai-do ')` to pre-fill the command bar rather than running with an empty query.

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

All inference runs on CPU by default — no GPU required. The all-MiniLM-L6-v2 model loads lazily on the first `:ai-do` invocation and stays cached in memory for subsequent calls.

Without `sentence-transformers`, the total drops to ~3 GB disk and ~4 GB RAM (Ollama + LLM only), since retrieval falls back to sklearn TF-IDF.

### Dependencies added

- `sentence-transformers` (optional — feature degrades gracefully without it)

No secrets are committed anywhere in this branch. See `.env.example` for the local-convenience variable template (not required to run — env vars can also just be exported in-shell).

## Major design decisions / tradeoffs

- **Retrieval corpus = the app's own command registry, not scraped docs.** This is the ground truth, always in sync with the installed version, and requires no external documentation dependency. Tradeoff: it only knows about commands, not about `:set` config options or broader "how do I..." questions — deliberately out of scope for this pass.
- **Local model by default, cloud as opt-in.** Generation defaults to a local model (Gemma 2 2B via Ollama's OpenAI-compatible endpoint) rather than requiring an API key. `AI_BASE_URL` / `AI_MODEL` / `AI_API_KEY` are all configurable so the same code path works against Ollama, LM Studio, or any OpenAI-compatible cloud provider — swapping providers is a config change, not a code change. Tradeoff: a 2B local model is weaker than a large cloud model, so it's paired with retrieval narrowing the candidate set to make the generation task easier (pick-from-a-short-list rather than free recall of ~200 command names).
- **Retrieval backend is itself swappable and degrades gracefully.** Preferred path uses a small local embedding model (`sentence-transformers`, ~80MB, CPU-only) for semantic matching. If that package or its cached model isn't available, it falls back automatically to a lexical/TF-IDF-style matcher — still legitimate retrieval, just not neural. This was a deliberate choice: for a small (~200-entry), high-vocabulary-overlap corpus like command docstrings, lexical matching is already strong, and it guarantees the feature can never hard-fail for a reviewer with a bare environment.
- **Confirm-before-execute, always.** No auto-run path, including in mock mode. This is a safety-over-magic choice: chained commands can close tabs, quit windows, or worse, so a resolved-but-unconfirmed action is never executed silently.
- **Structured-output constraint on generation.** The model is required to return strict JSON referencing only candidate commands already retrieved; anything referencing a command outside that set is dropped rather than executed. This bounds the blast radius of a hallucinated or malformed response to "the feature does nothing," never "the feature does something unintended."
- **Mock/offline fallback provider.** If no local model is reachable and no cloud key is set, a deterministic rule-based fallback still produces a runnable (if less accurate) result, so the entire pipeline — retrieval, confirmation, execution — remains demonstrable with zero setup and zero API key, per the assignment's guardrails.
- **Config kept to environment variables only.** Deliberately did not wire this into qutebrowser's `configdata.yml`/settings system — that would add real surface area (schema definitions, `:set` integration, docs generation) for no benefit at this scope. Env vars are sufficient, standard, and match the assignment's own suggested config pattern.

## What I'd do next with more time

- **Multi-turn clarification.** Right now an ambiguous query either resolves imperfectly or gets dropped by validation; a follow-up question ("did you mean tab 3 or tab 4?") would meaningfully improve usability.
- **Expand the corpus beyond commands** to include `:set`-able config options, so "make the tab bar bigger" resolves too, not just action commands.
- **Learn from confirm/reject feedback** — log which resolved commands users accept vs. decline, and use that to re-rank retrieval over time (even a simple frequency-based boost would help).
- **Bounded page-level actions** (e.g. "play this song on YouTube") — this is a meaningfully larger scope: it requires driving qutebrowser's hint-mode/click system and handling async page loads, which is DOM-dependent and a different risk profile than pure command dispatch. Deliberately scoped out to keep this feature small, safe, and reviewable in the available time; noted here as the clear next step if the feature proves useful.
- **Real embedding fine-tuning or a larger local model** if evaluation showed retrieval quality was the bottleneck rather than generation.
- **Usage telemetry / eval harness** — a small offline eval set of (query → expected command) pairs to track retrieval + generation accuracy as the corpus or model changes, rather than relying on manual spot-checks.
