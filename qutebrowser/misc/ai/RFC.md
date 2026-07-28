# RFC: Natural-Language-to-Command Translation for qutebrowser

## Status: Draft · July 2026

---

## 1. Problem

qutebrowser has ~200 commands. Every action requires exact recall of the command name and its flags. Fuzzy completion helps with *name* recall but not with chaining, flag discovery, or queries that don't share vocabulary with the command name (e.g. "mute everything" → `tab-mute --all`).

Goal: let users describe what they want in natural language and have it translated into real qutebrowser commands, with confirmation before execution.

---

## 2. Architecture (as of July 2026)

```

  User query ("close tab with wikipedia")
         │
         ▼
  ┌──────────────┐
  │  RETRIEVAL   │── semantic + lexical search over ~200 commands → top‑k candidates
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │   PROVIDER   │── LLM translates query → JSON commands using candidate list
  │  ┌─────────┐ │      Strategy 1: function‑calling tool (get_command_details)
  │  │ tool    │ │      Strategy 2: prompt‑based (all details inlined)
  │  └─────────┘ │      Strategy 3: mock fallback (no LLM available)
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │  VALIDATION  │── strip hallucinated commands/args, enforce mutual exclusion
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │  CONFIRM +   │── "Run: tab-close --url wikipedia ?" → y/n
  │  EXECUTE     │
  └──────────────┘

```

Three strategies in the provider ensure graceful degradation: function‑calling (lowest hallucination), prompt‑based (works everywhere), mock (zero‑dep demo).

---

## 3. Key challenges

### 3.1 PyTorch / Qt segfault (`retrieval.py`)

**Symptom:** importing `sentence_transformers` after `QApplication` initialisation segfaults.

**Root cause:** PyTorch registers its own signal handlers and jemalloc memory allocator. If Qt has already set up its event loop, the two conflict at the C level.

**Fix:** `sentence_transformers` is imported *eagerly at module load time* (before `QApplication` exists). The import sits at the top of `retrieval.py`, not inside a function. A comment on lines 12–16 documents exactly why.

### 3.2 HuggingFace runtime phone-home (`retrieval.py`)

**Symptom:** even with `local_files_only=True`, `sentence_transformers` still makes HTTP requests to `huggingface.co` on import.

**Root cause:** the library's telemetry/agent subsystem initialises before reading the `local_files_only` flag.

**Fix:** `HF_HUB_OFFLINE=1` and `HF_HUB_DISABLE_TELEMETRY=1` are set via `os.environ.setdefault()` *before* the import statement on the same page. These env vars suppress all HuggingFace network requests at the C/curl level.

### 3.3 LLM treats positional args as flags (`prompts.py`, `translator.py`)

**Symptom:** the LLM outputs `navigate --where prev` instead of `navigate prev`. The validator then drops `--where` as an unrecognised flag and the value `prev` along with it, producing a broken `navigate`.

**Root cause:** the original prompt showed positional args as `<where>` — indistinguishable from flags to the LLM. No examples showed correct positional usage. The validation code also had no concept of hallucinated flag stripping.

**Fix — two parts:**
1. Prompt now shows choices explicitly: `<where: prev|next|up|increment|decrement|strip>`. Examples include a "WRONG" case for `--where prev`. Both the tool prompt and fallback prompt carry these rules.
2. Validator now does two‑pass arg processing: known flags pass through, hallucinated flags are stripped (along with their value token if present), remaining tokens fill positional slots. `--help` and other argparse built‑ins are hard‑blocked.

### 3.4 Retrieval misses obvious matches (`retrieval.py`)

**Symptom:** for "open wikipedia", the embedding model ranks `history-clear`, `home`, `version` above `open`.

**Root cause:** sentence‑transformers `all-MiniLM-L6-v2` operates on sentence‑level semantics, and "open" appears in many command descriptions ("Open the next tab" for `tab-next`, "Open a URL" for `open`). The embedding space doesn't cleanly separate `open` from other navigation-related commands.

**Fix:** **hybrid scoring** — the final retrieval score blends the semantic embedding with a lexical TF‑IDF signal:

```
score = 0.6 · embedding_cosine + 0.4 · tfidf_cosine
```

This ensures that exact term matches (e.g. "open" in both the query and the `open` command name) provide a guaranteed boost, while the semantic embedder still handles paraphrases. Measured at ~0.1s overhead for the extra TF‑IDF pass.

### 3.5 Mutual exclusion isn't in arg metadata

**Symptom:** `bookmark-del` accepts `--all` OR a URL, but not both. The LLM often outputs both, and validation had no concept of mutual exclusion.

**Fix:** hard‑code a `_MUTUALLY_EXCLUSIVE_ALL` set in `translator.py` that detects when `--all` and a positional URL coexist and drops `--all`. This is a manual list — a proper fix would require qutebrowser's argparser to surface mutual‑exclusion groups in its metadata.

---

## 4. The three improvements in this round

### 4.1 Richer command ingestion (`registry.py`)

**Before:** each arg dict had `name`, `flag`/`long_flag`, `required`, `arg_type`.

**After:** now also carries:
- `choices` — from `cmd._qute_args[name].choices` (e.g. the `where` arg of `navigate`)
- `desc` — from `cmd.docparser.arg_descs[name]`
- `type` — from `cmd._type_hints[name]`

This data feeds both the prompt format (so the LLM sees `<where: prev|next|...>`) and the tool response (so the LLM gets structured JSON).

### 4.2 Smarter prompt formatting (`prompts.py`)

Two separate system prompts:
- **`SYSTEM_PROMPT_TOOL`** — used when function calling is available. Instructs the LLM to call `get_command_details` before responding. Includes explicit WRONG examples for positional args with `--` prefix.
- **`SYSTEM_PROMPT`** — used as fallback. All candidate details inlined (same information, different delivery).

`format_corpus()` now renders positional args with their choices inline: `<where: prev|next|up|increment|decrement|strip> (required)`.

### 4.3 Tool‑based command lookup (`provider.py`)

Instead of dumping all candidate details into the prompt, we define an OpenAI‑compatible function‑calling tool:

```json
{
  "name": "get_command_details",
  "parameters": {
    "commands": ["tab-close", "navigate"]
  }
}
```

**Flow:** system prompt (tool instructions + candidate names only) → LLM calls tool → tool returns JSON specs → second LLM call produces final command JSON.

**Why:** smaller initial prompt, structured data delivery, lower hallucination rate (the LLM fetches exact specs on demand). Falls back to the prompt approach if the backend doesn't support function calling.

---

## 5. Remaining issues

| Issue | Impact | Workaround |
|---|---|---|
| Mutual‑exclusion groups are hard‑coded | New commands with `--all` + positional need manual additions | Low churn; could be automated if argparser exposes it |
| No multi‑turn clarification | Ambiguous queries silently produce wrong or empty results | Acceptable for v1 — improves with model quality |
| Eager PyTorch import adds ~500ms to startup | Measurable but not user‑visible (happens before GUI renders) | Could be deferred if PyTorch fixes signal‑handler conflict |
| Small LLM URL completion is unreliable | gemma4:e4b may not know wikipedia→.org vs .com | Use a larger/cloud model, or keep URLs as bare names (qutebrowser resolves via search engine) |

---

## 6. Why these tradeoffs are acceptable

- **Retrieval > free generation:** narrowing 200 commands to 8 candidates transforms a hard "recall from 200" problem into an easy "pick from 8" problem. Even a weak 2B model succeeds at the latter.
- **Graceful degradation chain:** tool → prompt → mock means the feature never hard‑fails. Each level trades accuracy for reliability.
- **Confirmation gate:** no matter how wrong the LLM is, nothing executes without the user pressing y.
- **Environment‑variable config only:** deliberately not wired into qutebrowser's settings system — reduces surface area for a feature that's experimental.
