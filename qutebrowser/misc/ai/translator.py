# SPDX-FileCopyrightText: Camilo <camilo@example.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Orchestration: registry -> retrieval -> provider -> validation -> join."""

from __future__ import annotations

import logging
import time
from typing import Optional

from qutebrowser.misc.ai import registry, retrieval, provider
from qutebrowser.misc.ai.types import CandidateCommand, ResolvedCommand

logger = logging.getLogger('ai')

QUTEBROWSER_COMMAND_SEPARATOR = ' ;; '

# Python argparse built-ins that are never valid qutebrowser flags.
_HALLUCINATED_FLAGS: set[str] = {'--help'}

# Commands where --all and a positional URL are mutually exclusive.
_MUTUALLY_EXCLUSIVE_ALL: set[str] = {'bookmark-del'}


def _is_flag(arg: str) -> bool:
    """Return True if *arg* looks like a flag (starts with ``-``)."""
    return arg.startswith('-')


def _build_cmd_meta(candidates: list[CandidateCommand]) -> dict[str, dict]:
    """Build a lookup dict mapping command names to their flag/positional metadata."""
    cmd_meta: dict[str, dict] = {}
    for c in candidates:
        flag_set: set[str] = set()
        positional_count = 0
        for arg in c.args:
            if arg.get('arg_type') == 'positional':
                positional_count += 1
            else:
                if 'long_flag' in arg:
                    flag_set.add(arg['long_flag'])
                if 'flag' in arg:
                    flag_set.add(arg['flag'])
        cmd_meta[c.name] = {
            'flags': flag_set,
            'positional_count': positional_count,
        }
    return cmd_meta


def _validate_command(
    entry: ResolvedCommand,
    meta: dict,
    valid_names: set[str],
    query: str,
) -> Optional[str]:
    """Validate and format a single resolved command into a command string.

    Returns the command string (e.g. ``"tab-close --url wikipedia"``) or
    ``None`` if the command should be dropped entirely.
    """
    command = entry.command
    if command not in valid_names:
        logger.info(
            "[translate] query=%r -> dropping hallucinated command %r "
            "(not in candidate set)",
            query, command,
        )
        return None

    flags = meta['flags']
    positional_slots = meta['positional_count']
    args = entry.args

    if not args:
        return command

    # --- flag-aware two-pass validation ---
    filtered: list[str] = []
    positional_used = 0
    skip_next = False

    for i, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue

        # Check if the arg is a hallucinated flag like --help
        if arg in _HALLUCINATED_FLAGS:
            logger.info(
                "[translate] query=%r -> stripping hallucinated flag %r "
                "for command %r",
                query, arg, command,
            )
            continue

        if _is_flag(arg):
            if arg in flags:
                # Known flag — keep it
                filtered.append(arg)
            else:
                # Unknown flag — hallucinated; also skip the next token if
                # it looks like the flag's value (not another flag).
                if (i + 1 < len(args) and not _is_flag(args[i + 1])):
                    logger.info(
                        "[translate] query=%r -> stripping hallucinated "
                        "flag-value pair (%r %r) for command %r",
                        query, arg, args[i + 1], command,
                    )
                    skip_next = True
                else:
                    logger.info(
                        "[translate] query=%r -> stripping hallucinated "
                        "flag %r for command %r",
                        query, arg, command,
                    )
        else:
            if positional_used < positional_slots:
                filtered.append(arg)
                positional_used += 1
            else:
                logger.info(
                    "[translate] query=%r -> dropping extra positional "
                    "arg %r for command %r",
                    query, arg, command,
                )

    # --- mutual exclusion: --all vs positional (e.g. bookmark-del) ---
    if command in _MUTUALLY_EXCLUSIVE_ALL:
        has_all = '--all' in filtered
        has_positional = any(
            not _is_flag(a) for a in filtered if a not in flags
        )
        # Actually, positionals are already in filtered, so check if
        # there's a positional slot consumed.
        if has_all and positional_used > 0:
            logger.info(
                "[translate] query=%r -> dropping --all for command %r "
                "because a positional URL was also provided",
                query, command,
            )
            filtered = [a for a in filtered if a != '--all']

    if not filtered:
        return command

    return f"{command} {' '.join(filtered)}"


def translate_query(
    query: str,
    top_k: Optional[int] = None,
) -> str:
    """Translate a natural-language *query* into a qutebrowser command string.

    Returns an empty string if no command could be resolved.
    """
    t0 = time.monotonic()
    import os as _os

    def _log_done(result: str) -> str:
        elapsed = time.monotonic() - t0
        if result:
            logger.info(
                "[perf] total translation took %.1fs -> %s", elapsed, result,
            )
        else:
            logger.info(
                "[perf] total translation took %.1fs -> no result", elapsed,
            )
        return result

    if top_k is None:
        try:
            top_k = int(_os.environ.get('AI_TOP_K', '8'))
        except (ValueError, TypeError):
            top_k = 8

    corpus: list[CandidateCommand] = registry.get_corpus()
    if not corpus:
        logger.info("[translate] query=%r -> corpus is empty", query)
        return _log_done('')

    logger.info(
        "[translate] query=%r -> corpus=%d commands, top_k=%d",
        query, len(corpus), top_k,
    )

    candidates: list[CandidateCommand] = retrieval.retrieve(
        query, corpus, k=top_k,
    )
    if not candidates:
        logger.info("[translate] query=%r -> no candidates retrieved", query)
        return _log_done('')

    candidate_names = [c.name for c in candidates]
    logger.info(
        "[translate] query=%r -> retrieved candidates: %s",
        query, candidate_names,
    )

    resolved = provider.translate(query, candidates)

    if not resolved:
        logger.info(
            "[translate] query=%r -> provider returned no commands", query,
        )
        return _log_done('')

    resolved_names = [r.command for r in resolved]
    logger.info(
        "[translate] query=%r -> provider resolved: %s",
        query, resolved_names,
    )

    valid_names = {c.name for c in candidates}
    cmd_meta = _build_cmd_meta(candidates)

    valid_commands: list[str] = []
    for entry in resolved:
        meta = cmd_meta.get(entry.command, {
            'flags': set(), 'positional_count': 0,
        })
        cmd_str = _validate_command(entry, meta, valid_names, query)
        if cmd_str:
            valid_commands.append(cmd_str)

    if not valid_commands:
        logger.info(
            "[translate] query=%r -> all resolved commands were invalid", query,
        )
        return _log_done('')

    result = QUTEBROWSER_COMMAND_SEPARATOR.join(valid_commands)
    logger.info("[translate] query=%r -> final command: %s", query, result)
    return _log_done(result)
