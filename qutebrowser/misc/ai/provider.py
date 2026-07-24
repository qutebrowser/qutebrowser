# SPDX-FileCopyrightText: Camilo <camilo@example.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""LLM client abstraction for command translation.

Supports any OpenAI-compatible chat endpoint (Ollama, LM Studio, OpenAI,
etc.) via the ``AI_BASE_URL`` environment variable.

Falls back to a deterministic mock provider when the LLM is unreachable.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import urllib.error
import urllib.request
from typing import Optional

from qutebrowser.utils import message
from qutebrowser.misc.ai.prompts import SYSTEM_PROMPT, format_corpus
from qutebrowser.misc.ai.types import CandidateCommand, ResolvedCommand

logger = logging.getLogger('ai')

# ---------------------------------------------------------------------------
#  .env file loader
# ---------------------------------------------------------------------------


def _load_dotenv() -> None:
    """Load ``.env`` from the project root (if it exists) into ``os.environ``.

    Existing environment variables take precedence so shell exports or
    ``systemd`` service overrides are never silently ignored.
    """
    candidates = [
        pathlib.Path(__file__).resolve().parent.parent.parent.parent / '.env',
        pathlib.Path.cwd() / '.env',
    ]
    for path in candidates:
        if path.is_file():
            break
    else:
        return

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, _, val = line.partition('=')
            key = key.strip()
            val = val.strip().strip('"\'')
            if key not in os.environ:
                os.environ[key] = val


_load_dotenv()

# ---------------------------------------------------------------------------
#  Environment-variable configuration
# ---------------------------------------------------------------------------

_API_KEY: str = os.environ.get('AI_API_KEY', '')
_MODEL: str = os.environ.get('AI_MODEL', 'gemma2:2b')
_BASE_URL: str = os.environ.get(
    'AI_BASE_URL', 'http://localhost:11434/v1',
)


def _chat_completion(
    messages: list[dict],
) -> Optional[str]:
    """Call the OpenAI-compatible ``/v1/chat/completions`` endpoint.

    Returns the response content string, or ``None`` on failure.
    """
    url = f"{_BASE_URL.rstrip('/')}/chat/completions"
    body = json.dumps({
        'model': _MODEL,
        'messages': messages,
        'temperature': 0,
        'response_format': {'type': 'json_object'},
    }).encode('utf-8')

    headers = {'Content-Type': 'application/json'}
    if _API_KEY:
        headers['Authorization'] = f'Bearer {_API_KEY}'

    req = urllib.request.Request(url, data=body, headers=headers, method='POST')

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, urllib.error.HTTPError,
            json.JSONDecodeError, OSError, TimeoutError) as exc:
        logger.info("[llm] API call failed (falling back to mock): %s", exc)
        return None

    try:
        return data['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError) as exc:
        logger.info("[llm] Unexpected response shape (falling back to mock): %s", exc)
        return None


# ---------------------------------------------------------------------------
#  Mock provider (deterministic fallback)
# ---------------------------------------------------------------------------


def _mock_translate(
    query: str,
    candidates: list[CandidateCommand],
) -> list[ResolvedCommand]:
    """Deterministic fallback: return the single top candidate with no args."""
    if not candidates:
        return []
    logger.info(
        "[mock] query=%r -> picking top candidate: %s",
        query, candidates[0].name,
    )
    message.info(
        "AI: running in mock mode (no LLM available) - "
        "using best candidate command directly.",
    )
    best = candidates[0]
    return [ResolvedCommand(command=best.name, args=[])]


# ---------------------------------------------------------------------------
#  LLM JSON parser
# ---------------------------------------------------------------------------


def _parse_llm_response(
    content: str,
    valid_names: set[str],
    query: str = '',
) -> list[ResolvedCommand]:
    """Parse the LLM's JSON response, discarding hallucinated commands."""
    content = content.strip()
    if content.startswith('```'):
        content = content.split('\n', 1)[-1]
        content = content.rsplit('```', 1)[0]

    logger.info(
        "[llm] query=%r -> raw response: %s", query, content[:500],
    )

    try:
        raw = json.loads(content)
    except json.JSONDecodeError:
        logger.info(
            "[llm] query=%r -> invalid JSON in response: %s",
            query, content[:200],
        )
        return []

    if not isinstance(raw, list):
        raw = [raw]

    resolved: list[ResolvedCommand] = []
    for item in raw:
        if not isinstance(item, dict):
            logger.info(
                "[llm] query=%r -> non-dict item in response: %s",
                query, item,
            )
            continue
        cmd_name = item.get('command', '')
        if cmd_name not in valid_names:
            logger.info(
                "[llm] query=%r -> hallucinated command %r "
                "(valid: %s) - dropping",
                query, cmd_name, sorted(valid_names),
            )
            continue
        args = item.get('args', [])
        if not isinstance(args, list):
            args = []
        resolved.append(ResolvedCommand(command=cmd_name, args=args))

    logger.info(
        "[llm] query=%r -> parsed %d valid commands: %s",
        query, len(resolved),
        [(r.command, r.args) for r in resolved],
    )
    return resolved


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------


def translate(
    query: str,
    candidates: list[CandidateCommand],
) -> list[ResolvedCommand]:
    """Translate a natural-language *query* into resolved commands.

    Uses the configured LLM provider, or the mock fallback on failure.
    """
    valid_names = {c.name for c in candidates}

    candidate_list = format_corpus(candidates)
    messages = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {
            'role': 'user',
            'content': (
                f"{candidate_list}\n\nUser request: {query}"
            ),
        },
    ]

    logger.info(
        "[llm] query=%r -> sending %d candidates, %d total prompt chars",
        query, len(candidates), len(candidate_list) + len(SYSTEM_PROMPT) + len(query),
    )

    content = _chat_completion(messages)
    if content is None:
        logger.info(
            "[llm] query=%r -> API call failed, falling back to mock",
            query,
        )
        return _mock_translate(query, candidates)

    resolved = _parse_llm_response(content, valid_names, query=query)
    if not resolved:
        logger.info(
            "[llm] query=%r -> no usable commands from LLM, falling back to mock",
            query,
        )
        return _mock_translate(query, candidates)

    return resolved
