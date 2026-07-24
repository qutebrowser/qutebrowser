# SPDX-FileCopyrightText: Camilo <camilo@example.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Orchestration: registry -> retrieval -> provider -> validation -> join."""

from __future__ import annotations

import logging
from typing import Optional

from qutebrowser.misc.ai import registry, retrieval, provider
from qutebrowser.misc.ai.types import CandidateCommand

logger = logging.getLogger('ai')

QUTEBROWSER_COMMAND_SEPARATOR = ' ;; '


def translate_query(
    query: str,
    top_k: Optional[int] = None,
) -> str:
    """Translate a natural-language *query* into a qutebrowser command string.

    Returns an empty string if no command could be resolved.
    """
    import os as _os
    if top_k is None:
        try:
            top_k = int(_os.environ.get('AI_TOP_K', '8'))
        except (ValueError, TypeError):
            top_k = 8

    corpus: list[CandidateCommand] = registry.get_corpus()
    if not corpus:
        logger.info("[translate] query=%r -> corpus is empty", query)
        return ''

    logger.info(
        "[translate] query=%r -> corpus=%d commands, top_k=%d",
        query, len(corpus), top_k,
    )

    candidates: list[CandidateCommand] = retrieval.retrieve(
        query, corpus, k=top_k,
    )
    if not candidates:
        logger.info("[translate] query=%r -> no candidates retrieved", query)
        return ''

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
        return ''

    resolved_names = [r.command for r in resolved]
    logger.info(
        "[translate] query=%r -> provider resolved: %s",
        query, resolved_names,
    )

    valid_names = {c.name for c in candidates}
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

    valid_commands: list[str] = []
    for entry in resolved:
        if entry.command not in valid_names:
            logger.info(
                "[translate] query=%r -> dropping hallucinated command %r "
                "(not in candidate set)",
                query, entry.command,
            )
            continue

        meta = cmd_meta.get(entry.command, {'flags': set(), 'positional_count': 0})
        positional_slots = meta['positional_count']
        positional_used = 0
        filtered_args: list[str] = []
        for arg in entry.args:
            if arg in meta['flags']:
                filtered_args.append(arg)
            elif positional_used < positional_slots:
                filtered_args.append(arg)
                positional_used += 1
            else:
                logger.info(
                    "[translate] query=%r -> dropping hallucinated arg %r "
                    "for command %r",
                    query, arg, entry.command,
                )

        if entry.args:
            cmd_str = f"{entry.command} {' '.join(filtered_args)}"
        else:
            cmd_str = entry.command
        valid_commands.append(cmd_str)

    if not valid_commands:
        logger.info(
            "[translate] query=%r -> all resolved commands were invalid", query,
        )
        return ''

    result = QUTEBROWSER_COMMAND_SEPARATOR.join(valid_commands)
    logger.info("[translate] query=%r -> final command: %s", query, result)
    return result
