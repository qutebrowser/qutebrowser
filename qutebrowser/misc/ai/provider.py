# SPDX-FileCopyrightText: Camilo <camilo@example.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""LLM client abstraction for command translation.

Supports any OpenAI-compatible chat endpoint (Ollama, LM Studio, OpenAI,
etc.) via the ``AI_BASE_URL`` environment variable.

Two translation strategies, tried in order:
  1. **Tool-based** — the LLM calls ``get_command_details`` to look up
     exact command specifications before responding.  Requires function-
     calling support in the backend.
  2. **Prompt-based** (fallback) — all candidate details are inlined in
     the system prompt.  Works with any backend.

If both fail, a deterministic mock provider returns the top candidate.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import time
import urllib.error
import urllib.request
from typing import Optional

from qutebrowser.utils import message
from qutebrowser.misc.ai.prompts import (
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_TOOL,
    format_command_details,
    format_corpus,
)
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
_MODEL: str = os.environ.get('AI_MODEL', 'gemma4:e4b')
_BASE_URL: str = os.environ.get(
    'AI_BASE_URL', 'http://localhost:11434/v1',
)

# ---------------------------------------------------------------------------
#  Tool definition for function-calling
# ---------------------------------------------------------------------------

_LOOKUP_TOOL = {
    'type': 'function',
    'function': {
        'name': 'get_command_details',
        'description': (
            'Look up full details for one or more qutebrowser commands. '
            'Returns each command\'s description, positional arguments '
            '(with allowed choices), and available flags.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'commands': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': (
                        'Command names to look up, '
                        'e.g. ["tab-close", "open", "navigate"]'
                    ),
                },
            },
            'required': ['commands'],
        },
    },
}

# ---------------------------------------------------------------------------
#  Low-level API call
# ---------------------------------------------------------------------------


def _chat_completion(
    messages: list[dict],
    tools: Optional[list[dict]] = None,
) -> Optional[dict]:
    """Call the OpenAI-compatible ``/v1/chat/completions`` endpoint.

    Returns the *message* dict from the first choice (with keys ``content``
    and optionally ``tool_calls``), or ``None`` on failure.
    """
    url = f"{_BASE_URL.rstrip('/')}/chat/completions"
    body: dict = {
        'model': _MODEL,
        'messages': messages,
        'temperature': 0,
    }

    if not tools:
        body['response_format'] = {'type': 'json_object'}
    else:
        body['tools'] = tools
        body['tool_choice'] = 'auto'

    body_bytes = json.dumps(body).encode('utf-8')

    headers = {'Content-Type': 'application/json'}
    if _API_KEY:
        headers['Authorization'] = f'Bearer {_API_KEY}'

    logger.info(
        "[llm] request: model=%s messages=%d tools=%s",
        _MODEL, len(messages), 'yes' if tools else 'no',
    )

    req = urllib.request.Request(url, data=body_bytes, headers=headers,
                                 method='POST')
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, urllib.error.HTTPError,
            json.JSONDecodeError, OSError, TimeoutError) as exc:
        logger.info("[llm] API call failed: %s", exc)
        return None

    try:
        msg = data['choices'][0]['message']
    except (KeyError, IndexError, TypeError) as exc:
        logger.info("[llm] Unexpected response shape: %s", exc)
        return None

    return dict(msg)


# ---------------------------------------------------------------------------
#  Tool-based translation
# ---------------------------------------------------------------------------


def _translate_with_tools(
    query: str,
    candidates: list[CandidateCommand],
    valid_names: set[str],
) -> Optional[list[ResolvedCommand]]:
    """Translate using the ``get_command_details`` tool.

    Returns ``None`` if the backend does not support tools or the call
    fails, allowing the caller to fall back to the prompt-based approach.
    """
    names_str = ', '.join(sorted(valid_names))
    messages: list[dict] = [
        {'role': 'system', 'content': SYSTEM_PROMPT_TOOL.format(
            names=names_str,
        )},
        {'role': 'user', 'content': query},
    ]

    logger.info(
        "[llm/tool] query=%r -> sending %d candidates "
        "(tool-based), tool defined",
        query, len(candidates),
    )
    logger.debug(
        "[llm/tool] query=%r -> available candidates: %s",
        query, names_str,
    )

    t0 = time.monotonic()
    msg = _chat_completion(messages, tools=[_LOOKUP_TOOL])
    if msg is None:
        logger.info(
            "[llm/tool] query=%r -> first call failed, "
            "falling back to prompt approach",
            query,
        )
        return None

    tool_calls = msg.get('tool_calls')
    if tool_calls:
        logger.info(
            "[llm/tool] query=%r -> LLM called %d tool(s)",
            query, len(tool_calls),
        )
        for tc in tool_calls:
            try:
                args = json.loads(tc['function']['arguments'])
            except (json.JSONDecodeError, KeyError) as exc:
                logger.info(
                    "[llm/tool] query=%r -> bad tool args: %s", query, exc,
                )
                continue

            cmd_names = args.get('commands', [])
            details: list[dict] = []
            for name in cmd_names:
                if name in valid_names:
                    cmd = next(c for c in candidates if c.name == name)
                    details.append(format_command_details(cmd))
                else:
                    logger.info(
                        "[llm/tool] query=%r -> LLM looked up unknown "
                        "command %r, ignoring",
                        query, name,
                    )

            logger.info(
                "[llm/tool] query=%r -> returning details for %d commands",
                query, len(details),
            )
            messages.append({
                'role': 'tool',
                'tool_call_id': tc['id'],
                'content': json.dumps(details),
            })

        t1 = time.monotonic()
        logger.info(
            "[perf] tool round-trip: %.1fs, making second call",
            t1 - t0,
        )
        msg = _chat_completion(messages, tools=[_LOOKUP_TOOL])
        llm_elapsed = time.monotonic() - t1
        if msg is None:
            logger.info(
                "[llm/tool] query=%r -> second call failed, "
                "falling back to prompt",
                query,
            )
            return None
        logger.info("[perf] LLM tool response took %.1fs", llm_elapsed)
    else:
        logger.info(
            "[llm/tool] query=%r -> no tool calls, using direct response",
            query,
        )

    content = msg.get('content') or ''
    if not content.strip():
        logger.info(
            "[llm/tool] query=%r -> empty content", query,
        )
        return None

    logger.debug(
        "[llm/tool] query=%r -> tool-based response: %s",
        query, content[:500],
    )

    resolved = _parse_llm_response(content, valid_names, query=query)
    return resolved if resolved else None


# ---------------------------------------------------------------------------
#  Prompt-based translation (fallback)
# ---------------------------------------------------------------------------


def _translate_with_prompt(
    query: str,
    candidates: list[CandidateCommand],
    valid_names: set[str],
) -> Optional[list[ResolvedCommand]]:
    """Translate by inlining all candidate details in the system prompt."""
    candidate_text = format_corpus(candidates)
    messages: list[dict] = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {
            'role': 'user',
            'content': (
                f"{candidate_text}\n\nUser request: {query}"
            ),
        },
    ]

    logger.info(
        "[llm/prompt] query=%r -> sending %d candidates, %d total chars",
        query, len(candidates),
        len(candidate_text) + len(SYSTEM_PROMPT) + len(query),
    )
    logger.debug(
        "[llm/prompt] query=%r -> candidate list:\n%s", query, candidate_text,
    )

    t0 = time.monotonic()
    msg = _chat_completion(messages)
    llm_elapsed = time.monotonic() - t0
    if msg is None:
        logger.info(
            "[perf] prompt-based call failed after %.1fs", llm_elapsed,
        )
        return None

    content = msg.get('content') or ''
    if not content.strip():
        logger.info(
            "[llm/prompt] query=%r -> empty content", query,
        )
        return None

    logger.info("[perf] LLM prompt call took %.1fs", llm_elapsed)
    resolved = _parse_llm_response(content, valid_names, query=query)
    return resolved if resolved else None


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

    Tries (in order):
      1. Tool-based translation (function calling).
      2. Prompt-based translation (candidate details inlined).
      3. Mock fallback.
    """
    valid_names = {c.name for c in candidates}

    # 1. Tool-based approach
    resolved = _translate_with_tools(query, candidates, valid_names)
    if resolved is not None:
        return resolved

    # 2. Prompt-based fallback
    resolved = _translate_with_prompt(query, candidates, valid_names)
    if resolved is not None:
        return resolved

    # 3. Mock fallback
    logger.info(
        "[llm] query=%r -> both tool and prompt approaches failed, "
        "using mock fallback",
        query,
    )
    return _mock_translate(query, candidates)
