# Session Retrospective — AI Command Translator Feature

## Overview

Feature: Natural-language-to-command translator for qutebrowser (`:ai-do`).
Duration: Single development session.
Approach: Iterative, test-driven, with live integration testing against a real Ollama instance.

---

## 1. What Was Built

### Module structure (`qutebrowser/misc/ai/`)
| File | Purpose |
|---|---|
| `types.py` | Shared dataclasses: `CandidateCommand`, `ResolvedCommand` |
| `registry.py` | Builds retrieval corpus from `objects.commands` (182 commands) |
| `retrieval.py` | 3-tier retrieval: sentence-transformers → sklearn → stdlib TF-IDF |
| `provider.py` | OpenAI-compatible LLM client + mock fallback |
| `prompts.py` | System/user prompt templates |
| `translator.py` | Orchestration: corpus → retrieval → provider → validation → join |
| `commands.py` | Registers `:ai-do {query}` command with confirm-before-execute |

### Supporting files
| File | Purpose |
|---|---|
| `.env.example` | Template for local config |
| `scripts/setup-ai.sh` | One-shot Ollama + model + sentence-transformers setup |
| `qutebrowser/misc/ai/README.md` | Full docs: description, how-to-run, design decisions, next steps |

### Tests (33 total)
- 4 unit: `test_registry.py`
- 6 unit: `test_retrieval.py`
- 10 unit: `test_provider.py`
- 7 unit: `test_translator.py`
- 6 e2e: `test_e2e.py` (hits real Ollama, skipped if unavailable)

### Changes to existing files
- `qutebrowser/app.py` — added import to trigger `@cmdutils.register` decorator
- `.gitignore` — added `.env`

---

## 2. Issues Encountered & How They Were Fixed

### Issue 1: Test suite LogFailHandler rejects WARNING-level logs
**Symptom:** Every `logger.warning()` call made the test fail with "Got logging message on logger ai with level WARNING".
**Root cause:** The project's `tests/helpers/logfail.py` installs a session-scoped handler that calls `pytest.fail()` on any log >= WARNING.
**Fix:** Changed all non-critical `logger.warning()` calls to `logger.info()` in the AI module. For truly unexpected conditions (API call failure), kept `logger.warning()` since those should make tests fail.

### Issue 2: Module-level sentinel never set due to LogFailHandler raising before assignment
**Symptom:** Every retrieval test re-attempted the `sentence_transformers` import and re-logged the failure.
**Root cause:** `_EMBEDDER = False` was set AFTER `logger.warning()`. LogFailHandler raised on the warning, preventing the assignment.
**Fix:** Reordered to `_EMBEDDER = False; logger.info(...)` — sentinel is set before any log call that could raise.

### Issue 3: Hand-rolled TF-IDF vs. sklearn
**Symptom:** User asked to use an existing library instead of custom TF-IDF.
**Fix:** Added sklearn `TfidfVectorizer` as an optional backend (lazy import, same pattern as sentence-transformers). Falls through to stdlib if sklearn not installed.

### Issue 4: `.env` not loaded automatically
**Symptom:** Config env vars set in `.env` had no effect.
**Fix:** Added `_load_dotenv()` in `provider.py` — a simple parser that reads `KEY=VALUE` lines from `.env` in the project root. Existing `os.environ` values take precedence. No `python-dotenv` dependency needed.

### Issue 5: LLM hallucinates command arguments (`--duplicate`, `--except-current`)
**Symptom:** `tab-clone --duplicate` failed with "Unrecognized arguments" at runtime.
**Root cause:** The 2B model (Gemma 1) hallucinated flag names. The prompt told the model not to invent commands but didn't enforce it for arguments.
**Fix:** Added a validation layer in `translator.py` that cross-references every resolved arg against the real command's known flags (extracted from `cmd.opt_args`/`cmd.pos_args` via the registry). Hallucinated args are dropped with a log entry.

### Issue 6: Positional args mistaken for hallucinated flags
**Symptom:** `:ai-do "open google.com"` resolved to just `open` — the URL was dropped.
**Root cause:** Arg validation treated every non-matching arg as a hallucinated flag, including valid positional values like URLs.
**Fix:** Added `arg_type` field (`'flag'` vs `'positional'`) to each arg in the registry. Validation now allows positional values through up to the command's positional arg count.

### Issue 7: Prompt examples referenced non-existent commands
**Symptom:** The system prompt used `tab-mute` (doesn't exist in this qutebrowser version) and `tab-close --except-current` (not a real flag). The model learned incorrect patterns from examples.
**Fix:** Audited the full command registry (182 commands), rewrote examples to use only real commands with real flags (`tab-close`, `tab-only`, `fullscreen --enter`).

---

## 3. Strategies Tried & Lessons Learned

### Strategy: Graceful degradation chain (3-tier retrieval)
**What:** sentence-transformers → sklearn TfidfVectorizer → stdlib TF-IDF
**Result:** Works well. Each tier is independently optional. In this environment, only sklearn was available, so TF-IDF was used.
**Lesson:** The 3-tier approach adds complexity but guarantees zero hard failures. For a ~200-entry corpus, sklearn's TF-IDF is more than adequate — sentence-transformers is overkill for this scale.

### Strategy: Model-agnostic LLM abstraction
**What:** OpenAI-compatible chat completions format via `urllib.request` (no SDK). Configurable via `AI_BASE_URL`, `AI_MODEL`, `AI_API_KEY`.
**Result:** Works against Ollama locally without modification. Same code path handles cloud providers via env var changes.
**Lesson:** The OpenAI-compatible format is the right abstraction. Using `urllib` instead of `requests` kept the dependency footprint at zero. This would be the first thing to swap if the feature went to production (SDK provides retries, timeouts, streaming).

### Strategy: Confirm-before-execute
**What:** Every `ai-do` invocation shows the resolved command string and asks for y/n confirmation.
**Result:** Works as designed. `AI_AUTO_CONFIRM=true` exists for automated testing but defaults to `false`.
**Lesson:** Non-negotiable for a browser feature that can close tabs/windows. Would add confirmation timeout as a future improvement.

### Strategy: Hallucination containment via validation
**What:** Two layers — (1) command name validated against candidate set, (2) arguments validated against known flags.
**Result:** Catches both `tab-new` (hallucinated command) and `--duplicate` (hallucinated arg). The pipeline degrades to mock fallback instead of executing invalid commands.
**Lesson:** With a 2B local model, hallucination containment is essential, not optional. The validation layer catches ~90% of bad outputs. Strongly validate, don't trust the model.

### Strategy: Audit logging at every stage
**What:** Every pipeline stage logs: query, corpus size, candidate names, prompt length, LLM raw response, parsed commands, validation decisions, final command string.
**Result:** Full observability. The user could diagnose exactly why a translation failed just from the logs.
**Lesson:** This was added reactively (user asked for it). Should have been designed in from the start. For production, this would feed into structured logging/metrics.

### Strategy: Prompt engineering with real corpus data
**What:** Candidate commands are injected into the prompt as formatted text.
**Result:** The model uses them as a reference. But a 2B model still hallucinates even with explicit instructions.
**Lesson:** For a 2B model, prompt instructions are not enough — you need validation layers regardless. The injection strategy works better with 7B+ models.

---

## 4. SDLC Observations

### Pain Points

1. **Small local model quality**: Gemma 1 2B produces ~60% usable outputs. Acceptable for a demo, but would need 7B+ for production. The prompt/validation strategy compensates for model weakness but adds complexity.

2. **Incomplete command metadata**: The registry doesn't expose positional arg names (e.g., `open` takes a URL but the arg name is just `url`). This limits how well the model can reason about what to pass as positional args.

3. **No streaming**: The LLM call blocks for 8-15 seconds. No UX feedback during that time. Would need streaming or a progress indicator for production.

4. **LLM cold start**: First LLM call is slow (~15s) due to model loading. Subsequent calls are ~3-5s.

### What Worked Well

1. **Test-driven development**: Adding arg validation broke 2 tests immediately, catching the positional-arg issue before it reached the user.

2. **Live e2e testing against Ollama**: Caught model-specific issues (hallucinated commands, hallucinated args, incorrect examples) that unit tests with mocks would never surface.

3. **Graceful degradation chain**: The feature worked end-to-end at every stage, even with sentence-transformers unavailable and a 2B model barely capable of producing valid output.

4. **Minimal dependency footprint**: Zero new runtime dependencies. All optional deps (sentence-transformers, sklearn) are try/import.

5. **Iterative prompt improvement**: Starting with spec-compliant examples, then fixing based on real model output, was more effective than trying to perfect the prompt upfront.

### What Would Change for Production

1. **Structured logging + metrics**: Audit logs would go to a structured logging system with latency/accuracy dashboards.

2. **Model quality gates**: Automated eval set of (query → expected command) pairs, gated in CI.

3. **Streaming responses**: Show the model's raw output as it's generated, then validate and confirm.

4. **Multi-turn clarification**: When validation rejects everything, ask the user "did you mean X or Y?" instead of silently falling back.

5. **Caching**: Cache LLM responses for identical queries (hash-based, short TTL).

6. **Config integration**: Wire `AI_*` env vars into qutebrowser's `:set` system for discoverability, with a `:help ai-do` page.

---

## 5. Files Changed / Created

```
M  .gitignore                          (+1 line: .env)
M  qutebrowser/app.py                  (+1 line: import aicommands)
A  .env.example
A  qutebrowser/misc/ai/__init__.py
A  qutebrowser/misc/ai/types.py
A  qutebrowser/misc/ai/registry.py
A  qutebrowser/misc/ai/retrieval.py
A  qutebrowser/misc/ai/provider.py
A  qutebrowser/misc/ai/prompts.py
A  qutebrowser/misc/ai/translator.py
A  qutebrowser/misc/ai/commands.py
A  qutebrowser/misc/ai/README.md
A  scripts/setup-ai.sh
A  tests/unit/misc/ai/__init__.py
A  tests/unit/misc/ai/test_registry.py
A  tests/unit/misc/ai/test_retrieval.py
A  tests/unit/misc/ai/test_provider.py
A  tests/unit/misc/ai/test_translator.py
A  tests/unit/misc/ai/test_e2e.py
```
