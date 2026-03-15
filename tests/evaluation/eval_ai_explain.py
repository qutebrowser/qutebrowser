# SPDX-License-Identifier: GPL-3.0-or-later

"""LLM-as-a-judge evaluation of ai-explain explanation quality.

Uses RAGAS for dataset structure and a custom structured Claude judge
that returns both a score AND a reason for each metric:

  - faithfulness   : 0.0–1.0  fraction of claims grounded in context (no hallucination)
  - relevance      : 0 or 1   explanation addresses the selected text specifically
  - conciseness    : 0 or 1   explanation is 2–4 sentences, no padding
  - clarity        : 0 or 1   explanation is clear for a general technical audience

Usage:
    AI_API_KEY=sk-ant-... python tests/evaluation/eval_ai_explain.py

    # Override model under test or judge model:
    AI_MODEL=claude-haiku-4-5 AI_JUDGE_MODEL=claude-haiku-4-5 \\
        python tests/evaluation/eval_ai_explain.py

Results are printed to stdout and saved to tests/evaluation/eval_results.json.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import anthropic

# ---------------------------------------------------------------------------
# Path setup — allow running from repo root or from this directory
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from qutebrowser.components.ai_explain import (  # noqa: E402
    _SYSTEM_PROMPT,
    _build_prompt,
)
from tests.evaluation.fixtures import FIXTURES  # noqa: E402

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_API_KEY: str = os.environ.get("AI_API_KEY", "")
_MODEL: str = os.environ.get("AI_MODEL", "claude-haiku-4-5")
_JUDGE_MODEL: str = os.environ.get("AI_JUDGE_MODEL", "claude-haiku-4-5")

METRICS = ["faithfulness", "relevance", "conciseness", "clarity"]

_JUDGE_SYSTEM = """\
You are a strict quality judge evaluating AI-generated explanations of text \
selected by a user in a web browser. You will receive:
  - SELECTED TEXT: the exact text the user highlighted
  - CONTEXT: the surrounding paragraph from the page
  - PAGE TEXT: broader page content provided as background
  - EXPLANATION: the AI-generated explanation to evaluate

Score the explanation on exactly these four metrics and respond with valid JSON only.

Metric definitions:
  faithfulness  (float 0.0–1.0): What fraction of the explanation's factual claims \
are directly supported by CONTEXT or PAGE TEXT? 1.0 = fully grounded, \
0.0 = entirely fabricated or contradicted by the source.
  relevance     (int 0 or 1):    Does the explanation specifically address the \
SELECTED TEXT rather than giving a generic description of the surrounding topic? \
1 = yes, 0 = no.
  conciseness   (int 0 or 1):    Is the explanation concise and free of padding? \
Two valid formats are accepted: (a) 2–4 plain sentences, or (b) one short intro \
sentence followed by 2–4 bullet points. Both formats score 1 if there is no \
unnecessary repetition, padding, or restating of the selected text. Score 0 only \
if the explanation is genuinely verbose or redundant beyond these structures.
  clarity       (int 0 or 1):    Is the explanation clear and easy to understand \
for a general technical audience, using plain language? 1 = yes, 0 = no.

Respond ONLY with this JSON structure, no prose before or after:
{
  "faithfulness": {"score": <float>, "reason": "<one sentence>"},
  "relevance":    {"score": <0 or 1>, "reason": "<one sentence>"},
  "conciseness":  {"score": <0 or 1>, "reason": "<one sentence>"},
  "clarity":      {"score": <0 or 1>, "reason": "<one sentence>"}
}
"""


# ---------------------------------------------------------------------------
# Step 1 — Generate explanations using the real ai-explain pipeline
# ---------------------------------------------------------------------------


def _get_explanation(
    client: anthropic.Anthropic, selected: str, context: str, page_text: str
) -> str:
    """Call the Anthropic API exactly as _LLMWorker does."""
    prompt = _build_prompt(selected, context, page_text)

    with client.messages.stream(
        model=_MODEL,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        timeout=30,
    ) as stream:
        final = stream.get_final_message()

    return "\n".join(
        block.text
        for block in final.content
        if hasattr(block, "text") and block.type == "text"
    ).strip()


# ---------------------------------------------------------------------------
# Step 2 — Judge each explanation
# ---------------------------------------------------------------------------


def _judge_sample(
    client: anthropic.Anthropic,
    selected: str,
    context: str,
    page_text: str,
    explanation: str,
) -> dict[str, dict]:
    """Ask the judge LLM to score and explain all metrics in one call."""
    user_msg = (
        f"SELECTED TEXT:\n{selected}\n\n"
        f"CONTEXT:\n{context}\n\n"
        f"PAGE TEXT:\n{page_text}\n\n"
        f"EXPLANATION:\n{explanation}"
    )

    response = client.messages.create(
        model=_JUDGE_MODEL,
        max_tokens=512,
        system=_JUDGE_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
        timeout=30,
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        raw = raw.rstrip("`").strip()

    return json.loads(raw)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_evaluation() -> None:
    if not _API_KEY:
        print("ERROR: AI_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=_API_KEY)

    print("=" * 60)
    print("  ai-explain — LLM-as-a-Judge Evaluation")
    print("=" * 60)
    print(f"  Model under test : {_MODEL}")
    print(f"  Judge model      : {_JUDGE_MODEL}")
    print(f"  Fixtures         : {len(FIXTURES)}")
    print(f"  Metrics          : {', '.join(METRICS)}")
    print()

    # --- Step 1: generate explanations ---
    print("Step 1/2 — Generating explanations...")
    records = []
    for fixture in FIXTURES:
        print(f"  [{fixture['name']}] generating...")
        explanation = _get_explanation(
            client,
            fixture["selected_text"],
            fixture["context"],
            fixture["page_text"],
        )
        preview = explanation[:90].replace("\n", " ")
        print(f"    → {preview}{'...' if len(explanation) > 90 else ''}")
        records.append({**fixture, "explanation": explanation})

    # --- Step 2: judge each explanation ---
    print("\nStep 2/2 — Judging explanations...")
    for record in records:
        print(f"  [{record['name']}] judging...")
        scores = _judge_sample(
            client,
            record["selected_text"],
            record["context"],
            record["page_text"],
            record["explanation"],
        )
        record["scores"] = scores

    # --- Print results ---
    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)

    for record in records:
        print(f"\n┌─ {record['name']}")
        print(f"│  Selected: \"{record['selected_text']}\"")
        print(f"│  Explanation: {record['explanation'][:120].replace(chr(10), ' ')}...")
        print("│")
        for metric in METRICS:
            entry = record["scores"].get(metric, {})
            score = entry.get("score", "?")
            reason = entry.get("reason", "")
            print(f"│  {metric:<15} {score}  — {reason}")
        print("└" + "─" * 58)

    # --- Aggregate ---
    print("\n--- Aggregate scores (mean across all fixtures) ---")
    for metric in METRICS:
        scores = [
            r["scores"][metric]["score"] for r in records if metric in r["scores"]
        ]
        if scores:
            mean = sum(scores) / len(scores)
            bar = "█" * int(mean * 20)
            print(f"  {metric:<15} {mean:.3f}  {bar}")

    # --- Save ---
    out_path = Path(__file__).parent / "eval_results.json"
    aggregate = {}
    for metric in METRICS:
        scores = [
            r["scores"][metric]["score"]
            for r in records
            if metric in r.get("scores", {})
        ]
        aggregate[metric] = round(sum(scores) / len(scores), 4) if scores else None

    output = {
        "config": {"model": _MODEL, "judge_model": _JUDGE_MODEL},
        "aggregate": aggregate,
        "samples": [
            {
                "fixture": r["name"],
                "selected_text": r["selected_text"],
                "explanation": r["explanation"],
                "scores": r["scores"],
            }
            for r in records
        ],
    }
    out_path.write_text(json.dumps(output, indent=2))
    print(f"\nFull results saved → {out_path}")
    print("=" * 60)


if __name__ == "__main__":
    run_evaluation()
