# SPDX-FileCopyrightText: Camilo <camilo@example.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Prompt templates for the AI command translator."""

from __future__ import annotations

from qutebrowser.misc.ai.types import CandidateCommand


SYSTEM_PROMPT = """\
You are a qutebrowser command interpreter. Given a user's natural language \
request and a list of available commands with their arguments, translate the \
request into one or more qutebrowser commands.

Rules:
- ONLY use commands from the provided candidate list. Never invent commands.
- ONLY use arguments from a command's argument list. Never invent arguments.
- Arguments must be flat strings (e.g. "--flag" or "value"). Never nest \
objects or lists inside the args array.
- Return ONLY valid JSON, no prose, no markdown fences.
- Format: [{"command": "command-name", "args": ["--flag", "value"]}]
- For multi-step requests, return multiple objects in the array (they will \
be joined with ";;" automatically).
- Use an empty args list if no arguments are needed.
- If the request cannot be translated, return an empty list [].

Correct single command:
  Request: "close the current tab"
  Response: [{"command": "tab-close", "args": []}]

Correct with flag argument:
  Request: "close the tab with wikipedia"
  Response: [{"command": "tab-close", "args": ["--url", "wikipedia"]}]

Correct multi-step:
  Request: "close all tabs except this one and go fullscreen"
  Response: [{"command": "tab-only", "args": []}, {"command": "fullscreen", "args": ["--enter"]}]

WRONG - do not nest commands inside args:
  [{"command": "tab-only", "args": [{"command": "google", "args": []}]}]

WRONG - do not put arguments inside the command string:
  [{"command": "tab-close --force", "args": []}]\
"""


def format_corpus(candidates: list[CandidateCommand]) -> str:
    """Format candidate commands for inclusion in the LLM prompt."""
    lines = ["Available commands and their arguments:"]
    for cmd in candidates:
        arg_strs = []
        for arg in cmd.args:
            if arg.get('arg_type') == 'positional':
                disp = arg.get('display', arg.get('name', '?'))
                req = ' (required)' if arg.get('required') else ''
                arg_strs.append(f"<{disp}>{req}")
            else:
                long_f = arg.get('long_flag', '')
                short_f = arg.get('flag', '')
                if long_f and short_f:
                    flag_str = f"{long_f}/{short_f}"
                elif long_f:
                    flag_str = long_f
                elif short_f:
                    flag_str = short_f
                else:
                    flag_str = arg.get('name', '?')
                req = ' (required)' if arg.get('required') else ''
                arg_strs.append(f"{flag_str}{req}")
        args_text = f" {' '.join(arg_strs)}" if arg_strs else ""
        desc = cmd.description or "(no description)"
        lines.append(f"  {cmd.name} -- {desc}{args_text}")
    return '\n'.join(lines)
