# SPDX-FileCopyrightText: Camilo <camilo@example.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Build a retrieval corpus from the global command registry."""

from __future__ import annotations

from qutebrowser.misc import objects
from qutebrowser.misc.ai.types import CandidateCommand


def get_corpus() -> list[CandidateCommand]:
    """Iterate all registered commands and return structured entries.

    This reads from the global ``objects.commands`` dict, which is
    populated by ``@cmdutils.register`` decorators at import time.
    """
    corpus: list[CandidateCommand] = []
    for name, cmd in objects.commands.items():
        arg_list: list[dict] = []
        for param_name, (long_flag, short_flag) in cmd.opt_args.items():
            arg_info = {
                'name': param_name,
                'flag': short_flag,
                'long_flag': long_flag,
                'required': False,
                'arg_type': 'flag',
            }
            _enrich_arg(cmd, param_name, arg_info)
            arg_list.append(arg_info)
        for param_name, display_name in cmd.pos_args:
            arg_info = {
                'name': param_name,
                'display': display_name,
                'required': True,
                'arg_type': 'positional',
            }
            _enrich_arg(cmd, param_name, arg_info)
            arg_list.append(arg_info)

        entry = CandidateCommand(
            name=name,
            description=cmd.desc,
            args=arg_list,
        )
        corpus.append(entry)
    return corpus


def _enrich_arg(cmd, param_name: str, arg_info: dict) -> None:
    """Augment *arg_info* with choices, description, and type from *cmd*."""
    qute_arg = cmd._qute_args.get(param_name)
    if qute_arg is not None:
        if qute_arg.choices:
            arg_info['choices'] = qute_arg.choices

    arg_desc = cmd.docparser.arg_descs.get(param_name)
    if arg_desc:
        arg_info['desc'] = arg_desc

    type_hint = cmd._type_hints.get(param_name)
    if type_hint:
        arg_info['type'] = type_hint.__name__
