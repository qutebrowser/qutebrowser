# Agent Task List — qutebrowser AI Command Translator

Hand this whole file to the coding agent (e.g. Claude Code) as the spec. Execute steps in order. Each step has a "done when" check — don't move on until it passes.

## Context for the agent

We are adding an AI feature to qutebrowser (https://github.com/qutebrowser/qutebrowser), a keyboard-driven, Vim-inspired browser written in Python on top of QtWebEngine. This is a take-home assignment for a Principal MLOps Engineer interview. The feature is a **natural-language-to-command translator**: the user types `:ai-do "close all tabs except this one and mute the rest"` and the feature resolves it into one or more real qutebrowser commands (e.g. `tab-close --except-current ;; tab-mute --all`), shows the resolved command string, and asks for confirmation before running it.

Scope boundary — do not build: page clicking/hint-mode automation, multi-turn dialogue, or anything that acts on arbitrary page DOM content. This feature only maps language to qutebrowser's own existing `:` command set.

## Step 0 — Fork and branch setup

1. Fork/clone `https://github.com/qutebrowser/qutebrowser` to the candidate's own account or a local copy.
2. Create branch `candidate/camilo/ai-feature` off `main` (rename if the candidate wants a different handle).
3. Confirm the project runs locally first, unmodified: follow qutebrowser's own `CONTRIBUTING.md` / `README.md` to install dev dependencies (likely `tox` or a `requirements-dev` file) and launch it once.

**Done when:** stock qutebrowser launches locally with no errors.

## Step 1 — Orient in the codebase

1. Locate how existing commands are registered. Look for `@cmdutils.register` usage, e.g. in `qutebrowser/browser/commands.py` or `qutebrowser/misc/*.py`. Note the decorator signature, how docstrings become `:help` text, and how command args are typed.
2. Locate the command execution path: how a resolved command string (e.g. `"tab-close --except-current"`) gets run programmatically. Look at `qutebrowser/commands/runners.py` (`CommandRunner.run`) — this is what the feature will call after user confirmation.
3. Locate the message/prompt utilities used for user-facing confirmations (e.g. `qutebrowser/utils/message.py`, `qutebrowser/mainwindow/statusbar/prompt.py` or similar `yesno` prompt pattern). This is what will show the resolved command and ask "run this? y/n".
4. Locate how command metadata (name, docstring, args) can be introspected in bulk — i.e. how to iterate over *all* registered commands, not just call one. Likely a global registry dict inside `qutebrowser.api.cmdutils` or `qutebrowser.commands.cmdutils`.

**Done when:** the agent can name the exact file/function for (a) registering a new command, (b) running a command string programmatically, (c) showing a yes/no prompt, (d) iterating the full command registry. Write these four file paths into a scratch note — they'll be needed repeatedly.

## Step 2 — New module layout

Create a new package: `qutebrowser/misc/ai/`

- `__init__.py` — empty
- `registry.py` — builds the retrieval corpus: iterate all registered qutebrowser commands, extract `{name, docstring/description, args}`, return as a list of structured entries. Cache in memory (rebuild is cheap, ~200 commands).
- `retrieval.py` — given a natural language query and the corpus from `registry.py`, return top-k candidate commands (default k=8). Implementation:
  - Try to import `sentence_transformers`. If available, embed corpus descriptions + query with `all-MiniLM-L6-v2`, rank by cosine similarity.
  - If `sentence_transformers` is not installed or fails to load (no internet, no model cached), fall back to a pure-stdlib/`sklearn`-free TF-IDF or simple keyword-overlap scorer. This fallback must have zero extra dependencies beyond what's already in scope, so the feature never hard-fails for a reviewer with a bare Python env.
  - Expose one function: `retrieve(query: str, corpus, k: int = 8) -> list[CandidateCommand]`, so the caller doesn't care which backend ran.
- `provider.py` — LLM client abstraction for the generation step:
  - Read config from environment variables: `AI_API_KEY` (optional), `AI_MODEL` (default `gemma2:2b`), `AI_BASE_URL` (default `http://localhost:11434/v1`, i.e. Ollama's OpenAI-compatible endpoint).
  - Use the OpenAI-compatible chat completions HTTP format (works unmodified against Ollama, LM Studio, OpenAI, or any compatible cloud provider — the whole point of `AI_BASE_URL` being configurable) — a plain `requests.post` call, no SDK dependency needed.
  - On connection failure/timeout (no local model running, no key, no network), fall back to a deterministic **mock provider**: simple rule-based matching against the top retrieved candidate (e.g. pick the single highest-scoring candidate command with no args) so the full pipeline still produces *something* runnable and reviewable offline. Log clearly (`message.info`) when running in mock mode, so it's never silently pretending to be the real model.
  - Public function: `translate(query: str, candidates: list[CandidateCommand]) -> list[ResolvedCommand]`.
- `prompts.py` — the system/user prompt template sent to the LLM. Must instruct the model to:
  - Only ever choose from the provided candidate command list (never invent a command name).
  - Return **strict JSON only**, no prose, no markdown fences: a list of `{"command": str, "args": [str, ...]}`.
  - Support returning multiple objects for multi-step requests (they'll be joined with qutebrowser's native `;;` chaining separator).
- `translator.py` — orchestration: `registry.get_corpus()` → `retrieval.retrieve()` → `provider.translate()` → validate every returned command name exists in the candidate set (reject/drop any hallucinated command, log a warning) → join into a single qutebrowser command string using `;;`.
- `commands.py` — registers the actual `:ai-do {query}` qutebrowser command using the pattern found in Step 1:
  1. Call `translator.translate_query(query)` to get the resolved command string.
  2. Show it to the user via the prompt/message utility found in Step 1 (e.g. `"Run: tab-close --except-current ;; tab-mute --all ? (y/n)"`).
  3. On confirmation, execute via the `CommandRunner.run` path found in Step 1.
  4. On rejection or empty/failed resolution, do nothing and show a short message.

**Done when:** `:ai-do "test query"` is a recognized command in `:help` and doesn't crash on any input, even with no model/network available (mock path).

## Step 3 — Config surface

Keep configuration to environment variables only for this take-home (`AI_API_KEY`, `AI_MODEL`, `AI_BASE_URL`, plus optionally `AI_TOP_K` and `AI_AUTO_CONFIRM=false`) — do not attempt to wire these into qutebrowser's `configdata.yml` settings system, as that's unnecessary surface area for a take-home and adds review complexity for no real benefit. Document defaults clearly in the README (Step 6).

**Done when:** running with zero env vars set still works end-to-end via the local-Ollama-then-mock fallback chain.

## Step 4 — Tests

Add `tests/unit/misc/ai/` (match qutebrowser's existing `tests/unit/...` layout) with:

- `test_registry.py` — corpus builds from a small fixture set of fake registered commands, extracts expected fields.
- `test_retrieval.py` — given a query and a fixed corpus, both the embedding path (if available) and the fallback path return sane top-k results; test the fallback path unconditionally (don't skip it even if `sentence_transformers` is installed, so CI without the package still proves the fallback works).
- `test_provider.py` — mock the HTTP call (use `responses` or `unittest.mock`) to test: (a) well-formed JSON response parses correctly, (b) malformed JSON is handled without crashing, (c) a hallucinated command name outside the candidate set is dropped, (d) connection failure triggers the mock provider path.
- `test_translator.py` — end-to-end with mocked retrieval + provider, confirms multi-command queries produce a correctly `;;`-joined string.

Run whatever qutebrowser's existing test invocation is (`tox`, or `pytest tests/unit`) and confirm the new tests pass alongside the existing suite without breaking anything else.

**Done when:** `pytest tests/unit/misc/ai/` is green, and a full existing-suite run isn't newly broken by the changes (spot-check by running the broader unit test directory, doesn't need to be exhaustive given take-home time constraints).

## Step 5 — Guardrail check (do this explicitly, don't skip)

- `git grep -i` for anything resembling a hardcoded API key, token, or secret before the final commit. There should be none — everything sensitive comes from env vars only.
- Confirm `.env` (if created for local convenience) is in `.gitignore` and never committed; provide `.env.example` instead with placeholder values and comments.
- Confirm the feature never executes a resolved command without the user confirmation step (no silent auto-run path, even in mock mode).

**Done when:** a `git log -p` / diff review shows no secrets anywhere in history on this branch.

## Step 6 — Deliverable docs (content already drafted — see companion files)

Place the following in the repo on this branch:
- `qutebrowser/misc/ai/README.md` (or top-level `AI_FEATURE.md`) — use the content from `feature-description.md` (companion deliverable, provided separately) as the feature description / design-decisions / next-steps writeup.
- Update or add a "How to run" section — use the content from `how-to-run.md` (companion deliverable) verbatim, adjusted for any file paths that changed during implementation.

**Done when:** a reviewer with no prior context could clone the branch, follow the README, and see the feature work using only the mock/local-Ollama path — no cloud API key required.

## Step 7 — Final PR prep

1. Push branch `candidate/camilo/ai-feature` to the fork.
2. Write a PR description (can reuse the feature-description.md content, shortened) targeting the original repo (or just leave it open against the fork if the reviewers only need branch access — confirm with the assignment instructions, they said "so we can review as a PR").
3. Do a final self-review diff: check for stray debug prints, commented-out code, TODOs that should either be resolved or explicitly listed in "what I'd do next."

**Done when:** the PR diff is clean, scoped, and every file in it is something you'd defend line-by-line in a live review.
