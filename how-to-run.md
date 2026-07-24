# How to Run

## Prerequisites

- A working qutebrowser dev environment (see the project's own `README.md`/`CONTRIBUTING.md` for base setup — Python 3.x + Qt/QtWebEngine).
- No API key or local model is strictly required — the feature runs in a degraded-but-functional mock mode with zero extra setup. See "Evaluation without any model" below if that's all you want to check.

## Optional: run with the full local model (recommended for the real experience)

1. Install [Ollama](https://ollama.com).
2. Pull the default model: `ollama pull gemma2:2b`
3. Make sure Ollama is running (it listens on `http://localhost:11434` by default — no extra config needed, this matches the feature's default `AI_BASE_URL`).
4. (Optional) install the local embedding retrieval dependency: `pip install sentence-transformers`. If skipped, retrieval automatically falls back to a lexical matcher — no error, no missing functionality, just a different retrieval backend.

## Optional: run against a cloud provider instead

Set these environment variables before launching qutebrowser:

```
export AI_BASE_URL="https://api.your-provider.com/v1"
export AI_MODEL="your-model-name"
export AI_API_KEY="your-key-here"
```

Any OpenAI-compatible chat completions endpoint works — no code changes needed, only these three variables.

## Evaluation without any model or dependency at all

Just launch qutebrowser as normal with no env vars set and `sentence-transformers` not installed. The feature will:
- Use the lexical retrieval fallback (still real retrieval, just not neural).
- Attempt the local Ollama endpoint, fail to connect, and fall back to the deterministic mock provider — clearly indicated via an in-app message so it's never mistaken for the real model output.
- Still run the full confirm-before-execute flow end-to-end with a runnable (if less accurate) resolved command.

This means the whole pipeline is reviewable with nothing installed beyond qutebrowser itself.

## Using the feature

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

## Environment variable reference

| Variable | Default | Purpose |
|---|---|---|
| `AI_BASE_URL` | `http://localhost:11434/v1` | OpenAI-compatible endpoint for the generation model |
| `AI_MODEL` | `gemma2:2b` | Model name sent in the request |
| `AI_API_KEY` | (unset) | Only needed for providers that require auth (local Ollama doesn't) |
| `AI_TOP_K` | `8` | Number of candidate commands retrieval surfaces to the model |
| `AI_AUTO_CONFIRM` | `false` | If `true`, skips the y/n prompt — off by default for safety, exists mainly for automated testing |

## Dependencies added

- `sentence-transformers` (optional — feature degrades gracefully without it)
- `requests` (likely already a qutebrowser dependency; used for the OpenAI-compatible HTTP calls)

No secrets are committed anywhere in this branch. See `.env.example` for the local-convenience variable template (not required to run — env vars can also just be exported in-shell).
