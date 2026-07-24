# SPDX-FileCopyrightText: Camilo <camilo@example.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Register the ``:ai-do`` command."""

from __future__ import annotations

import os
import logging

from qutebrowser.api import cmdutils
from qutebrowser.commands import runners
from qutebrowser.utils import message, usertypes

from qutebrowser.misc.ai import translator

logger = logging.getLogger('ai')


@cmdutils.register(maxsplit=0)
@cmdutils.argument('win_id', value=cmdutils.Value.win_id)
def ai_do(query: str, win_id: int) -> None:
    """Translate a natural-language request into qutebrowser commands.

    Uses an LLM (or mock fallback) to resolve the query and prompts the
    user for confirmation before executing.

    Args:
        query: The natural-language request, e.g.
               "close all tabs except this one".
        win_id: The window ID (filled automatically).
    """
    resolved = translator.translate_query(query)
    if not resolved:
        logger.info("[ai-do] query=%r -> no command resolved", query)
        message.info("AI: Could not resolve command from request.")
        return

    auto_confirm = os.environ.get('AI_AUTO_CONFIRM', '').lower() in (
        '1', 'true', 'yes',
    )

    runner = runners.CommandRunner(win_id)

    if auto_confirm:
        logger.info("[ai-do] query=%r -> auto-confirming: %s", query, resolved)
        runner.run(resolved, safely=True)
        return

    logger.info("[ai-do] query=%r -> awaiting confirmation: %s", query, resolved)
    message.confirm_async(
        title=f"Run: {resolved} ?",
        yes_action=lambda: runner.run(resolved, safely=True),
        no_action=lambda: message.info("AI: Command cancelled."),
    )
