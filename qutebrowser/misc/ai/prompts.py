# SPDX-FileCopyrightText: Camilo <camilo@example.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Prompt templates for the AI command translator."""

from __future__ import annotations

from qutebrowser.misc.ai.types import CandidateCommand

# ---------------------------------------------------------------------------
#  System prompt for the tool-based approach
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TOOL = """\
You are a qutebrowser command interpreter. Given a user's natural language \
request, translate it into one or more qutebrowser commands.

Available commands: {names}

Use the **get_command_details** tool before using a command — it returns \
the exact flags, positional arguments, and allowed choices for any command.

Rules:
- ONLY use commands from the available list.
- ONLY use flags and positional values returned by get_command_details.
- Positional arguments go directly as values (e.g. "prev"), NOT as flags \
(e.g. never write "--where prev").
- Arguments must be flat strings (e.g. "--flag" or "value"). Never nest \
objects or lists inside the args array.
- Return ONLY valid JSON, no prose, no markdown fences.
- Format: [{{"command": "command-name", "args": ["--flag", "value"]}}]
- For multi-step requests, return multiple objects in the array (they will \
be joined with ";;" automatically).
- Use an empty args list if no arguments are needed.
- If the request cannot be translated, return an empty list [].
- For 'open X' or 'go to X' requests, use the **open** command. If X \
looks like a bare domain name (e.g. "wikipedia", "google"), complete it \
to a valid URL with .com or .org (e.g. "wikipedia" → "wikipedia.org"). \
Keep multi-word or descriptive text as-is — the browser will search for it.

Correct single command:
  Request: "close the current tab"
  Response: [{{"command": "tab-close", "args": []}}]

Correct with flag argument:
  Request: "close the tab with wikipedia"
  Response: [{{"command": "tab-close", "args": ["--url", "wikipedia"]}}]

Correct multi-step:
  Request: "close all tabs except this one and go fullscreen"
  Response: [{{"command": "tab-only", "args": []}}, {{"command": "fullscreen", \
"args": ["--enter"]}}]

Correct positional (no -- prefix):
  Request: "navigate to the previous page"
  After look-up: navigate takes <where> (choices: prev|next|up|...)
  Response: [{{"command": "navigate", "args": ["prev"]}}]

Correct URL opening with TLD completion:
  Request: "open wikipedia"
  After look-up: open takes <url> (free text, no choices)
  Response: [{{"command": "open", "args": ["wikipedia.org"]}}]

Correct URL opening (multi-word stays as search):
  Request: "open python tutorial"
  Response: [{{"command": "open", "args": ["python tutorial"]}}]

WRONG - do not nest commands inside args:
  [{{"command": "tab-only", "args": [{{"command": "google", "args": []}}]}}]

WRONG - do not put arguments inside the command string:
  [{{"command": "tab-close --force", "args": []}}]

WRONG - do not use -- prefix for positional arguments:
  [{{"command": "navigate", "args": ["--where", "prev"]}}]\
"""

# ---------------------------------------------------------------------------
#  System prompt for the fallback (prompt-based) approach
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a qutebrowser command interpreter. Given a user's natural language \
request and a list of available commands with their arguments, translate the \
request into one or more qutebrowser commands.

Rules:
- ONLY use commands from the provided candidate list. Never invent commands.
- ONLY use arguments from a command's argument list. Never invent arguments.
- Positional arguments go directly as values (e.g. "prev"), NOT as flags \
(e.g. never write "--where prev"). Positional args are shown inside angle \
brackets like <where: prev|next|up> in the list.
- Arguments must be flat strings (e.g. "--flag" or "value"). Never nest \
objects or lists inside the args array.
- Return ONLY valid JSON, no prose, no markdown fences.
- Format: [{"command": "command-name", "args": ["--flag", "value"]}]
- For multi-step requests, return multiple objects in the array (they will \
be joined with ";;" automatically).
- Use an empty args list if no arguments are needed.
- If the request cannot be translated, return an empty list [].
- For 'open X' or 'go to X' requests, use the **open** command. If X \
looks like a bare domain name (e.g. "wikipedia", "google"), complete it \
to a valid URL with .com or .org (e.g. "wikipedia" → "wikipedia.org"). \
Keep multi-word or descriptive text as-is — the browser will search for it.

Correct single command:
  Request: "close the current tab"
  Response: [{"command": "tab-close", "args": []}]

Correct with flag argument:
  Request: "close the tab with wikipedia"
  Response: [{"command": "tab-close", "args": ["--url", "wikipedia"]}]

Correct multi-step:
  Request: "close all tabs except this one and go fullscreen"
  Response: [{"command": "tab-only", "args": []}, {"command": "fullscreen", "args": ["--enter"]}]

Correct positional (no -- prefix):
  Request: "navigate to the previous page"
  Response: [{"command": "navigate", "args": ["prev"]}]

Correct URL opening with TLD completion:
  Request: "open wikipedia"
  Response: [{"command": "open", "args": ["wikipedia.org"]}]

Correct URL opening (multi-word stays as search):
  Request: "open python tutorial"
  Response: [{"command": "open", "args": ["python tutorial"]}]

WRONG - do not nest commands inside args:
  [{"command": "tab-only", "args": [{"command": "google", "args": []}]}]

WRONG - do not put arguments inside the command string:
  [{"command": "tab-close --force", "args": []}]

WRONG - do not use -- prefix for positional arguments:
  [{"command": "navigate", "args": ["--where", "prev"]}]\
"""

# ---------------------------------------------------------------------------
#  Candidate list formatter (for the prompt-based fallback)
# ---------------------------------------------------------------------------


def format_corpus(candidates: list[CandidateCommand]) -> str:
    """Format candidate commands for inclusion in the LLM prompt."""
    lines = ["Available commands and their arguments:"]
    for cmd in candidates:
        arg_lines: list[str] = []
        for arg in cmd.args:
            if arg.get('arg_type') == 'positional':
                disp = arg.get('display', arg.get('name', '?'))
                choices = arg.get('choices')
                req = ' (required)' if arg.get('required') else ''
                desc = arg.get('desc', '')
                if choices:
                    choices_str = '|'.join(choices)
                    pos_str = f"  <{disp}: {choices_str}>{req}"
                else:
                    pos_str = f"  <{disp}>{req}"
                if desc:
                    pos_str += f" {desc}"
                arg_lines.append(pos_str)
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
                desc = arg.get('desc', '')
                flag_line = f"  {flag_str}{req}"
                if desc:
                    flag_line += f" {desc}"
                arg_lines.append(flag_line)

        desc = cmd.description or "(no description)"
        if arg_lines:
            arg_text = '\n' + '\n'.join(arg_lines)
        else:
            arg_text = ""
        lines.append(f"  {cmd.name} -- {desc}{arg_text}")
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
#  Command-details formatter (for the tool-response)
# ---------------------------------------------------------------------------


def format_command_details(cmd: CandidateCommand) -> dict:
    """Format a single command's details for a tool-response payload."""
    positional_args: list[dict] = []
    flags: list[dict] = []
    for arg in cmd.args:
        if arg.get('arg_type') == 'positional':
            entry: dict = {
                'name': arg.get('display', arg.get('name', '?')),
                'required': arg.get('required', True),
            }
            if arg.get('choices'):
                entry['choices'] = arg['choices']
            if arg.get('desc'):
                entry['description'] = arg['desc']
            positional_args.append(entry)
        else:
            entry = {
                'flag': arg.get('long_flag', arg.get('flag', '')),
                'required': arg.get('required', False),
            }
            if arg.get('desc'):
                entry['description'] = arg['desc']
            flags.append(entry)

    return {
        'name': cmd.name,
        'description': cmd.description or '(no description)',
        'positional_args': positional_args,
        'flags': flags,
    }
